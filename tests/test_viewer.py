"""Headless rendering and real control-callback regression coverage."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from quantum_simulator import QuantumSimulator
    from psi_lang import QScriptParser
except ImportError:
    matplotlib = None


@unittest.skipIf(matplotlib is None, "Optional viewer dependencies: install requirements-viewer.txt")
class TestViewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("interference_viewer", root / "viewer-references/psi_interference_viewer.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.root = root

    def circuit(self, name):
        registers, ops = QScriptParser(str(self.root / "qscripts" / name)).parse()
        n = next(iter(registers.values()))
        sim = QuantumSimulator(n, ops, seed=1)
        return {"name": name, "num_qubits": n, "snapshots": sim.run()}

    def test_render_gates_collapse_modes_pairs_and_circuit_switch(self):
        a, b = self.circuit("interactions.psi"), self.circuit("ghz.psi")
        viewer = self.module.InterferenceViewer(a["snapshots"], a["num_qubits"], circuits=[a, b])
        self.addCleanup(plt.close, viewer.fig)
        viewer.slider.set_val(1)
        self.assertEqual(viewer.index, 1)
        self.assertIn("Theory Re", viewer.matrix_ref_ax.get_title())
        viewer._cycle_matrix()
        self.assertIn("Theory Im", viewer.matrix_ref_ax.get_title())
        viewer._cycle_mode()
        self.assertEqual(viewer.mode, "Real amplitude")
        viewer._cycle_mode()
        self.assertEqual(viewer.mode, "Imaginary amplitude")
        viewer.slider.set_val(5)
        self.assertIn("sampled", viewer.measure_ax.get_title())
        self.assertIn("Projector", viewer.matrix_ref_ax.get_title())
        viewer._cycle_circuit()
        self.assertEqual(viewer.num_qubits, 3)
        viewer._cycle_pair()
        self.assertEqual(viewer.qubits, [0, 2])
        viewer._bump(1)
        self.assertLess(viewer.index, len(viewer.snapshots))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "view.png"
            viewer.fig.savefig(output)
            self.assertGreater(output.stat().st_size, 10000)

    def test_one_qubit_initial_and_pulse_steps_render(self):
        pulse = self.circuit("ghost_filter.psi")
        viewer = self.module.InterferenceViewer(pulse["snapshots"], pulse["num_qubits"])
        self.addCleanup(plt.close, viewer.fig)
        viewer._draw_snapshot(2)
        viewer._cycle_pair()
        self.assertEqual(viewer.qubits, [0])
        empty = QuantumSimulator(1, []).run()
        viewer = self.module.InterferenceViewer(empty, 1)
        self.addCleanup(plt.close, viewer.fig)
        viewer._bump(1)
        self.assertEqual(viewer.index, 0)

@unittest.skipIf(matplotlib is None, 'Optional viewer dependencies unavailable')
class TestWaveLens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root/'viewer-references'))
        import wave_interaction_viewer
        cls.wave = wave_interaction_viewer

    def test_mode_density_normalization_and_entangled_nonseparability(self):
        import numpy as np
        coordinates = np.linspace(-6, 6, 241)
        state = np.array([1, 0, 0, -1j])/np.sqrt(2)
        x, y, wave, density = self.wave.wave_field(state, [1,0], 2, coordinates)
        np.testing.assert_allclose(abs(wave)**2, density, atol=1e-12)
        spacing = coordinates[1]-coordinates[0]
        self.assertAlmostEqual(density.sum()*spacing**2, 1, places=9)
        singular = np.linalg.svd(wave, compute_uv=False)
        self.assertGreater(singular[1], .1)
        # A pair reduced from GHZ is mixed and must not get a fabricated wave.
        ghz = np.zeros(8, complex)
        ghz[0] = ghz[7] = 1/np.sqrt(2)
        self.assertIsNone(self.wave.wave_field(ghz, [0,1], 3, coordinates)[2])

    def test_unitary_interpolation_and_measurement_jump(self):
        import numpy as np
        from psi_lang import PsiOperation
        from quantum_simulator import QuantumSimulator
        op = PsiOperation('gate','q',[0,1],gate='RXX',parameters=[np.pi/2])
        before = np.array([1,0,0,0],complex)
        sim = QuantumSimulator(2,[op])
        sim.run()
        for t in (0,.25,.5,.75,1):
            state = self.wave.gate_state(before,sim.state,op,2,t,{})
            self.assertAlmostEqual(np.linalg.norm(state),1)
        np.testing.assert_allclose(self.wave.gate_state(before,sim.state,op,2,1,{}),sim.state)
        m = PsiOperation('measure','q',measure_all=True)
        np.testing.assert_allclose(self.wave.gate_state(before,sim.state,m,2,.9,{}),before)

    def test_wave_controls_render(self):
        import numpy as np
        from psi_lang import PsiOperation
        from quantum_simulator import QuantumSimulator
        snapshots = QuantumSimulator(2,[PsiOperation('gate','q',[0,1],gate='RXX',parameters=[np.pi/2])]).run()
        viewer = self.wave.WaveInteractionViewer(snapshots,2)
        self.addCleanup(plt.close,viewer.fig)
        viewer.slider.set_val(1)
        viewer.progress.set_val(.4)
        viewer._mode()
        viewer._mode()
        viewer._circuit()
        self.assertEqual(viewer.mode,'Imaginary')


if __name__ == "__main__":
    unittest.main()
