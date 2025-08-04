import numpy as np
import scipy.linalg as la
import datetime, timeit
import random as rd
import numpy.random as nprd
import shutil
terminal_width, _ = shutil.get_terminal_size()
from functools import reduce
import pickle
from scipy.stats import unitary_group
from tqdm import tqdm
from scipy.linalg import fractional_matrix_power as fmp
from math import comb

from scipy.linalg import eigh
import warnings
from itertools import combinations, product
from functools import reduce


from numba import njit, prange#, config,

# set the threading layer before any parallel target compilation
# config.THREADING_LAYER = 'threadsafe'

def print_matrix(matr, precision=4):
    s = [[str(e) if abs(e) > 1e-15 else '.' for e in row] for row in np.round(matr,precision)]
    lens = [max(map(len, col)) for col in zip(*s)]
    fmt = '\t'.join('{{:{}}}'.format(x) for x in lens if x != 0) or '.'
    table = [fmt.format(*row) for row in s]
    print('\n'.join(table))
#########################################################################
I = np.diag([1, 
               1]) + 0j
X = np.array([[0,1],
              [1,0]], dtype=complex)
Y = np.array([[0,-1j],
              [1j,0]], dtype=complex)
Z = np.array([[1, 0],
              [0,-1]], dtype=complex)
M = np.array([[0,1],
              [0,0]], dtype=complex)
P = np.array([[0,0],
              [1,0]], dtype=complex)
UP = np.array([1,0], dtype=complex)
DOWN = np.array([0,1], dtype=complex)

II = np.kron(I,I)
IX = np.kron(I,X)
XI = np.kron(X,I)
IZ = np.kron(I,Z)
ZI = np.kron(Z,I)
XX = np.kron(X,X)
YY = np.kron(Y,Y)
ZZ = np.kron(Z,Z)
PM = np.kron(P,M)
MP = np.kron(M,P)

#########################################################################

def get_masks(N, first_qubit, K=2):
    """
    Return an array of shape (2**K,) of index-arrays (masks), each selecting those
    computational-basis states (0..2**N-1) whose bits at positions
    first_qubit, first_qubit+1, ..., first_qubit+K-1 (mod N) equal one of the
    2**k possible patterns.

    Qubits are numbered from 0 (LSB) to N-1 (MSB).  A mask is the sorted list of
    integers whose binary representation has the specified K-bit pattern in those
    positions.
    
    K is the locality of the mask, i.e. the number of qubits in the window.
    """
    comp_basis = np.arange(2**N)
    masks = []

    # generate all k‐bit patterns 0..2**k-1
    for pattern in range(2**K):
        idx = comp_basis
        # for each qubit in the window, filter idx by whether that bit matches
        for offset in range(K):
            q = (first_qubit + offset) % N # qubit index
            want = (pattern >> offset) & 1 # get the bit of pattern at offset
            idx = idx[(idx // 2**q) % 2 == want]
        masks.append(idx)

    return np.array(masks, dtype=object)


def get_masks_typed(N, first_qubit, K):
    comp = np.arange(2**N, dtype=np.int64)
    D = 2**K
    M = (2**N) // D
    masks = np.empty((D, M), dtype=np.int64)

    for pat in prange(D):
        idx = comp
        for offset in range(K):
            q   = (first_qubit + offset) % N
            bit = (pat >> offset) & 1
            idx = idx[(idx // (1 << q)) % 2 == bit]
        masks[pat, :] = idx

    return masks

def apply_gate(state, gate, masks):
    '''
    Apply a gate to the state

    Parameters:
    - state: state vector on full Hilbert space
    - gate: 4x4 matrix corresponding to a 2-qubit gate
    - masks: list of 4 elements
        . first element contains the indices to treat as |00>
        . second element contains the indices to treat as |01>
        . third element contains the indices to treat as |10>
        . fourth element contains the indices to treat as |11>
    '''
    state_fin = np.zeros_like(state, dtype=complex)

    # Split the state in its four components
    state_split = state[masks]

    # Apply gate to state
    state_fin[masks] =  np.matmul(gate, state_split)[:,]

    return state_fin
    

@njit(parallel=True, fastmath=True, cache=True)
def apply_gate(state, gate, masks):
    '''
    Apply a gate to the state

    Parameters:
    - state: state vector on full Hilbert space
    - gate: 4x4 matrix corresponding to a 2-qubit gate
    - masks: list of 4 elements
        . first element contains the indices to treat as |00>
        . second element contains the indices to treat as |01>
        . third element contains the indices to treat as |10>
        . fourth element contains the indices to treat as |11>
    '''
    state_fin = np.zeros_like(state, dtype=np.complex128)
    num_elements = len(masks[0]) # 2^N/4
    for idx in prange(num_elements):
        i0, i1, i2, i3 = masks[0][idx], masks[1][idx], masks[2][idx], masks[3][idx]
        s0, s1, s2, s3 = state[i0], state[i1], state[i2], state[i3]
        t0 = gate[0,0]*s0 + gate[0,1]*s1 + gate[0,2]*s2 + gate[0,3]*s3
        t1 = gate[1,0]*s0 + gate[1,1]*s1 + gate[1,2]*s2 + gate[1,3]*s3
        t2 = gate[2,0]*s0 + gate[2,1]*s1 + gate[2,2]*s2 + gate[2,3]*s3
        t3 = gate[3,0]*s0 + gate[3,1]*s1 + gate[3,2]*s2 + gate[3,3]*s3
        state_fin[i0], state_fin[i1], state_fin[i2], state_fin[i3] = t0, t1, t2, t3
    return state_fin

@njit(parallel=True, fastmath=True, cache=True)
def apply_gate_k(state, gate, masks):
    """
    Apply a K-local gate to an N-qubit state vector.

    Parameters
    ----------
    state : complex128[2**N]
        The input state vector.
    gate : complex128[2**K, 2**K]
        The K-qubit gate to apply.
    masks : int64[2**K, M], M = 2**N / 2**K
        masks[c] is the array of all basis-state indices whose
        local K-bit pattern equals the integer c (0 ≤ c < 2**K).

    Returns
    -------
    state_out : 1D complex128 array, length = 2**N
        The output state, with the K-qubit gate applied in place.
    """
    D, M = masks.shape         # D = 2**K,  M = 2**N / 2**K
    out = np.zeros_like(state)

    for b in prange(M):
        # gather
        amp = np.empty(D, dtype=np.complex128)
        for c in range(D):
            amp[c] = state[masks[c, b]]

        # apply
        res = gate.dot(amp)

        # scatter
        for c in range(D):
            out[masks[c, b]] = res[c]

    return out

def apply_U(state, gates, gate_ordering_idx_list, masks_dict, K=None):
    '''
    Apply the Floquet operator to the state psi 2-qubit gate at a time

    Parameters:
    - state: state vector on full Hilbert space
    - gates: list of matrices. each is a 2-qubit gate
    - gate_ordering_idx_list: list of indeces correspoding to the
                              order the gates wil be applied:
                              eg. i -> gate_{i,i+1}
    - masks_dict: dictionary containing N masks defining how a gate on
                  2 consecutive sites needs to be applied
    '''
    for gate_idx, order_idx in enumerate(gate_ordering_idx_list):
        if K is not None:
            try:
                state = apply_gate_k(state, gates[gate_idx], masks_dict[order_idx])
            except:
                print('Error applying gate')
                print('len gates:', len(gates))
                print('gate:', gate_idx)
                print('list:', gate_ordering_idx_list)
                print('order:', order_idx)
                print('masks:', masks_dict[order_idx])
                raise
        else:
            state = apply_gate(state, gates[gate_idx], masks_dict[order_idx])
    return state

#########################################################################

def ptrace(rho, qkeep):
    N = int(np.log2(rho.shape[0]))
    rd = [2,] * N
    qkeep = list(np.sort(qkeep))
    dkeep = list(np.array(rd)[qkeep])
    qtrace = list(set(np.arange(N))-set(qkeep))
    dtrace = list(np.array(rd)[qtrace])
    if len(rho.shape) == 1: # if rho is ket
        temp = (rho
                .reshape(rd) # convert it to 2x2x2x...x2
                .transpose(qkeep+qtrace) # leave sites to trace as last
                .reshape([np.prod(dkeep),np.prod(dtrace)])) # dkeep x dtrace 
        partial_rho = temp.dot(temp.conj().T) 
    else : # if rho is density matrix
        partial_rho = np.trace(rho
                      .reshape(rd+rd)
                      .transpose(qtrace+[N+q for q in qtrace]+qkeep+[N+q for q in qkeep])
                      .reshape([np.prod(dtrace),np.prod(dtrace),
                                np.prod(dkeep),np.prod(dkeep)]))
    return partial_rho

def gen_u1(params=None):
    if params is not None:
        if len(params) == 2: params += [0, 0, 0]
        return gate_xxz_disordered(*params)
    gate = np.zeros((4,4), dtype=complex)
    gate[0,0] = np.exp(1j*np.random.rand()*2*np.pi)
    gate[3,3] = np.exp(1j*np.random.rand()*2*np.pi)
    gate[1:3,1:3] = unitary_group.rvs(2)
    return gate

def gen_su2(J=None):
    if J is None:
        J = np.random.rand()*np.pi
    swap = np.array([[1, 0, 0, 0],
                     [0, 0, 1, 0],
                     [0, 1, 0, 0],
                     [0, 0, 0, 1]])
    
    gate = np.eye(4) * np.cos(J/2) - 1j * np.sin(J/2) * swap
    return gate

def vNE(rho):
    eigvals = np.linalg.eigvalsh(rho)
    eigvals = eigvals[eigvals > 1e-10]
    return -np.sum(eigvals*np.log2(eigvals))

def load_mask_memory(N, K=2):
    '''
    Load the mask memory for a given N and K
    '''
    mask_dict = {}
    for n in range(N):
        mask_dict[n] = get_masks_typed(N, n, K)
    return mask_dict

def gen_Q(N, Ns=None):
    '''
    Generate the Q matrix composed by the projectors on the sectors of different
    magnetization values
    '''
    # if f'N{N}.pkl' in os.listdir('mask_memory'):
    #     DB = pickle.load(open(f'mask_memory/N{N}.pkl', 'rb'))
    #     mask_dict = DB['mask_dict']
    #     states_per_sector = DB['states_per_sector']
    #     qs = DB['qs']
    #     if Ns is None:
    #         return mask_dict
    #     Q = DB['Q']
    #     return mask_dict, qs, states_per_sector, Q
    
    if Ns is None:
        print('Ns must be specified if the mask memory is not available yet')
        mask_dict = {}
        for n in range(N):
            mask_dict[n] = get_masks(N, n)
        return mask_dict
    
    mask_dict = {}
    for n in range(N):
        mask_dict[n] = get_masks(N, n)
        
    computational_basis = np.arange(2**Ns)
    basis = np.array([bin(i).count('1') for i in computational_basis], dtype=int)

    states_per_sector = {}
    Q = np.zeros((2**Ns, 2**Ns), dtype=complex)    
    qs = []
    for M_A in range(Ns+1):
        temp_comp_states = computational_basis[basis == M_A]
        states_per_sector[M_A] = temp_comp_states
        vector = np.zeros(2**Ns)
        vector[temp_comp_states] = 1
        qs.append(np.outer(vector, np.conj(vector)))

    Q = reduce(np.add, qs)

    data_to_save = {'mask_dict': mask_dict,
                    'qs': qs,
                    'states_per_sector': states_per_sector,
                    'Q': Q}   

    with open(f'mask_memory/N{N}.pkl', 'wb') as file:
        pickle.dump(data_to_save, file)

    return mask_dict, qs, states_per_sector, Q

@njit(parallel=True, fastmath=True, cache=True)
def apply_u1(state, gate, masks):
    '''
    Apply a gate to the state

    Parameters:
    - state: state vector on full Hilbert space
    - gate: 4x4(1x1,2x2,1x1) matrix corresponding to a 2-qubit gate
    - masks: list of 4 elements
        . first element contains the indices to treat as |00>
        . second element contains the indices to treat as |01>
        . third element contains the indices to treat as |10>
        . fourth element contains the indices to treat as |11>
    '''
    state_fin = np.zeros_like(state, dtype=np.complex128)
    num_elements = len(masks[0]) # 2^N/4
    for idx in prange(num_elements):
        i0, i1, i2, i3 = masks[0][idx], masks[1][idx], masks[2][idx], masks[3][idx]
        s0, s1, s2, s3 = state[i0], state[i1], state[i2], state[i3]
        state_fin[i0] = gate[0,0]*s0
        state_fin[i1] = gate[1,1]*s1 + gate[1,2]*s2
        state_fin[i2] = gate[2,1]*s1 + gate[2,2]*s2
        state_fin[i3] = gate[3,3]*s3
    return state_fin

@njit(parallel=True, fastmath=True, cache=True)
def apply_su2(state, gate, masks):
    '''
    Apply a gate to the state

    Parameters:
    - state: state vector on full Hilbert space
    - gate: 4x4(1x1,1x1,1x1,1x1) matrix corresponding to a 2-qubit gate
    - masks: list of 4 elements
        . first element contains the indices to treat as |00>
        . second element contains the indices to treat as |01>
        . third element contains the indices to treat as |10>
        . fourth element contains the indices to treat as |11>
    '''
    state_fin = np.zeros_like(state, dtype=np.complex128)
    num_elements = len(masks[0]) # 2^N/4
    for idx in prange(num_elements):
        i0, i1, i2, i3 = masks[0][idx], masks[1][idx], masks[2][idx], masks[3][idx]
        state_fin[i0] = gate[0,0]*state[i0]
        state_fin[i1] = gate[1,2]*state[i1]
        state_fin[i2] = gate[2,1]*state[i2]
        state_fin[i3] = gate[3,3]*state[i3]
    return state_fin

def gate_xyz_disordered(h1, h2, Jx, Jy, Jz, h3, h4):
    """Return the unitary matrix for the disordered XXZ model."""
    U_H1 = np.diag(np.exp(-.5j*np.array([h1+h2, h1-h2, h2-h1, -h1-h2])))
    U_H2 = np.diag(np.exp(-.5j*np.array([h3+h4, h3-h4, h4-h3, -h3-h4])))
    U_XX = II * np.cos(Jx) - 1.0j * XX * np.sin(Jx)
    U_YY = II * np.cos(Jy) - 1.0j * YY * np.sin(Jy)
    U_ZZ = II * np.cos(Jz) - 1.0j * ZZ * np.sin(Jz)
    U_XXZ = U_XX @ U_YY @ U_ZZ
    return U_H1 @ U_XXZ @ U_H2

def gate_xxz_disordered(J, Jz, h1, h2, phi):
    ''' phase diagram [0,Pi] x [0,Pi]
    SWAP at J = pi
    '''
    U_H1 = np.diag(np.exp(-.5j*np.array([h1+h2, h1-h2, h2-h1, -h1-h2])))
    U_PM_MP = la.expm(-1j * J/2 * (PM * np.exp(1.0j * phi) + \
                                   MP * np.exp(-1.0j * phi)))
    U_ZZ = II * np.cos(Jz/4) - 1j * ZZ * np.sin(Jz/4) 
    U_XXZ = U_PM_MP @ U_ZZ
    return U_H1 @ U_XXZ

def gen_Jz(N):
    """
    Generate the Jz operator for N spins.
    """ 
    id_ = np.diag([1,1])
    sz = np.diag([1,-1])
    Jz = np.zeros((2**N, 2**N), dtype=np.complex128)
    for i in range(N):
        ops = [id_] * N
        ops[i] = sz
        op = reduce(np.kron, ops)
        Jz += op
    return Jz

def get_magnetization(st, N):
    id_ = np.array([1,1])
    up = np.array([0,1])
    
    res = np.zeros(N, np.float64)
    for i in prange(N):
        st_up = st.copy()
        st_dw = st.copy()
        ops = [id_] * N
        ops[i] = up
        up_m = reduce(np.kron, ops)

        st_up[up_m == 0] = 0
        st_dw[up_m == 1] = 0
        
        res[i] = (st.conj().dot(st_up - st_dw)).real
        
    return res

@njit(parallel=True, fastmath=True, cache=True)
def compute_magn(psi_2, magn_mask_is):
    N = int(np.log2(len(psi_2)))
    magn_is = np.zeros(N)
    for i in prange(N):
        magn_is[i] = np.dot(psi_2, magn_mask_is[i]).real
    return magn_is

def is_bad_value(coeff):
    return coeff == 0 or np.isnan(coeff) or np.isinf(coeff) or not np.isfinite(coeff)

def find_crossing_times(x_vals, y_vals1, y_vals2):
    """
    Find the crossing times between y_vals1 and y_vals2 by interpolation.
    
    Parameters:
    x_vals (np.ndarray): Array of x values.
    y_vals1 (np.ndarray): Array of y values for the first function.
    y_vals2 (np.ndarray): Array of y values for the second function.
    
    Returns:
    np.ndarray: Array of x values where the two functions cross.
    """
    # Compute the difference between the y values
    diff = y_vals1 - y_vals2
    
    # Find the indices where the sign of the difference changes
    crossing_indices = np.where(np.diff(np.sign(diff)))[0]
    
    # Interpolate to find the exact crossing points
    crossing_times = []
    if len(crossing_indices) == 0:
        return np.array(crossing_times)
    for idx in crossing_indices:
        x1, x2 = x_vals[idx], x_vals[idx + 1]
        y1, y2 = diff[idx], diff[idx + 1]
        crossing_time = x1 - y1 * (x2 - x1) / (y2 - y1)
        crossing_times.append(crossing_time)
    
    return np.array(crossing_times)


def gen_gates_order(N, geometry='random', boundary_conditions='PBC', eo_first='True'):
    # Generate the order the gates will be applied
    if geometry == 'random':
        if boundary_conditions == 'PBC':
            return rd.sample([n for n in range(N)],N)
        elif boundary_conditions == 'OBC':
            return rd.sample([n for n in range(N-1)],N-1)
    if geometry != 'brickwork':
        raise ValueError('Only random and brickwork geometries are supported')
    gate_ordering_idx_list = []
    if eo_first:
        for n in range(N):
            if n % 2 == 0:
                if n == N-1 and boundary_conditions == 'OBC':
                    continue
                else:
                    gate_ordering_idx_list.append(n)
    for n in range(N):
        if n % 2 == 1:
            if n == N-1 and boundary_conditions == 'OBC':
                continue
            else:
                gate_ordering_idx_list.append(n)
    if not eo_first:
        for n in range(N):
            if n % 2 == 0:
                if n == N-1 and boundary_conditions == 'OBC':
                    continue
                else:
                    gate_ordering_idx_list.append(n)

    return np.array(gate_ordering_idx_list, dtype=int)

def compute_unitary(gates, order, masks_dict, N):
    '''
    Compute the unitary of the circuit
    '''
    # since the gates are applied on states apply the gates to the identity matrix, column by column sending them to the apply_U function
    U = np.eye(2**N, dtype=complex)
    for i in tqdm(range(2**N)):
        U[:, i] = apply_U(U[:, i], gates, order, masks_dict)
    return U

def compute_hamiltonian(gates, order, masks_dict, N):
    '''
    Compute the Hamiltonian of the circuit
    '''
    U = compute_unitary(gates, order, masks_dict, N)
    # diagonalize U
    eigvals, eigvecs = np.linalg.eig(U)
    # compute the log of the eigenvalues
    log_eigvals = np.log(eigvals)
    return eigvecs.T.conj() @ log_eigvals @ eigvecs

@njit(parallel=True, fastmath=True, cache=True)
def compute_projector(Ns, states):
    """
    Computes the projector onto span{|s⟩ : s in states}.
    states should be a 1D np.int64 array of basis indices.
    """
    dim = 1 << Ns           # 2**Ns
    P   = np.zeros((dim, dim), dtype=np.complex128)
    n   = states.shape[0]   # number of basis states

    # Fill P[s1,s2] = 1 for all s1,s2 in states
    for i in prange(n):
        s1 = states[i]
        for j in prange(n):
            s2 = states[j]
            P[s1, s2] = 1.0

    # The Frobenius norm of this matrix is n, so normalize by n
    return P / n

def manual_U1_tw(rho, projectors):
    '''
    Apply the twirling operation to the density matrix rho.
    The twirling operation is a sum over the projectors, weighted by the density matrix.
    If ordered is True, the projectors are applied on the reordered basis.
    '''
    P = np.array([Pj / np.max(Pj) for Pj in projectors.values()])  # Shape (N, d, d)
    
    return np.sum(P * rho, axis=0)


''' Checking the consistency of S(rho || G(rho)) == S(G(rho)) - S(rho) 
<\

import scipy.special  # For binomial coefficient

state = fn.initial_state(N, sites_to_keep, .2 * np.pi, state_phases)
state /= np.linalg.norm(state)
# apply a U
h_list = np.random.uniform(-np.pi, np.pi, 5*N).reshape(N, 5) /alpha
gates = [fn.gen_u1([*h]) for h in h_list]
order = fn.gen_gates_order(N, geometry=geometry)
state = fn.apply_U(state, gates, order, masks_dict)
pstate = fn.ptrace(state, sites_to_keep)
##############################################################################
pstateQ = fn.twirling(pstate, projectors)    
    
reordered_pstate = basis_reordering.T @ pstate @ basis_reordering
reordered_pstateQ = basis_reordering.T @ pstateQ @ basis_reordering
    
from scipy.linalg import logm, expm

def vNentropy(x): return - x @ logm(x)
def idfunction(x): return x 

A = - basis_reordering.T @ pstateQ @ logm(pstateQ) @ basis_reordering
B = fn.operation_per_block(reordered_pstate, vNentropy, Ns)
C = fn.twirling(- basis_reordering.T @ pstate @ logm(pstateQ) @ basis_reordering, reordered_projectors)
C = (- basis_reordering.T @ pstate @ logm(pstateQ) @ basis_reordering)
C = (- pstate @ logm(pstateQ))

fn.print_matrix(A, 2)
fn.print_matrix(B, 2)
fn.print_matrix(C, 2)
np.trace(A), np.trace(B), np.trace(C)

>
'''


##### Relative entropy
warnings.simplefilter("ignore", category=UserWarning)

def _safe_logm(mat: np.ndarray, epsilon: float) -> np.ndarray:
    """
    Compute log(mat) by eigen-decomposition, clamping eigenvalues to [epsilon, ∞).
    """
    vals, vecs = eigh(mat)
    # clamp eigenvalues away from zero
    safe_vals = np.clip(vals, epsilon, None)
    log_vals  = np.log(safe_vals)
    return (vecs * log_vals) @ vecs.conj().T

def _safe_frac_power(mat: np.ndarray, power: float, epsilon: float) -> np.ndarray:
    """
    Compute mat**power by eigen-decomposition, clamping eigenvalues to [epsilon, ∞).
    """
    vals, vecs = eigh(mat)
    safe_vals = np.clip(vals, epsilon, None)
    frac_vals = safe_vals**power
    return (vecs * frac_vals) @ vecs.conj().T

def renyi_divergence(
    rho: np.ndarray,
    sigma: np.ndarray,
    alpha: float = 1.0,
    epsilon: float = 1e-12,
) -> float:
    """
    Computes D_α(ρ || σ) with spectrum-level regularization to avoid Infs/NaNs.

    Parameters
    ----------
    rho, sigma : np.ndarray
        Density matrices (Hermitian, trace 1).
    alpha : float
        Rényi parameter (α > 0, α ≠ 1 normally; α→1 gives KLD).
    epsilon : float
        Clamping floor for all eigenvalues.

    Returns
    -------
    float
        The Rényi divergence D_α(ρ || σ).
    """
    # basic checks
    if alpha <= 0:
        raise ValueError("α must be > 0.")
    t_rho = np.trace(rho)
    t_sig = np.trace(sigma)
    if not np.allclose(t_rho, 1, atol=1e-6) or not np.allclose(t_sig, 1, atol=1e-6):
        raise ValueError("Both ρ and σ must have trace 1: "
                         f"tr(ρ) = {t_rho}, tr(σ) = {t_sig}.")

    # α → 1 → Kullback-Leibler
    if np.isclose(alpha, 1.0):
        log_rho   = _safe_logm(rho,   epsilon)
        log_sigma = _safe_logm(sigma, epsilon)
        # D = tr[ρ (log ρ − log σ)]
        D = np.real_if_close(np.trace(rho @ (log_rho - log_sigma)))
        return float(D)

    # α → 0 limit
    if np.isclose(alpha, 0.0):
        # support projector of ρ
        vals_rho, _ = eigh(rho)
        support = (vals_rho > epsilon).astype(float)
        vals_sig, _ = eigh(sigma)
        return -np.log(np.sum(support * np.clip(vals_sig, epsilon, None)))

    # enforce α ≤ 2 if desired
    if alpha > 2:
        raise ValueError("α must be ≤ 2 for this implementation.")

    # general α ≠ 1
    rho_a = _safe_frac_power(rho,   alpha,     epsilon)
    sig_b = _safe_frac_power(sigma, 1 - alpha, epsilon)
    trace_term = np.trace(rho_a @ sig_b)

    # guard against tiny negatives or Infs
    trace_term = np.real_if_close(trace_term)
    trace_term = float(np.clip(trace_term, epsilon, None))

    return (1.0 / (alpha - 1.0)) * np.log(trace_term)

def renyi_divergence_sym(
    rho: np.ndarray,
    symmetry: str,
    alpha: float = 1.0,
    epsilon: float = 1e-12,
    K = None,
    Ubasis=None
) -> float:
    """
    Computes D_α(ρ || G(ρ)) with spectrum-level regularization to avoid Infs/NaNs.

    Parameters
    ----------
    rho : np.ndarray
        Density matrix (Hermitian, trace 1).
    symmetry : str
        Symmetry group for the twirling operation (e.g., 'U1', 'SU2').
    alpha : float
        Rényi parameter (α > 0, α ≠ 1 normally; α→1 gives KLD).
    epsilon : float
        Clamping floor for all eigenvalues.

    Returns
    -------
    float
        The Rényi divergence D_α(ρ || σ).
    """
    # basic checks
    if alpha <= 0:
        raise ValueError("α must be > 0.")
    if symmetry not in ['U1']:
        raise ValueError("symmetry must be 'U1'.")
    Ns = int(np.log2(rho.shape[0]))
    if Ubasis is not None:
        U_basis = Ubasis
    else:
        if symmetry == 'U1':
            projectors, U_basis = build_projectors(Ns)
        else:
            raise ValueError("Invalid symmetry group. Choose 'U1'.")
        
    if symmetry == 'U1':           
        sigma = manual_U1_tw(rho, projectors)
        
    rho = U_basis.conj().T @ rho @ U_basis
    sigma = U_basis.conj().T @ sigma @ U_basis
    t_rho = np.trace(rho)
    t_sig = np.trace(sigma)
    
    if not np.allclose(t_rho, 1, atol=1e-6) or not np.allclose(t_sig, 1, atol=1e-6):
        raise ValueError("Both ρ and σ must have trace 1: "
                         f"tr(ρ) = {t_rho}, tr(σ) = {t_sig}.")

    # α → 1 → Kullback-Leibler
    if np.isclose(alpha, 1.0):
        log_rho   = _safe_logm(rho,   epsilon)
        log_sigma = _safe_logm(sigma, epsilon)
        log_sigma_basis = U_basis @ log_sigma @ U_basis.conj().T
        if symmetry == 'U1':           
            log_sigma_basis_tw = manual_U1_tw(log_sigma_basis, projectors)
        log_sigma = U_basis.conj().T @ log_sigma_basis_tw @ U_basis
        # D = tr[ρ (log ρ − log σ)]
        D = np.real_if_close(np.trace(rho @ (log_rho - log_sigma)))
        return float(D)

    # α → 0 limit
    if np.isclose(alpha, 0.0):
        # support projector of ρ
        vals_rho, _ = eigh(rho)
        support = (vals_rho > epsilon).astype(float)
        vals_sig, _ = eigh(sigma)
        return -np.log(np.sum(support * np.clip(vals_sig, epsilon, None)))

    # enforce α ≤ 2 if desired
    if alpha > 2:
        raise ValueError("α must be ≤ 2 for this implementation.")

    # general α ≠ 1
    rho_a = _safe_frac_power(rho,   alpha,     epsilon)
    sig_b = _safe_frac_power(sigma, 1 - alpha, epsilon)
    trace_term = np.trace(rho_a @ sig_b)

    # guard against tiny negatives or Infs
    trace_term = np.real_if_close(trace_term)
    trace_term = float(np.clip(trace_term, epsilon, None))

    return (1.0 / (alpha - 1.0)) * np.log(trace_term)


def max_divergence(rho: np.ndarray, sigma: np.ndarray, epsilon=1e-10) -> float:
    """
    Computes the max divergence D_infty(rho || sigma).
    """
    eigvals, eigvecs = np.linalg.eigh(sigma)
    eigvals = np.maximum(eigvals, epsilon)  # Regularization

    sqrt_sigma_inv = eigvecs @ np.diag(1 / np.sqrt(eigvals)) @ eigvecs.T
    sandwiched_matrix = sqrt_sigma_inv @ rho @ sqrt_sigma_inv
    lambda_max = np.max(np.linalg.eigvalsh(sandwiched_matrix))
    
    return np.log(lambda_max)


def decompose_rho_modes(rho, Ub, Op):
    """
    Decomposes the density matrix 'rho' into its frequency (charge difference) modes.
    
    Parameters:
    -----------
    rho : ndarray
        The density matrix in the original (computational) basis.
    Ub : ndarray
        The unitary transformation matrix that rotates the computational basis into the 
        eigenbasis of J_z or J^2 (sorted from the lowest to the highest eigenvalue).
    Op : ndarray
        The magnetization operator or the total angular momentum operator J^2.
        
    Returns:
    --------
    freq_modes : dict
        A dictionary where keys are integer frequency modes (charge differences) and 
        the values are matrices of the same shape as the rotated density matrix
        containing the part of rho associated with that frequency.
    """
    # Rotate the density matrix into the J^2-eigenbasis.
    # In this basis, U_b.T @ J^2 @ U_b is diagonal.
    rho_rot = Ub.conj().T @ rho @ Ub
    
    # The diagonal of the rotated J^2 is the sorted charge vector.
    # (We assume here that this product is exactly diagonal; in numerical code, you might
    # enforce a tolerance.)
    diag_Op = Ub.conj().T @ Op @ Ub
    eigs_Op = np.real(np.diag(diag_Op))
    
    # Initialize dictionary to store matrices for each frequency mode.
    freq_modes = {}
    d = rho_rot.shape[0]
    
    # Loop over each element of rho_rot and assign it to the appropriate frequency.
    # The frequency is defined as the difference between the different values of the 
    # eigval of the Operator of the row and column.
    for i in range(d):
        for j in range(d):
            # frequency mode associated with element (i,j)
            freq = int(eigs_Op[i] - eigs_Op[j])
            # Initialize the mode if it does not exist; same shape as rho_rot.
            if freq not in freq_modes:
                freq_modes[freq] = np.zeros_like(rho_rot, dtype=rho_rot.dtype)
            freq_modes[freq][i, j] = rho_rot[i, j]
            
    return freq_modes

'''
# Test cases
rho_pure = np.array([[1, 0], [0, 0]])  # Pure state
rho_mixed = np.array([[0.5, 0], [0, 0.5]])  # Maximally mixed state
rho_intermediate = np.array([[0.7, 0.3], [0.3, 0.3]])  # Intermediate case

sigma_mixed = np.array([[0.6, 0.4], [0.4, 0.4]])  # Reference state

# Test different values of alpha
alpha_values = [0.0001, .9999, 100]  # Alpha → 0, 1 (KL), and large alpha
test_pairs = {
    "Pure vs Mixed": (rho_pure, sigma_mixed),
    "Mixed vs Mixed": (rho_mixed, sigma_mixed),
    "Intermediate vs Mixed": (rho_intermediate, sigma_mixed)
}

for name, (rho, sigma) in test_pairs.items():
    print(f"\n### {name} ###")
    print(f"  Max Divergence = {max_divergence(rho, sigma)}")
    print(f"  KL-1 Divergence = {renyi_divergence(rho, sigma, 1)}")
    for alpha in alpha_values:
        renyi_val = renyi_divergence(rho, sigma, alpha)
        print(f"  Rényi Divergence (α={alpha}): {renyi_val}")

    print(f"  Large α Approx: {renyi_divergence(rho, sigma, 100)}")
    
'''

# U1 ############
def spin_basis_1d(N, m=0.0, dtype=np.uint32, tol=1e-8):
    """
    NumPy‐only re-implementation of quspin.basis.spin_basis_1d
    valid for any N (even or odd) and allowing half-integer total M.

    Parameters
    ----------
    N : int
        Number of spin-1/2 sites.
    m : float
        Magnetization per site; 2*m*N must be (nearly) integer.
    dtype : np.dtype
        Output integer dtype for the bit-strings.
    tol : float
        Tolerance for floating-point checks.

    Returns
    -------
    Ns : int
        Number of basis states = binomial(N, n_up).
    states : ndarray[int]
        Unsigned ints (dtype) whose binary representation encodes the spin configuration,
        sorted descending exactly as QuSpin.spin_basis_1d does.
        
    TEST:
        Ns = np.arange(4, 21)
        for N in Ns:
            tot_states = 0
            ms = np.linspace(-N/2, N/2, N+1)/N
            for m in ms:
                numb_states = len(fn.spin_basis_1d(N, m=m))
                tot_states += numb_states
            assert tot_states == 2**N, f'numb states found for {N}: {tot_states} instead of {2**N}'
    """

    # 1) total 2M = 2*m*N must be integer
    twoM_float = 2 * m * N
    if abs(twoM_float - round(twoM_float)) > tol:
        raise ValueError(f"2*m*N = {twoM_float} not (nearly) integer")
    twoM = int(round(twoM_float))

    # 2) number of up-spins: n_up = (2M + N) / 2
    if (twoM + N) % 2 != 0:
        # Should never happen if twoM is int and N is int, but just in case
        raise ValueError(
            f"(2*m*N + N)/2 = {(twoM+N)/2} not integer"
        )
    n_up = (twoM + N)//2
    if not (0 <= n_up <= N):
        raise ValueError(f"n_up = {n_up} out of range [0, {N}]")

    # 3) enumerate all combinations of n_up ones in N bits,
    #    in descending‐bit lex order to match QuSpin exactly.
    states_list = []
    # iterate over positions N-1, N-2, …, 0
    for comb_ in combinations(range(N-1, -1, -1), n_up):
        s = 0
        for i in comb_:
            s |= (1 << i)
        states_list.append(s)
        
    states = np.array(states_list, dtype=dtype)
    assert len(states) == comb(N, int(N/2 + m * N)), \
        f'Wrong basis for {N}, {m}: {len(states)} != {comb(N, int(N/2 + m * N))}'

    return states


# Create a dictionary to hold projectors for each magnetization subsector.
# Here we assume the magnetization m runs from -NA/2 to NA/2 in steps of 1.

def build_projectors(Ns):
    projectors = {}
    U_U1 = np.zeros((2**Ns, 2**Ns), dtype=np.complex128)
    row_index = 0
    old_basis = None
    for m in np.linspace(-Ns/2, Ns/2, Ns+1)/Ns:
        # Retrieve the list of computational basis states for this magnetization sector.
        # (Assuming spin_basis_1d(NA, m=m) returns an object with a member .states.)
        if old_basis is not None:
            it = 0
            while len(old_basis) == len(spin_basis_1d(Ns, m=m)):
                m += 1e-7
                it += 1
                if it > 1000:
                    print("Warning: too many iterations")
                    break
        
        basis_obj = spin_basis_1d(Ns, m=m)
        old_basis = basis_obj
                
        states_m = basis_obj
        # print(f"Magnetization m {m:.2f} has", len(states_m), "states: states_m =", states_m)
        for state in states_m[::-1]:
            U_U1[state, row_index] = 1
            row_index += 1
        # Compute the projector onto the subspace spanned by these states.
        projectors[m] = compute_projector(Ns, states_m)
        
    return projectors, U_U1


def _infer_subsystem_dims(psi):
    """
    Given a statevector of length D, infer total qubit count N and
    split into nA = N//2 qubits for A and nB = N − nA for B.
    Returns (dA, dB).
    """
    D = psi.size
    # total qubits
    N = int(np.log2(D))
    if 2**N != D:
        raise ValueError(f"Length {D} is not a power of two.")
    nA = N // 2
    dA = 2**nA
    dB = 2**(N - nA)
    return dA, dB

def schmidt_coeffs(psi: np.ndarray):
    """
    Compute the normalized Schmidt coefficients of |psi⟩
    splitting into A⊗B with an equal-qubit cut.
    """
    dA, dB = _infer_subsystem_dims(psi)
    M = psi.reshape((dA, dB))
    s = np.linalg.svd(M, compute_uv=False)
    return s / np.linalg.norm(s)

def entanglement_entropy(psi: np.ndarray, base: float = 2.0):
    """
    von Neumann entanglement entropy S = −∑ p_i log_b p_i,
    where p_i = s_i^2 are Schmidt probabilities.
    """
    s = schmidt_coeffs(psi)
    p = s**2
    p = p[p > 0]
    return -np.sum(p * np.log(p)) / np.log(base)

def renyi_entanglement(psi: np.ndarray, alpha: float = 2, base: float = np.e):
    """
    Rényi entanglement entropy S_α = (1/(1-α)) log_b ∑ p_i^α.
    """
    s = schmidt_coeffs(psi)
    p = s**2
    if np.isclose(alpha, 1.0):
        return entanglement_entropy(psi, base)
    return (1.0/(1.0-alpha)) * np.log(np.sum(p**alpha)) / np.log(base)


def participation_entropy(psi: np.ndarray,
                          k: float = 2,
                          base: float = np.e,
                          eps: float = 1e-12) -> float:
    """
    Compute the Rényi participation entropy S_k(|psi>).

    Parameters
    ----------
    psi : np.ndarray
        State vector of length D (complex or real).
    k : float
        Rényi index. If k==1 (within eps), returns the Shannon entropy.
    base : float, optional
        Logarithm base (default: natural log). For bits use base=2.
    eps : float, optional
        Tolerance for detecting k==1.

    Returns
    -------
    S_k : float
        Participation entropy.
    """
    # Compute probabilities p_x = |<x|psi>|^2
    p = np.abs(psi)**2

    # Normalize (in case psi isn't strictly normalized)
    p_sum = p.sum()
    if not np.isclose(p_sum, 1.0, atol=eps):
        p = p / p_sum

    # Shannon limit
    if np.isclose(k, 1.0, atol=eps):
        # avoid log(0) with masking
        mask = p > 0
        return -np.sum(p[mask] * np.log(p[mask]) / np.log(base))

    # Rényi form
    sum_p_k = np.sum(p**k)
    return (1.0 / (1.0 - k)) * np.log(sum_p_k) / np.log(base)


def stabilizer_renyi_entropy(psi: np.ndarray, k: float) -> float:
    """
    Computation of the stabilizer Rényi entropy by applying
    single-qubit Pauli operations via tensor contractions.
    """
    D = psi.size
    L = int(np.log2(D))
    if 2**L != D:
        raise ValueError("State vector length must be a power of 2.")
    if np.isclose(k, 1.0):
        raise ValueError("k = 1 is singular; handle k→1 separately.")
    
    # Reshape psi for tensor operations
    psi_tensor = psi.reshape([2]*L)
    
    # Single-qubit Pauli matrices
    paulis = { 'I': I, 'X': X, 'Y': Y, 'Z': Z }
    
    total = 0.0
    # Iterate over all Pauli strings
    for labels in product('IXYZ', repeat=L):
        # Apply each single-qubit Pauli via tensordot
        psi_transformed = psi_tensor
        for qubit, lbl in enumerate(labels):
            psi_transformed = np.tensordot(
                paulis[lbl], psi_transformed, axes=([1], [qubit])
            )
            # Move the contracted axis back to original position
            psi_transformed = np.moveaxis(psi_transformed, 0, qubit)
        
        exp_val = np.vdot(psi, psi_transformed.ravel())
        total += (np.abs(exp_val)**(2*k))
    
    # Divide by D here (outside the loop to reduce operations)
    total /= D
    return np.log(total) / (1 - k)

@njit
def stabilizer_renyi_entropy_numba(psi, k):
    D = psi.size
    L = int(np.log2(D))
    total = 0.0
    # Pre-define pauli matrices in numba-compatible way
    pauli_arr = np.zeros((4, 2, 2), np.complex128)
    pauli_arr[0] = np.eye(2)
    pauli_arr[1] = np.array([[0, 1], [1, 0]], np.complex128)
    pauli_arr[2] = np.array([[0, -1j], [1j, 0]], np.complex128)
    pauli_arr[3] = np.array([[1, 0], [0, -1]], np.complex128)
    idxs = np.zeros(L, np.int32)
    for idx in range(4**L):
        code = idx
        psi_t = psi.copy()
        for q in range(L):
            lbl = code % 4
            code //= 4
            # apply single-qubit pauli
            new = np.zeros_like(psi_t)
            for state in range(psi_t.size):
                bit = (state >> q) & 1
                for b in range(2):
                    new_state = (state & ~(1 << q)) | (b << q)
                    new[new_state] += pauli_arr[lbl, b, bit] * psi_t[state]
            psi_t = new
        exp_val = 0+0j
        for i in range(D):
            exp_val += np.conjugate(psi[i]) * psi_t[i]
        total += np.abs(exp_val)**(2*k)
    total /= D
    return np.log(total) / (1 - k)