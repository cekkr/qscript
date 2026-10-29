import tempfile
import unittest
from pathlib import Path

from psi_lang import QScriptParser, build_classical_predicate, build_quantum_predicate
from quantum_gates import GATES


def _write_tmp_script(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".psi")
    tmp.write(content.encode("utf-8"))
    tmp.flush()
    return Path(tmp.name)


class TestAnalogParsing(unittest.TestCase):
    def test_analog_targets_propagate(self):
        script = """
        let q = Register(2);
        Analog(target: q[1]) {
            Rotate(axis: X, angle: PI/2, duration: 20ns);
            Wait(duration: 5ns);
            ShiftPhase(angle: PI/4);
            SetFreq(hz: 5.1e9);
            Play(waveform: Gaussian(amp: 0.2), channel: d0);
            Acquire(duration: 100ns, kernel: boxcar);
        }
        """
        path = _write_tmp_script(script)
        registers, ops = QScriptParser(str(path)).parse()

        self.assertEqual(registers, {"q": 2})
        self.assertEqual([op.kind for op in ops], ["analog", "rotate", "wait", "shiftphase", "setfreq", "play", "acquire"])
        self.assertEqual(ops[0].targets, [1])  # Analog target
        self.assertEqual(ops[1].targets, [1])  # Rotate inherits Analog target
        self.assertEqual(ops[2].targets, [1])  # Wait inherits Analog target
        self.assertEqual(ops[3].targets, [1])  # ShiftPhase inherits Analog target
        self.assertEqual(ops[4].targets, [1])  # SetFreq inherits Analog target
        self.assertEqual(ops[5].register, "q")
        self.assertEqual(ops[6].register, "q")

    def test_align_and_branch_targets(self):
        script = """
        let q = Register(2);
        Align {
            branch q[0] { Rotate(axis: Z, angle: PI, duration: 10ns); }
            branch q[1] { Wait(duration: 10ns); }
        }
        """
        path = _write_tmp_script(script)
        registers, ops = QScriptParser(str(path)).parse()

        self.assertEqual(registers, {"q": 2})
        self.assertEqual([op.kind for op in ops], ["align", "branch", "rotate", "branch", "wait"])
        self.assertEqual(ops[1].targets, [0])  # branch q[0]
        self.assertEqual(ops[2].targets, [0])  # Rotate in branch retains target
        self.assertEqual(ops[3].targets, [1])  # branch q[1]
        self.assertEqual(ops[4].targets, [1])  # Wait in branch retains target


class TestLogicParsing(unittest.TestCase):
    def parse(self, content):
        path = _write_tmp_script(content)
        self.addCleanup(path.unlink)
        return QScriptParser(str(path)).parse()

    def test_every_gate_roundtrips_parameters(self):
        for name, spec in GATES.items():
            params = ", ".join(f"{key}: PI/{i+2}" for i, key in enumerate(spec.parameters))
            targets = ", ".join(str(i) for i in range(spec.qubits))
            text = f"let q = Register(3); q.Gate(name: {name}, targets: [{targets}]" + (", " + params if params else "") + ", inverse: true);"
            with self.subTest(gate=name):
                _, ops = self.parse(text)
                self.assertEqual(ops[0].gate, name)
                self.assertEqual(len(ops[0].parameters), len(spec.parameters))
                self.assertTrue(ops[0].inverse)

    def test_multiline_and_direct_methods_preserve_primitive_phase(self):
        _, ops = self.parse("""let q = Register(2);
        q.Gate(name: U, target: 0,
               params: [PI/2, 0, PI]); // continuation
        q.Interact(axes: XY, targets: [1, 0], angle: PI/2);
        q.Turn(axis: Y, target: 1, angle: PI/3);
        q.CNOT(targets: [0, 1]);
        q.Phase(angle: PI,
                where: (q[0] && !q[1]) || (!q[0] && q[1]));
        """)
        self.assertEqual([op.gate for op in ops[:4]], ["U", "RXY", "RY", "CX"])
        self.assertEqual(ops[4].kind, "phase")

    def test_measurement_forms_and_guards(self):
        _, ops = self.parse("""let q = Register(2);
        let c = Measure(q[1]);
        let all = Measure(q, when: c == 1);
        let other = q.Measure(target: 0, when: c == 0);
        q.Measure();""")
        self.assertEqual(ops[0].targets, [1])
        self.assertTrue(ops[1].measure_all)
        self.assertEqual(ops[1].when, "c == 1")
        self.assertEqual(ops[2].targets, [0])
        self.assertTrue(ops[3].measure_all)

    def test_invalid_gates_fail_instead_of_disappearing(self):
        calls = ["q.Gate(name: Missing, target: 0)", "q.CX(targets: [0,0])", "q.RX(target: 3, angle: 0)",
                 "q.RY(target: 0)", "q.Interact(axes: QZ, targets: [0,1], angle: PI)",
                 "q.H(target: 0, typo: 1)", "q.H(target: 0, where: q[1])", "q.Turn(axis: X, target: 0, angle: 1e999)",
                 "q.H(target: 0, inverse: maybe)", "q.Phase(angle: 0, where: other[0])",
                 "q.Turn(axis: -X, target: 0, angle: PI)", "q.Interact(axes: X, target: 0, angle: PI)",
                 "q.Phase(angle: 0, where: q[9])", "q.Gate(name: U, target: 0, params: [0,1])"]
        for call in calls:
            with self.subTest(call=call), self.assertRaises(ValueError): self.parse("let q = Register(2); " + call)
        for text in ("q.H(target: 0", "q.H(target: 0))", "Align { q.H(target: 0)", "}"):
            with self.subTest(text=text), self.assertRaises(ValueError): self.parse("let q = Register(2); " + text)

    def test_logic_does_not_become_a_pulse(self):
        with self.assertRaises(ValueError):
            self.parse("let q = Register(2); Analog(target: q[0]) { q.Interact(axes: XX, targets: [0,1], angle: PI); }")

    def test_boolean_negation_and_not_equal(self):
        self.assertTrue(build_quantum_predicate("!q[0] && q[1] != 0")([0, 1]))
        self.assertTrue(build_classical_predicate("true && c != 0")({"c": 1}))
        self.assertFalse(build_classical_predicate("false || c == 0")({"c": 1}))
        self.assertTrue(build_classical_predicate("untrue == 1")({"untrue": 1}))

    def test_multiline_algorithm_examples_parse(self):
        root = Path(__file__).resolve().parents[1]
        for name in ("grover_sat.psi", "bernstein_vazirani.psi"):
            _, ops = QScriptParser(str(root / "qscripts" / name)).parse()
            self.assertTrue(any(op.kind == "phase" and op.predicate for op in ops))


if __name__ == "__main__":
    unittest.main()
