import tempfile
import unittest
from pathlib import Path

from compiler.pulse_compiler import PulseLayerCompiler


def _write_tmp_script(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".psi")
    tmp.write(content.encode("utf-8"))
    tmp.flush()
    return Path(tmp.name)


class TestPulseCompiler(unittest.TestCase):
    def test_simple_pulse_schedule(self):
        script = """
        let q = Register(1);
        Analog(target: q[0]) {
            Rotate(axis: X, angle: PI/2, duration: 10ns);
            Wait(duration: 5ns);
            ShiftPhase(angle: PI/4);
            Acquire(duration: 20ns, kernel: boxcar);
        }
        """
        path = _write_tmp_script(script)
        schedule = PulseLayerCompiler(str(path)).compile()

        kinds = [evt.kind for evt in schedule.events]
        self.assertEqual(kinds, ["rotate", "wait", "shiftphase", "acquire"])
        self.assertAlmostEqual(schedule.events[0].start_ns, 0.0)
        self.assertAlmostEqual(schedule.events[1].start_ns, 10.0)
        self.assertAlmostEqual(schedule.events[2].start_ns, 15.0)
        self.assertAlmostEqual(schedule.events[3].start_ns, 15.0)
        self.assertAlmostEqual(schedule.events[3].duration_ns, 20.0)
        self.assertAlmostEqual(schedule.duration_ns, 35.0)

    def test_align_branches_share_start(self):
        script = """
        let q = Register(2);
        Align {
            branch q[0] {
                Rotate(axis: Z, angle: PI, duration: 10ns);
            }
            branch q[1] {
                Wait(duration: 25ns);
            }
        }
        """
        path = _write_tmp_script(script)
        schedule = PulseLayerCompiler(str(path)).compile()

        self.assertEqual(len(schedule.events), 2)
        starts = {evt.target: evt.start_ns for evt in schedule.events}
        durations = {evt.target: evt.duration_ns for evt in schedule.events}
        branches = {evt.target: evt.branch for evt in schedule.events}

        self.assertAlmostEqual(starts[0], 0.0)
        self.assertAlmostEqual(starts[1], 0.0)
        self.assertAlmostEqual(durations[0], 10.0)
        self.assertAlmostEqual(durations[1], 25.0)
        self.assertEqual(schedule.duration_ns, 25.0)
        self.assertEqual(branches[0], "q[0]")
        self.assertEqual(branches[1], "q[1]")


if __name__ == "__main__":
    unittest.main()
