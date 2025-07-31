#!/usr/bin/env python3

'''
python single_run.py \
  --N 14 \
  --T 1000 \
  --circuit-realizations 10 --L 3 \
  --params-path ../random_archive/angles_N14.json \
  --output-magic ../output/magic/N14 \
  --output-entanglement ../output/entan/N14 \
  --point 0 1 2 \
  --point 3 0 0
'''
import os
import json
import argparse
import numpy as np
from itertools import product
from tqdm import tqdm
from functions import gate_xyz_disordered, gen_gates_order, load_mask_memory
from circuit_obj import Circuit

def initial_state(N: int, n: int) -> np.ndarray:
    """N-qubit state with spin-up at site n and random complex elsewhere."""
    up = np.array([0, 1], dtype=complex)
    left  = np.random.rand(2**n) + 1j*np.random.rand(2**n)
    right = np.random.rand(2**(N-n-1)) + 1j*np.random.rand(2**(N-n-1))
    psi = np.kron(left, np.kron(up, right))
    return psi / np.linalg.norm(psi)

def random_basis_state(n_qubits: int) -> np.ndarray:
    """Uniform random computational basis state on n_qubits."""
    x = np.random.randint(0, 2**n_qubits)
    psi = np.zeros(2**n_qubits, dtype=complex)
    psi[x] = 1.0
    return psi

def build_circuits(args):
    """
    Load angle parameters and build all circuits on the full L x L grid.
    Returns a 3D list: circuits[cr][ix][iz].
    """
    with open(args.params_path, 'r', encoding='utf-8') as f:
        loaded = json.load(f)

    J_vals = np.linspace(0.1, np.pi - 0.1, args.L)
    circuits = []

    for cr in range(args.circuit_realizations):
        site_params = loaded[cr]
        grid = []
        for ix, Jx in enumerate(J_vals):
            row = []
            for iz, Jz in enumerate(J_vals):
                # build gates for sites 0…N-1
                gates = []
                for n in range(args.N):
                    p = site_params[str(n)] if isinstance(site_params, dict) else site_params[n]
                    θ1, θ2 = p['θ1'], p['θ2']
                    θ3, θ4 = p['θ3'], p['θ4']
                    gates.append(gate_xyz_disordered(
                        θ1, θ2,
                        Jx/4, -Jx/4, Jz/4,
                        θ3, θ4
                    ))
                gates = np.array(gates)
                assert gates.shape[0] == args.N

                # assemble circuit object
                order = gen_gates_order(args.N)
                circ = Circuit(N=args.N, gates=gates, order=order)
                circ.couplings = (Jx, Jz)
                circ.verbose = False
                row.append(circ)
            grid.append(row)
        circuits.append(grid)

    return circuits

def compute_and_save(args, circuits, masks):
    """
    For each (cr,ix,iz) in args.points (or all if empty), compute magic+entanglement
    and save compressed .npz per realization.
    """
    # default to all points if none provided
    if not args.points:
        args.points = list(product(
            range(args.circuit_realizations),
            range(args.L),
            range(args.L)
        ))

    # prepare output arrays
    magic_all = {}
    entan_all = {}
    
    # print points for debugging
    print(f"Computing {len(args.points)} points: {args.points}")

    for cr, ix, iz in tqdm(args.points, desc="Points"):
        circ = circuits[cr][ix][iz]
        # random basis input
        psi = random_basis_state(args.N)
        (m_vals, e_vals), _ = circ.run(
            masks, psi, args.T,
            objective=['magic','entanglement']
        )

        # save per-point
        Jx, Jz = circ.couplings
        m_dir = os.path.join(args.output_magic, f"Jx{Jx:.2f}", f"Jz{Jz:.2f}")
        e_dir = os.path.join(args.output_entanglement, f"Jx{Jx:.2f}", f"Jz{Jz:.2f}")
        
        # Create directories with error handling
        try:
            os.makedirs(m_dir, exist_ok=True)
            os.makedirs(e_dir, exist_ok=True)
        except OSError as e:
            print(f"Error creating directories: {e}")
            print(f"  Magic dir: {m_dir}")
            print(f"  Entanglement dir: {e_dir}")
            raise

        m_path = os.path.join(m_dir, f"cr{cr}.npz")
        e_path = os.path.join(e_dir, f"cr{cr}.npz")

        np.savez_compressed(m_path, magic=m_vals)
        np.savez_compressed(e_path, entan=e_vals)

        # optional: store in dict for return
        magic_all[(cr,ix,iz)] = m_vals
        entan_all[(cr,ix,iz)]  = e_vals

    return magic_all, entan_all

def parse_args():
    p = argparse.ArgumentParser(
        description="Compute magic & entanglement for selected circuits."
    )
    p.add_argument("--N",                   type=int,   required=True)
    p.add_argument("--T",                   type=int,   required=True)
    p.add_argument("--circuit-realizations", type=int,  required=True)
    p.add_argument("--L",                   type=int,   required=True)
    p.add_argument("--params-path",         type=str,   required=True,
                   help="JSON file with angle parameters")
    p.add_argument("--output-magic",        type=str,   required=True,
                   help="Base dir to save magic .npz files")
    p.add_argument("--output-entanglement", type=str,   required=True,
                   help="Base dir to save entanglement .npz files")
    p.add_argument(
        "--point", dest="points", nargs=3, metavar=('CR','IX','IZ'), type=int, action='append',
        help="One point to compute: cr index, Jx-idx, Jz-idx"
    )
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()

    # precompute masks once
    masks = load_mask_memory(args.N, 2)

    # build all circuits on the L×L grid
    circuits = build_circuits(args)

    # compute & save only the requested points
    magic, entan = compute_and_save(args, circuits, masks)
