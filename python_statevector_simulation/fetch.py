#!/usr/bin/env python3
import os
import re
import sys
import time
import shutil
import zipfile
import argparse
from datetime import datetime, timezone, timedelta
from itertools import groupby
import requests
import numpy as np
from tqdm import tqdm

GITHUB_API = "https://api.github.com"

def request_with_retries(url, headers=None, params=None, stream=False,
                         timeout=10, max_retries=3, backoff=2):
    headers = headers or {}
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(
                url, headers=headers, params=params,
                stream=stream, timeout=timeout
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            if attempt == max_retries:
                raise
            time.sleep(backoff)

def get_workflow_runs(owner, repo, workflow_filename, token, since_dt):
    # (unchanged) fetch workflow list → identify workflow ID → list recent successful runs
    headers = {'Accept': 'application/vnd.github+json'}
    if token: headers['Authorization'] = f"Bearer {token}"

    # 1) find workflow ID
    url_list = f"{GITHUB_API}/repos/{owner}/{repo}/actions/workflows"
    wf_data = request_with_retries(url_list, headers=headers).json().get('workflows',[])
    wf_id = next((wf['id'] for wf in wf_data
                  if wf.get('path','').endswith("/" + workflow_filename)), None)
    if wf_id is None:
        raise RuntimeError(f"Workflow '{workflow_filename}' not found")

    # 2) paginate through runs
    runs, page = [], 1
    while True:
        url_runs = (
            f"{GITHUB_API}/repos/{owner}/{repo}"
            f"/actions/workflows/{wf_id}/runs"
        )
        params = {'status':'success','per_page':100,'page':page}
        batch = request_with_retries(url_runs, headers=headers, params=params) \
                    .json().get('workflow_runs',[])
        if not batch:
            break
        for run in batch:
            created = datetime.fromisoformat(run['created_at'].replace('Z','+00:00'))
            if created >= since_dt:
                runs.append(run)
            else:
                return runs
        page += 1

    return runs

def get_artifacts(owner, repo, run_id, token):
    headers = {'Accept': 'application/vnd.github+json'}
    if token: headers['Authorization'] = f"Bearer {token}"
    url = f"{GITHUB_API}/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
    return request_with_retries(url, headers=headers) \
             .json().get('artifacts', [])

def download_and_extract(artifact, token, base_dir):
    """Download one artifact ZIP and unzip under base_dir/run_<run_id>/"""
    headers = {'Accept': 'application/vnd.github+json'}
    if token: headers['Authorization'] = f"Bearer {token}"

    run_id = artifact['workflow_run']['id']
    art_id = artifact['id']
    name   = artifact['name']  # e.g. rydberg-results-batch-0
    dl_url = artifact['archive_download_url']

    run_dir = os.path.join(base_dir, f"run_{run_id}")
    os.makedirs(run_dir, exist_ok=True)

    zip_path = os.path.join(run_dir, f"{name}_{art_id}.zip")
    # stream download
    with request_with_retries(dl_url, headers=headers, stream=True).raw as r:
        with open(zip_path, 'wb') as f:
            for chunk in tqdm(r, desc=f"Downloading {name}", unit='KB', unit_scale=True):
                f.write(chunk)

    # extract
    ext_dir = os.path.join(run_dir, f"artifact_{art_id}")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(ext_dir)
    os.remove(zip_path)
    return ext_dir

def collect_npz_paths(extracted_dir):
    """
    Crawl extracted_dir for any .npz under:
      .../magic/N{N}/T{T}/Jx{Jx}/Jz{Jz}/cr{cr}.npz
      .../entanglement/N{N}/T{T}/Jx{Jx}/Jz{Jz}/cr{cr}.npz
    Return list of tuples: (full_path, observable, Jx, Jz, cr, N, T)
    """
    pattern = re.compile(r".*/(magic|entanglement)/N(\d+)/T(\d+)/Jx([0-9.]+)/Jz([0-9.]+)/cr(\d+)\.npz$")
    found = []
    for root, _, files in os.walk(extracted_dir):
        for fn in files:
            if not fn.endswith(".npz"):
                continue
            full = os.path.join(root, fn)
            m = pattern.match(full.replace(os.sep, '/'))
            if m:
                obs, N, T, jx, jz, cr = m.groups()
                found.append((full, obs, float(jx), float(jz), int(cr), int(N), int(T)))
    return found

def main():
    p = argparse.ArgumentParser(
        description="Fetch & combine .npz artifacts from Parallel Rydberg Simulations"
    )
    p.add_argument('--owner',    default="alessum")
    p.add_argument('--repo',     default="quera_proj")
    p.add_argument('--workflow', default="parallel-rydberg.yml")
    p.add_argument('--hours',    type=float, default=12,
                   help="Lookback window for successful runs")
    p.add_argument('--outdir',   default="combined_results")
    p.add_argument('--token',    default=None,
                   help="GitHub token (or set GITHUB_TOKEN env var)")
    args = p.parse_args()

    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token:
        print("ERROR: please provide a token via --token or GITHUB_TOKEN", file=sys.stderr)
        sys.exit(1)

    since = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    runs = get_workflow_runs(args.owner, args.repo, args.workflow, token, since)
    if not runs:
        print("No successful runs in the last", args.hours, "hours.")
        return

    # prepare a clean temp workspace
    tmp_base = "tmp_fetch"
    if os.path.exists(tmp_base):
        shutil.rmtree(tmp_base)
    os.makedirs(tmp_base)

    # 1) Download & extract
    for run in runs:
        arts = get_artifacts(args.owner, args.repo, run['id'], token)
        for art in arts:
            download_and_extract(art, token, tmp_base)

    # 2) Find all .npz files with their metadata
    npz_list = []
    for entry in os.scandir(tmp_base):
        if entry.is_dir():
            npz_list += collect_npz_paths(entry.path)

    if not npz_list:
        print("No .npz files found in artifacts.")
        return

    # 3) Group by (observable, N, T, Jx, Jz) and stack along CR-dimension
    #    Then save one combined .npz per group.
    npz_list.sort(key=lambda x: (x[1], x[5], x[6], x[2], x[3]))  # obs, N, T, Jx, Jz
    for (obs, N, T, jx, jz), group in groupby(
            npz_list, key=lambda x: (x[1], x[5], x[6], x[2], x[3])):
        files = [item[0] for item in group]
        # load each into an array
        arrays = [np.load(fp)['magic' if obs=='magic' else 'entan'] for fp in files]
        stacked = np.stack(arrays, axis=0)  # shape = (n_cr, T+1)

        # write out with N and T in the path
        out_dir = os.path.join(args.outdir, obs, f"N{N}", f"T{T}", f"Jx{jx:.2f}", f"Jz{jz:.2f}")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "combined.npz")
        key = obs
        np.savez_compressed(out_path, **{key: stacked})
        print(f"Saved combined {obs} @ N={N}, T={T}, Jx={jx:.2f}, Jz={jz:.2f}: {out_path}")

    print("All done. Combined results are under", args.outdir)

if __name__ == "__main__":
    main()
