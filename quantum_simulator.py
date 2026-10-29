"""Ideal single-register statevectors, density matrices and gate diagnostics.

Logic gates run through the primitive synthesis path; analytic gate matrices
provide an independent comparison. Pulses remain timeline annotations.
"""

import math
from collections import Counter

import numpy as np

from psi_lang import PsiOperation, StepSnapshot, build_classical_predicate, build_quantum_predicate
from quantum_gates import decompose_gate, gate_matrix, validate_gate


def apply_matrix(state, matrix, targets, num_qubits):
    """Apply a local matrix, first target the most significant local bit."""
    targets = list(targets)
    if len(set(targets)) != len(targets) or any(q < 0 or q >= num_qubits for q in targets):
        raise ValueError(f"Invalid ordered targets: {targets}")
    matrix = np.asarray(matrix, dtype=complex)
    if matrix.shape != (2 ** len(targets),) * 2:
        raise ValueError("Matrix dimension does not match targets")
    axes = [num_qubits - 1 - q for q in targets]
    axes += [a for a in range(num_qubits) if a not in axes]
    tensor = np.asarray(state).reshape((2,) * num_qubits).transpose(axes)
    updated = matrix @ tensor.reshape(2 ** len(targets), -1)
    return updated.reshape((2,) * num_qubits).transpose(np.argsort(axes)).reshape(-1)


def reduced_density_matrix(state, qubits, num_qubits):
    """Partial trace; keeps entanglement with all unselected qubits."""
    qubits = list(qubits)
    if not qubits or len(set(qubits)) != len(qubits) or any(q < 0 or q >= num_qubits for q in qubits):
        raise ValueError("Select distinct valid qubits")
    axes = [num_qubits - 1 - q for q in qubits]
    axes += [a for a in range(num_qubits) if a not in axes]
    amplitudes = np.asarray(state).reshape((2,) * num_qubits).transpose(axes).reshape(2 ** len(qubits), -1)
    return amplitudes @ amplitudes.conj().T


def entropy(density):
    values = np.linalg.eigvalsh(density).clip(0, 1)
    values = values[values > 1e-14]
    return float(-np.sum(values * np.log2(values)))


def bloch_vector(density):
    return np.array([2 * density[0, 1].real, -2 * density[0, 1].imag, (density[0, 0] - density[1, 1]).real])


def pair_diagnostics(state, qubits, num_qubits):
    rho = reduced_density_matrix(state, qubits, num_qubits)
    pur = float(np.trace(rho @ rho).real)
    result = {"density": rho, "purity": pur, "entropy": entropy(rho)}
    if len(qubits) == 2:
        paulis = [np.asarray(gate_matrix(a)) for a in "XYZ"]
        rhos = [reduced_density_matrix(state, [q], num_qubits) for q in qubits]
        means = [[np.trace(r @ p).real for p in paulis] for r in rhos]
        corr = np.array([[np.trace(rho @ np.kron(a, b)).real for b in paulis] for a in paulis])
        result["correlations"] = corr
        result["connected"] = corr - np.outer(*means)
        # Wootters concurrence applies to mixed two-qubit reductions too.
        yy = np.kron(paulis[1], paulis[1])
        roots = np.sqrt(np.maximum(0, np.linalg.eigvals(rho @ yy @ rho.conj() @ yy).real))
        roots = np.sort(roots)[::-1]
        result["concurrence"] = float(np.clip(roots[0] - roots[1:].sum(), 0, 1))
        result["mutual_information"] = entropy(rhos[0]) + entropy(rhos[1]) - entropy(rho)
    return result


def primitive_action(state, op, num_qubits):
    """Unitary primitive execution; guards are evaluated by the caller."""
    state = np.asarray(state, dtype=complex).copy()
    targets = list(range(num_qubits)) if op.targets == ["ALL"] else op.targets
    if any(type(q) is not int or not 0 <= q < num_qubits for q in targets):
        raise ValueError(f"Invalid targets: {targets}")
    if op.kind == "superpose":
        for q in targets:
            state = apply_matrix(state, gate_matrix("H"), [q], num_qubits)
    elif op.kind in ("phase", "flip"):
        predicate = build_quantum_predicate(op.predicate) if op.predicate else lambda bits: True
        matches = np.array([predicate([(i >> q) & 1 for q in range(num_qubits)]) for i in range(len(state))])
        if op.kind == "phase":
            state[matches] *= np.exp(1j * op.angle)
        else:
            if len(targets) != 1: raise ValueError("Flip needs one target")
            partners = np.arange(len(state)) ^ (1 << targets[0])
            if not np.array_equal(matches, matches[partners]):
                raise ValueError("Flip predicate must be invariant under flipping its target")
            state[matches] = state[partners[matches]]
    elif op.kind == "reflect":
        if "MEAN" not in (op.axis or "").upper(): raise ValueError("Only mean reflection is implemented")
        state = 2 * np.mean(state) - state
    else:
        raise ValueError(f"Not a unitary primitive: {op.kind}")
    return state


def reference_action(state, op, num_qubits):
    """Dense theory path, independent of gate synthesis and primitive execution."""
    if op.kind == "gate":
        return apply_matrix(state, gate_matrix(op.gate, *op.parameters, inverse=op.inverse), op.targets, num_qubits)
    if op.kind == "superpose":
        for q in (range(num_qubits) if op.targets == ["ALL"] else op.targets):
            state = apply_matrix(state, gate_matrix("H"), [q], num_qubits)
        return state
    if op.kind == "reflect":
        return (2 / len(state)) * np.sum(state) * np.ones_like(state) - state
    indices = np.arange(len(state))
    predicate = build_quantum_predicate(op.predicate) if op.predicate else lambda bits: True
    selected = [predicate([(i >> q) & 1 for q in range(num_qubits)]) for i in indices]
    if op.kind == "phase":
        diagonal = np.where(selected, np.exp(1j * op.angle), 1)
        return diagonal * state
    if op.kind == "flip":
        rows = [i ^ (1 << op.targets[0]) if selected[i] else i for i in indices]
        matrix = np.zeros((len(state), len(state)), dtype=complex)
        matrix[rows, indices] = 1
        return matrix @ state
    raise ValueError(f"No matrix reference for {op.kind}")


def gate_comparison(op):
    """Small local matrices in operand order, independent of register width."""
    from dataclasses import replace
    n = len(op.targets)
    local = replace(op, targets=list(reversed(range(n))), when=None)
    primitives = decompose_gate(local)
    actual = np.eye(2**n, dtype=complex)
    for primitive in primitives:
        actual = np.column_stack([primitive_action(col, primitive, n) for col in actual.T])
    reference = np.asarray(gate_matrix(op.gate, *op.parameters, inverse=op.inverse))
    return {"reference": reference, "actual": actual, "operator_error": float(np.max(np.abs(reference - actual))),
            "basis": "|" + " ".join(f"q{q}" for q in op.targets) + ">", "primitive_count": len(primitives)}


class QuantumSimulator:
    """Ideal pure-state evolution, with sampled projective measurements."""

    def __init__(self, num_qubits, operations, seed=None, initial_state=None, compare=True):
        if type(num_qubits) is not int or num_qubits < 1: raise ValueError("Register must contain at least one qubit")
        self.num_qubits, self.operations = num_qubits, operations
        self.initial_state = np.zeros(2**num_qubits, dtype=complex)
        self.initial_state[0] = 1
        if initial_state is not None:
            if isinstance(initial_state, str):
                if len(initial_state) != num_qubits or set(initial_state) - {"0", "1"}:
                    raise ValueError("Initial bitstring must have one binary digit per qubit (high bit first)")
                self.initial_state[:] = 0
                self.initial_state[int(initial_state, 2)] = 1
            else:
                value = np.asarray(initial_state, dtype=complex)
                if value.shape != self.initial_state.shape or not np.all(np.isfinite(value)) or not np.isclose(np.linalg.norm(value), 1, rtol=0, atol=1e-10):
                    raise ValueError("Initial state must be finite, normalized, and match the register")
                self.initial_state = value.copy()
        self.state = self.initial_state.copy()
        self.seed, self.compare = seed, compare
        self.rng = np.random.default_rng(seed)
        self.classical_bits, self.snapshots, self.measurements = {}, [], {}

    def run(self, record=True):
        self.state = self.initial_state.copy()
        self.classical_bits, self.snapshots, self.measurements = {}, [], {}
        self.rng = np.random.default_rng(self.seed)
        if record: self._record("Init", "Initial state; q0 is the least significant register bit.")
        for idx, op in enumerate(self.operations, 1):
            applied = not op.when or build_classical_predicate(op.when)(self.classical_bits)
            before = self.state.copy()
            measurement, comparison = None, None
            if applied:
                if op.kind == "gate":
                    validate_gate(op.gate, op.targets, op.parameters, self.num_qubits)
                    for primitive in decompose_gate(op):
                        self.state = primitive_action(self.state, primitive, self.num_qubits)
                elif op.kind in {"superpose", "phase", "flip", "reflect"}:
                    self.state = primitive_action(self.state, op, self.num_qubits)
                elif op.kind == "measure":
                    measurement = self._apply_measure(op)
                    self.measurements[idx] = measurement
                elif op.kind not in {"analog", "align", "branch", "rotate", "wait", "shiftphase", "setfreq", "play", "acquire"}:
                    raise ValueError(f"Unsupported simulation operation: {op.kind}")
            if self.compare and record and op.kind in {"gate", "superpose", "phase", "flip", "reflect"}:
                theory = reference_action(before, op, self.num_qubits) if applied else before
                comparison = gate_comparison(op) if op.kind == "gate" else {}
                comparison.update(state_error=float(np.max(np.abs(theory - self.state))), applied=applied)
            if not np.isclose(np.linalg.norm(self.state), 1, rtol=0, atol=1e-9):
                raise ValueError(f"State lost normalization after {op.raw or op.kind}")
            if record:
                label = f"{idx}. {op.gate or op.kind}" + (" (skipped)" if not applied else "")
                self._record(label, op.raw or op.kind, measurement, op, comparison)
        return self.snapshots

    def _record(self, label, detail, measurement=None, operation=None, comparison=None):
        self.snapshots.append(StepSnapshot(label, detail, self.state.copy(), measurement,
                                           dict(self.classical_bits), operation, comparison))

    def _apply_measure(self, op):
        probabilities = np.abs(self.state) ** 2
        if op.measure_all:
            result = int(self.rng.choice(len(self.state), p=probabilities / probabilities.sum()))
            bitstring = format(result, f"0{self.num_qubits}b")
            distribution = {format(i, f"0{self.num_qubits}b"): float(p) for i, p in enumerate(probabilities)}
            # Keep the sampled amplitude's phase when normalizing the projector.
            amp = self.state[result]
            self.state[:] = 0
            self.state[result] = amp / abs(amp)
            measurement = {"type": "register", "bitstring": bitstring, "distribution": distribution}
        else:
            q = op.targets[0]
            if not 0 <= q < self.num_qubits: raise ValueError("Measurement target outside register")
            selector = (np.arange(len(self.state)) >> q) & 1
            p0 = float(np.clip(probabilities[selector == 0].sum() / probabilities.sum(), 0, 1))
            result = int(self.rng.random() >= p0)
            self.state[selector != result] = 0
            self.state /= np.linalg.norm(self.state)
            measurement = {"type": "qubit", "qubit": q, "result": result, "p0": p0, "p1": 1-p0}
        if op.classical_target: self.classical_bits[op.classical_target] = result
        return measurement

    def _probabilities(self):
        return {format(i, f"0{self.num_qubits}b"): float(abs(a)**2) for i, a in enumerate(self.state)}

    def _index_to_bits(self, idx):
        return [(idx >> q) & 1 for q in range(self.num_qubits)]


def sample_shots(num_qubits, operations, shots, seed=None, initial_state=None):
    """Rerun the full circuit per shot, preserving mid-circuit feed-forward."""
    if shots < 0: raise ValueError("shots must be nonnegative")
    rng = np.random.default_rng(seed)
    final, measured = Counter(), {}
    for _ in range(shots):
        sim = QuantumSimulator(num_qubits, operations, seed=int(rng.integers(2**63)), initial_state=initial_state, compare=False)
        sim.run(record=False)
        for step, event in sim.measurements.items():
            outcome = event.get("bitstring", str(event.get("result")))
            measured.setdefault(step, Counter())[outcome] += 1
        probs = np.abs(sim.state)**2
        final[format(int(rng.choice(len(probs), p=probs/probs.sum())), f"0{num_qubits}b")] += 1
    return {"shots": shots, "final": dict(final), "measurements": {step: dict(counts) for step, counts in measured.items()}}


def circuit_unitary(num_qubits, operations, primitives=False):
    """Dense reference for small unitary circuits; measurement has no unitary."""
    if num_qubits > 8: raise ValueError("Dense circuit matrices are limited to 8 qubits")
    if any(op.when or op.kind not in {"gate", "superpose", "phase", "flip", "reflect"} for op in operations):
        raise ValueError("Measurement, classical guards, and pulses do not define a circuit unitary")
    matrix = np.eye(2**num_qubits, dtype=complex)
    for op in operations:
        if primitives:
            for item in (decompose_gate(op) if op.kind == "gate" else [op]):
                matrix = np.column_stack([primitive_action(col, item, num_qubits) for col in matrix.T])
        else:
            matrix = np.column_stack([reference_action(col, op, num_qubits) for col in matrix.T])
    return matrix
