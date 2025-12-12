import tempfile
import unittest
from pathlib import Path

from psi_lang import PsiScriptParser


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
        registers, ops = PsiScriptParser(str(path)).parse()

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
        registers, ops = PsiScriptParser(str(path)).parse()

        self.assertEqual(registers, {"q": 2})
        self.assertEqual([op.kind for op in ops], ["align", "branch", "rotate", "branch", "wait"])
        self.assertEqual(ops[1].targets, [0])  # branch q[0]
        self.assertEqual(ops[2].targets, [0])  # Rotate in branch retains target
        self.assertEqual(ops[3].targets, [1])  # branch q[1]
        self.assertEqual(ops[4].targets, [1])  # Wait in branch retains target


if __name__ == "__main__":
    unittest.main()
