import math
import unittest
from pathlib import Path

from psi_lang import PsiOperation, QScriptParser
from quantum_gates import GATES

try:
    import numpy as np
    from quantum_simulator import (QuantumSimulator, apply_matrix, bloch_vector, circuit_unitary,
                                   gate_comparison, pair_diagnostics, reduced_density_matrix, sample_shots)
except ImportError:
    np = None


@unittest.skipIf(np is None, "Optional viewer dependencies: install requirements-viewer.txt")
class TestQuantumSimulator(unittest.TestCase):
    def gate(self, name, targets, parameters=(), **kwargs):
        return PsiOperation("gate", "q", targets, gate=name, parameters=list(parameters), **kwargs)

    def test_all_gates_on_nonadjacent_reversed_wires_and_random_state(self):
        rng = np.random.default_rng(912)
        initial = rng.normal(size=16) + 1j*rng.normal(size=16)
        initial /= np.linalg.norm(initial)
        for name, spec in GATES.items():
            targets = [3, 0, 2][:spec.qubits]
            params = [0.34*(i+1) for i in range(len(spec.parameters))]
            with self.subTest(gate=name):
                op = self.gate(name, targets, params)
                sim = QuantumSimulator(4, [op], initial_state=initial)
                snapshots = sim.run()
                self.assertLess(snapshots[-1].comparison["state_error"], 1e-10)
                self.assertLess(snapshots[-1].comparison["operator_error"], 1e-10)
                sim2 = QuantumSimulator(4, [op, self.gate(name, targets, params, inverse=True)], initial_state=initial)
                sim2.run()
                np.testing.assert_allclose(sim2.state, initial, atol=1e-10)

    def test_bell_joint_and_reduced_density(self):
        sim = QuantumSimulator(2, [self.gate("H", [0]), self.gate("CX", [0, 1])])
        sim.run()
        np.testing.assert_allclose(sim.state, [1/math.sqrt(2), 0, 0, 1/math.sqrt(2)], atol=1e-12)
        for q in (0, 1):
            rho = reduced_density_matrix(sim.state, [q], 2)
            np.testing.assert_allclose(rho, np.eye(2)/2, atol=1e-12)
            np.testing.assert_allclose(bloch_vector(rho), [0, 0, 0], atol=1e-12)
        diag = pair_diagnostics(sim.state, [0, 1], 2)
        self.assertAlmostEqual(diag["concurrence"], 1, places=6)
        self.assertAlmostEqual(diag["purity"], 1)
        np.testing.assert_allclose(diag["correlations"], np.diag([1, -1, 1]), atol=1e-12)
        self.assertAlmostEqual(diag["mutual_information"], 2)

    def test_ghz_pair_is_classically_correlated_without_pair_entanglement(self):
        ops = [self.gate("H", [0]), self.gate("CX", [0, 1]), self.gate("CX", [0, 2])]
        sim = QuantumSimulator(3, ops)
        sim.run()
        diag = pair_diagnostics(sim.state, [0, 2], 3)
        self.assertAlmostEqual(diag["concurrence"], 0)
        self.assertAlmostEqual(diag["purity"], 0.5)
        self.assertAlmostEqual(diag["mutual_information"], 1)

    def test_partial_measurement_snapshot_isolation_and_correction(self):
        ops = [self.gate("H", [0]), self.gate("CX", [0, 1]),
               PsiOperation("measure", "q", [0], classical_target="c"),
               self.gate("X", [1], when="c == 1")]
        sim = QuantumSimulator(2, ops, seed=5)
        snapshots = sim.run()
        np.testing.assert_allclose(abs(snapshots[2].amplitudes)**2, [0.5, 0, 0, 0.5], atol=1e-12)
        self.assertEqual(snapshots[2].classical_bits, {})
        self.assertAlmostEqual(snapshots[3].measurement["p0"], 0.5)
        rho = reduced_density_matrix(sim.state, [1], 2)
        np.testing.assert_allclose(rho, [[1, 0], [0, 0]], atol=1e-12)
        self.assertAlmostEqual(np.linalg.norm(sim.state), 1)
        again = sim.run()
        self.assertEqual(len(again), len(ops)+1)
        np.testing.assert_allclose(again[-1].amplitudes, snapshots[-1].amplitudes)
        self.assertEqual(snapshots[2].classical_bits, {})

    def test_shots_replay_mid_circuit_feed_forward(self):
        ops = [self.gate("H", [0]), self.gate("CX", [0, 1]),
               PsiOperation("measure", "q", [0], classical_target="c"),
               self.gate("X", [1], when="c == 1"), PsiOperation("measure", "q", measure_all=True)]
        histogram = sample_shots(2, ops, 200, seed=123)
        self.assertEqual(sum(histogram["final"].values()), 200)
        self.assertEqual(set(histogram["final"]), {"00", "01"})
        self.assertEqual(set(histogram["measurements"][3]), {"0", "1"})
        self.assertEqual(histogram, sample_shots(2, ops, 200, seed=123))

    def test_xx_entangles_and_xy_preserves_excitations(self):
        sim = QuantumSimulator(2, [self.gate("RXX", [0, 1], [math.pi/2])])
        sim.run()
        np.testing.assert_allclose(sim.state, [1/math.sqrt(2), 0, 0, -1j/math.sqrt(2)], atol=1e-12)
        sim = QuantumSimulator(2, [self.gate("RXY", [0, 1], [math.pi/2])], initial_state="01")
        sim.run()
        self.assertAlmostEqual(abs(sim.state[1])**2, 0.5)
        self.assertAlmostEqual(abs(sim.state[2])**2, 0.5)
        self.assertAlmostEqual(abs(sim.state[0])+abs(sim.state[3]), 0)

    def test_global_phase_matches_reference_without_changing_probability(self):
        sim = QuantumSimulator(1, [PsiOperation("phase", "q", angle=0.3)])
        sim.run()
        np.testing.assert_allclose(sim.state, [np.exp(0.3j), 0])

    def test_target_dependent_flip_rejected(self):
        with self.assertRaisesRegex(ValueError, "invariant"):
            QuantumSimulator(1, [PsiOperation("flip", "q", [0], predicate="q[0] == 0")]).run()

    def test_reduced_y_sign_and_qubit_order(self):
        state = np.array([1, 1j])/math.sqrt(2)
        np.testing.assert_allclose(bloch_vector(reduced_density_matrix(state, [0], 1)), [0, 1, 0], atol=1e-12)
        state = np.array([0, 1, 0, 0], dtype=complex)
        self.assertEqual(np.argmax(np.diag(reduced_density_matrix(state, [0, 1], 2))), 2)
        self.assertEqual(np.argmax(np.diag(reduced_density_matrix(state, [1, 0], 2))), 1)

    def test_bv_example_algorithm_and_unitary_boundary(self):
        path = Path(__file__).resolve().parents[1] / "qscripts/bernstein_vazirani.psi"
        _, ops = QScriptParser(str(path)).parse()
        sim = QuantumSimulator(3, ops, seed=1)
        sim.run()
        self.assertAlmostEqual(abs(sim.state[5]), 1)
        unitary = circuit_unitary(3, ops[:-1])
        np.testing.assert_allclose(unitary.conj().T @ unitary, np.eye(8), atol=1e-12)
        with self.assertRaises(ValueError): circuit_unitary(3, ops)

    def test_measurement_preserves_projected_phase(self):
        sim = QuantumSimulator(1, [PsiOperation("measure", "q", measure_all=True)], initial_state=[1j, 0])
        sim.run()
        np.testing.assert_allclose(sim.state, [1j, 0])

    def test_qft_matches_full_dft_matrix_and_bell_circuits_agree(self):
        root = Path(__file__).resolve().parents[1] / "qscripts"
        _, ops = QScriptParser(str(root / "qft_3.psi")).parse()
        j, k = np.meshgrid(np.arange(8), np.arange(8), indexing="ij")
        expected = np.exp(2j*np.pi*j*k/8)/np.sqrt(8)
        np.testing.assert_allclose(circuit_unitary(3, ops), expected, atol=1e-12)
        np.testing.assert_allclose(circuit_unitary(3, ops, primitives=True), expected, atol=1e-12)
        _, named = QScriptParser(str(root / "bell_unitary.psi")).parse()
        _, primitives = QScriptParser(str(root / "bell_primitives.psi")).parse()
        np.testing.assert_allclose(circuit_unitary(2, named), circuit_unitary(2, primitives), atol=1e-12)


if __name__ == "__main__":
    unittest.main()
