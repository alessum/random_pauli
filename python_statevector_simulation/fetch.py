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
                         timeout=30, max_retries=5, backoff=2):
    """Make HTTP requests with exponential backoff for retries"""
    headers = headers or {}
    
    # Add User-Agent to avoid rate limiting
    if 'User-Agent' not in headers:
        headers['User-Agent'] = 'fetch-script/1.0'
    
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(
                url, headers=headers, params=params,
                stream=stream, timeout=timeout
            )
            
            # Handle rate limiting specifically
            if resp.status_code == 429:
                retry_after = int(resp.headers.get('Retry-After', backoff * 2))
                print(f"Rate limited. Waiting for {retry_after} seconds before retrying...")
                time.sleep(retry_after)
                continue
                
            resp.raise_for_status()
            return resp
            
        except requests.RequestException as e:
            print(f"Request attempt {attempt}/{max_retries} failed: {e}")
            if attempt == max_retries:
                raise
                
            # Calculate backoff with jitter to avoid thundering herd
            jitter = 0.1 * backoff * (2 * np.random.random() - 1)
            sleep_time = backoff + jitter
            
            print(f"Retrying in {sleep_time:.1f} seconds...")
            time.sleep(sleep_time)
            
            # Increase backoff time for next retry
            backoff *= 2

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
    name   = artifact['name']  # e.g. results-batch-0
    dl_url = artifact['archive_download_url']
    size_mb = artifact.get('size_in_bytes', 0) / (1024 * 1024)  # Convert to MB

    run_dir = os.path.join(base_dir, f"run_{run_id}")
    os.makedirs(run_dir, exist_ok=True)

    zip_path = os.path.join(run_dir, f"{name}_{art_id}.zip")
    
    # Try downloading with progressively longer timeouts based on size
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            # Calculate timeout based on size (minimum 30s, plus 5s per MB, capped at 600s)
            base_timeout = 30 + min(int(size_mb * 5), 570)  # Cap at 10 minutes
            timeout = base_timeout * attempt  # Increase timeout with each attempt
            
            print(f"Downloading {name} ({size_mb:.1f}MB) [attempt {attempt}/{max_attempts}, timeout={timeout}s]")
            
            # Use larger chunk size for bigger files to improve performance
            chunk_size = 8192 * 4  # 32KB chunks
            
            # Get the response but don't use .raw, use the requests response directly
            response = request_with_retries(dl_url, headers=headers, stream=True, timeout=timeout)
            total_size = int(response.headers.get('content-length', 0))
            
            with open(zip_path, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=f"Downloading {name}") as pbar:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)
                            pbar.update(len(chunk))
                
            # If we get here, download succeeded
            print(f"Download of {name} completed successfully")
            break
        except Exception as e:
            print(f"Error downloading {name}: {e}")
            if attempt == max_attempts:
                print(f"Failed to download {name} after {max_attempts} attempts, skipping")
                return None
            # Exponential backoff
            sleep_time = attempt * 10
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

    # extract
    ext_dir = os.path.join(run_dir, f"artifact_{art_id}")
    try:
        if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
            print(f"Extracting {name}...")
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(ext_dir)
            print(f"Extraction of {name} completed")
            
            # Remove zip file after successful extraction to save space
            os.remove(zip_path)
            return ext_dir
        else:
            print(f"Skipping extraction for {name}: ZIP file doesn't exist or is empty")
            return None
    except zipfile.BadZipFile:
        print(f"Error: Bad ZIP file for {name}, skipping extraction")
        # Keep the bad zip file for inspection
        print(f"Bad ZIP file retained at {zip_path} for investigation")
        return None

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
        description="Fetch & combine .npz artifacts from Parallel Simulations"
    )
    p.add_argument('--owner',    default="alessum")
    p.add_argument('--repo',     default="random_pauli")
    p.add_argument('--workflow', default="executor.yml")
    p.add_argument('--hours',    type=float, default=12,
                   help="Lookback window for successful runs")
    p.add_argument('--outdir',   default="combined_results")
    p.add_argument('--token',    default=None,
                   help="GitHub token (or set GITHUB_TOKEN env var)")
    p.add_argument('--verbose',  action='store_true',
                   help="Enable verbose output")
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
        
    print(f"Found {len(runs)} successful workflow runs in the last {args.hours} hours.")

    # prepare a clean temp workspace
    tmp_base = "tmp_fetch"
    if os.path.exists(tmp_base):
        shutil.rmtree(tmp_base)
    os.makedirs(tmp_base)

    # 1) Download & extract
    for run in runs:
        arts = get_artifacts(args.owner, args.repo, run['id'], token)
        for art in arts:
            try:
                download_and_extract(art, token, tmp_base)
            except Exception as e:
                print(f"Failed to process artifact {art.get('name', 'unknown')}: {e}")
                print("Continuing with next artifact...")

    # 2) Find all .npz files with their metadata
    npz_list = []
    for entry in os.scandir(tmp_base):
        if entry.is_dir():
            npz_list += collect_npz_paths(entry.path)

    if not npz_list:
        print("No .npz files found in artifacts.")
        return

    # 3) Copy individual CR files to output directory, preserving structure
    for full_path, obs, jx, jz, cr, N, T in npz_list:
        # Create destination directory
        out_dir = os.path.join(args.outdir, obs, f"N{N}", f"T{T}", f"Jx{jx:.2f}", f"Jz{jz:.2f}")
        os.makedirs(out_dir, exist_ok=True)
        
        # Load the data
        data = np.load(full_path)
        
        # Try to determine the correct key for the data
        if obs == 'magic':
            key = 'magic'
        else:
            # For entanglement, try both possible keys
            if 'entan' in data:
                key = 'entan'
            elif 'entanglement' in data:
                key = 'entanglement'
            else:
                print(f"Warning: Could not determine key for {full_path}. Available keys: {data.files}")
                continue
        
        # Save to destination with consistent naming
        out_path = os.path.join(out_dir, f"cr{cr}.npz")
        np.savez_compressed(out_path, **{key: data[key]})
        print(f"Saved {obs} for CR={cr} @ N={N}, T={T}, Jx={jx:.2f}, Jz={jz:.2f}: {out_path} with key '{key}'")

    # Summarize what was processed
    magic_count = sum(1 for path, obs, _, _, _, _, _ in npz_list if obs == 'magic')
    entanglement_count = sum(1 for path, obs, _, _, _, _, _ in npz_list if obs == 'entanglement')
    
    # Count unique parameter combinations
    unique_params = set()
    for _, _, jx, jz, _, N, T in npz_list:
        unique_params.add((jx, jz, N, T))
    
    print("\n=== SUMMARY ===")
    print(f"Processed {len(npz_list)} total .npz files:")
    print(f"  - Magic: {magic_count}")
    print(f"  - Entanglement: {entanglement_count}")
    print(f"Across {len(unique_params)} unique parameter combinations (Jx, Jz, N, T)")
    
    # If any entanglement files, report on key usage
    if entanglement_count > 0:
        entan_keys = {}
        for full_path, obs, _, _, _, _, _ in npz_list:
            if obs == 'entanglement':
                try:
                    data = np.load(full_path)
                    if 'entan' in data:
                        entan_keys['entan'] = entan_keys.get('entan', 0) + 1
                    if 'entanglement' in data:
                        entan_keys['entanglement'] = entan_keys.get('entanglement', 0) + 1
                except Exception:
                    pass
                    
        print("\nEntanglement key usage:")
        for key, count in entan_keys.items():
            print(f"  - '{key}': {count} files")
    
    print("\nAll done. Results are available under", args.outdir)
    print("To load individual circuit realization files in a notebook, use:")
    print("""
# Example code for your notebook:
def load_individual_files(base_dir, observable, N, T, L, circuit_realizations):
    data_matrix = np.zeros((circuit_realizations, L, L, T+1))
    jx_values = np.linspace(0.1, np.pi-0.1, L)
    jz_values = np.linspace(0.1, np.pi-0.1, L)
    
    for cr in range(circuit_realizations):
        for i, Jx in enumerate(jx_values):
            for j, Jz in enumerate(jz_values):
                file_path = f"{base_dir}/{observable}/N{N}/T{T}/Jx{Jx:.2f}/Jz{Jz:.2f}/cr{cr}.npz"
                try:
                    data = np.load(file_path)
                    key = 'magic' if observable == 'magic' else ('entan' if 'entan' in data else 'entanglement')
                    data_matrix[cr, i, j, :] = data[key]
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
    
    return data_matrix
""")

if __name__ == "__main__":
    main()
