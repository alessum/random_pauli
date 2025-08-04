import numpy as np
import functions as fn
from tqdm import tqdm


class Circuit:
    def __init__(self, N, gates, order):
        """
        Initialize the circuit object.
        - N is the number of qubits.
        - gates is either the list of gates or of parameters: 
            [circuit_type, geometry, Js] or [circuit_type, geometry]
            where if u1 is used, Js = [J, Jz] and if su2 is used, Js = J = Jz.
          if no Js is reported, the gates are set randomly.
        - initial_state is either the state or the parameters:
            [state_type, p, state_phases, theta]
        - order is the order of the gates.
        """
        self.N = N
        self.order = order
        self.gates = gates

    def run(self, masks_dict, state, T, objective, description=None):
        """
        Run the circuit and calculate the magnetization.
        
        Args:
            masks_dict: Dictionary of masks for gate operations
            state: Initial quantum state
            T: Number of time steps
            objective: List of objectives ['correlation', 'magic', 'entanglement']
            description: Optional description for progress bar
        
        Returns:
            tuple: (output_list, final_state)
        """
        # Initialize output arrays based on objectives
        outputs = {}
        if 'correlation' in objective:
            outputs['correlation'] = np.zeros((T+1, self.N), dtype=np.float64)
            outputs['correlation'][0] = fn.get_magnetization(state, self.N)
        if 'magic' in objective:
            outputs['magic'] = np.zeros(T+1, dtype=np.float64)
            outputs['magic'][0] = fn.stabilizer_renyi_entropy_numba(state, k=2)
        if 'entanglement' in objective:
            outputs['entanglement'] = np.zeros(T+1, dtype=np.float64)
            outputs['entanglement'][0] = fn.renyi_entanglement(state, alpha=2)

        for t in tqdm(range(1, T+1), desc=description, disable=not self.verbose):
            state = fn.apply_U(state, self.gates, self.order, masks_dict, None)
            
            if 'correlation' in objective:
                outputs['correlation'][t] = fn.get_magnetization(state, self.N)
            if 'magic' in objective:
                outputs['magic'][t] = fn.stabilizer_renyi_entropy_numba(state, k=2)
            if 'entanglement' in objective:
                outputs['entanglement'][t] = fn.renyi_entanglement(state, alpha=2)
        
        # Build output list in consistent order
        output_list = []
        for obj in ['correlation', 'magic', 'entanglement']:
            if obj in objective:
                output_list.append(outputs[obj])
        
        return output_list, state
