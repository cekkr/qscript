"""
PsiScript -> OpenQASM 2.0 sketch compiler + pulse scheduler.

This is intentionally minimal: it lowers the common PsiScript samples into
qelib1 gates, emits comments when a predicate is too complex to lower, and
keeps classical guards (`when:`) as OpenQASM `if` statements. Pulse-layer
sections are converted into a timestamped schedule that can be simulated
through a pluggable backend interface.

PsiScript v1.2 adds an Analog/pulse layer. Those operations are parsed but not
lowered here; they are emitted as comments to preserve intent in the output.

Run (from repo root):
    python compiler/qasm_compiler.py psiscripts/teleport.psi --out build/teleport.qasm
    python compiler/qasm_compiler.py psiscripts/ghost_filter.psi --pulse-table
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psi_lang import PsiOperation, PsiScriptParser, parse_conjunctive_controls


PULSE_KINDS = {"rotate", "wait", "shiftphase", "setfreq", "play", "acquire"}


@dataclass
class PulseEvent:
    kind: str
    register: str
    target: Optional[int]
    start_ns: float
    duration_ns: float
    axis: Optional[str] = None
    angle: Optional[float] = None
    shape: Optional[str] = None
    waveform: Optional[str] = None
    channel: Optional[str] = None
    frequency: Optional[str] = None
    kernel: Optional[str] = None
    when: Optional[str] = None
    branch: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    raw: str = ""


@dataclass
class PulseSchedule:
    events: List[PulseEvent] = field(default_factory=list)

    @property
    def duration_ns(self) -> float:
        if not self.events:
            return 0.0
        return max(evt.start_ns + evt.duration_ns for evt in self.events)

    def to_json(self) -> str:
        return json.dumps([asdict(evt) for evt in self.events], indent=2)

    def to_table(self) -> str:
        if not self.events:
            return "(no pulse events)"
        lines = []
        header = f"{'start(ns)':>10} {'dur(ns)':>8} {'reg':>6} {'tgt':>4} {'kind':>10} details"
        lines.append(header)
        lines.append("-" * len(header))
        for evt in sorted(self.events, key=lambda e: (e.start_ns, e.register, e.target or -1)):
            tgt = "" if evt.target is None else str(evt.target)
            details = []
            if evt.axis:
                details.append(f"axis={evt.axis}")
            if evt.kind in {"rotate", "shiftphase"} and evt.angle is not None:
                details.append(f"angle={evt.angle}")
            if evt.shape:
                details.append(f"shape={evt.shape}")
            if evt.waveform:
                details.append(f"waveform={evt.waveform}")
            if evt.channel:
                details.append(f"channel={evt.channel}")
            if evt.frequency:
                details.append(f"freq={evt.frequency}")
            if evt.kernel:
                details.append(f"kernel={evt.kernel}")
            if evt.branch:
                details.append(f"branch={evt.branch}")
            lines.append(
                f"{evt.start_ns:10.1f} {evt.duration_ns:8.1f} {evt.register:>6} {tgt:>4} {evt.kind:>10} "
                + ", ".join(details)
            )
        lines.append(f"Total duration: {self.duration_ns:.1f} ns")
        return "\n".join(lines)


class PulseScheduler:
    """Build a timestamped pulse schedule by walking parsed PsiScript statements."""

    def __init__(
        self,
        parser: PsiScriptParser,
        registers: Dict[str, int],
        default_register: Optional[str] = None,
        target_register: Optional[str] = None,
    ):
        self.parser = parser
        self.registers = registers
        self.register_filter = target_register
        if target_register and target_register not in registers:
            raise ValueError(f"Register '{target_register}' not declared.")
        self.default_register = default_register or target_register or next(iter(registers.keys()))

    def build(self) -> PulseSchedule:
        statements = getattr(self.parser, "statements", [])
        events, _ = self._compile_block(
            statements=statements,
            default_register=self.default_register,
            scope="logic",
            analog_context=None,
            start_time=0.0,
            branch_label=None,
        )
        events.sort(key=lambda e: (e.start_ns, e.register, e.target or -1))
        return PulseSchedule(events)

    # --- internal helpers ---

    def _compile_block(
        self,
        *,
        statements: List[object],
        default_register: Optional[str],
        scope: str,
        analog_context: Optional[Tuple[Optional[str], Optional[int]]],
        start_time: float,
        branch_label: Optional[str],
    ) -> Tuple[List[PulseEvent], float]:
        time_cursor = start_time
        events: List[PulseEvent] = []

        for stmt in statements:
            op, ctx_update = self.parser._parse_operation(
                stmt.text,
                scope=scope,
                analog_context=analog_context,
                default_register=default_register,
            )
            next_default = ctx_update.get("default_register", default_register)
            next_scope = ctx_update.get("scope", scope)
            next_analog = ctx_update.get("analog_context", analog_context)

            if op and op.kind in PULSE_KINDS:
                evt, delta = self._lower_pulse_op(op, time_cursor, branch_label)
                if evt:
                    events.append(evt)
                time_cursor += delta
                continue

            if op and op.kind == "analog":
                child_events, duration = self._compile_block(
                    statements=stmt.children,
                    default_register=next_default,
                    scope=next_scope,
                    analog_context=next_analog,
                    start_time=time_cursor,
                    branch_label=branch_label,
                )
                events.extend(child_events)
                time_cursor += duration
                continue

            if op and op.kind == "align":
                child_events, duration = self._compile_align(
                    branches=stmt.children,
                    default_register=next_default,
                    scope=next_scope,
                    analog_context=next_analog,
                    start_time=time_cursor,
                )
                events.extend(child_events)
                time_cursor += duration
                continue

            if stmt.children:
                child_events, duration = self._compile_block(
                    statements=stmt.children,
                    default_register=next_default,
                    scope=next_scope,
                    analog_context=next_analog,
                    start_time=time_cursor,
                    branch_label=branch_label,
                )
                events.extend(child_events)
                time_cursor += duration

        return events, time_cursor - start_time

    def _compile_align(
        self,
        *,
        branches: List[object],
        default_register: Optional[str],
        scope: str,
        analog_context: Optional[Tuple[Optional[str], Optional[int]]],
        start_time: float,
    ) -> Tuple[List[PulseEvent], float]:
        events: List[PulseEvent] = []
        durations: List[float] = []

        for branch_stmt in branches:
            op, ctx_update = self.parser._parse_operation(
                branch_stmt.text,
                scope=scope,
                analog_context=analog_context,
                default_register=default_register,
            )
            branch_label = op.metadata.get("label") if op and op.metadata else None
            child_events, duration = self._compile_block(
                statements=branch_stmt.children,
                default_register=ctx_update.get("default_register", default_register),
                scope=ctx_update.get("scope", scope),
                analog_context=ctx_update.get("analog_context", analog_context),
                start_time=start_time,
                branch_label=branch_label,
            )
            events.extend(child_events)
            durations.append(duration)

        return events, max(durations) if durations else 0.0

    def _lower_pulse_op(
        self, op: PsiOperation, start: float, branch_label: Optional[str]
    ) -> Tuple[Optional[PulseEvent], float]:
        target = op.targets[0] if op.targets else None
        duration = self._parse_duration(op.duration or op.metadata.get("duration"))
        include_event = not self.register_filter or op.register == self.register_filter
        if not include_event:
            return None, duration

        event = PulseEvent(
            kind=op.kind,
            register=op.register,
            target=target,
            start_ns=start,
            duration_ns=duration,
            axis=op.axis,
            angle=op.angle if hasattr(op, "angle") else None,
            shape=op.shape,
            waveform=op.waveform,
            channel=op.channel,
            frequency=op.frequency,
            kernel=op.kernel,
            when=op.when,
            branch=branch_label,
            metadata=op.metadata,
            raw=op.raw,
        )
        return event, duration

    def _parse_duration(self, text: Optional[str]) -> float:
        if not text:
            return 0.0
        value, unit = self._split_number_unit(text)
        factor = {
            "s": 1e9,
            "ms": 1e6,
            "us": 1e3,
            "ns": 1.0,
            "ps": 1e-3,
            "fs": 1e-6,
            "dt": 1.0,  # treat dt as an abstract tick
        }.get(unit, 1.0)
        return value * factor

    def _split_number_unit(self, text: str) -> Tuple[float, str]:
        cleaned = text.strip()
        match = re.match(r"([-+]?\d*\.?\d+(?:e[-+]?\d+)?)\s*([a-zA-Z]+)?", cleaned)
        if not match:
            return 0.0, "ns"
        value = float(match.group(1))
        unit = (match.group(2) or "ns").lower()
        return value, unit


# Backwards-compat alias for previous standalone module
PulseLayerCompiler = PulseScheduler


class PulseBackend:
    """Lightweight abstraction so different simulators/backends can be plugged in."""

    def on_start(self, schedule: PulseSchedule):
        return None

    def on_event(self, event: PulseEvent):
        return None

    def on_finish(self, schedule: PulseSchedule):
        return None


class LoggingPulseBackend(PulseBackend):
    """Collects events for inspection or downstream integration."""

    def __init__(self):
        self.events: List[PulseEvent] = []
        self.started = False
        self.finished = False

    def on_start(self, schedule: PulseSchedule):
        self.started = True
        self.finished = False

    def on_event(self, event: PulseEvent):
        self.events.append(event)

    def on_finish(self, schedule: PulseSchedule):
        self.finished = True
        return {
            "event_count": len(self.events),
            "duration_ns": schedule.duration_ns,
        }


class PulseSimulator:
    """Replay a pulse schedule into a backend (could be a hardware API or physics simulator)."""

    def __init__(self, backend: PulseBackend):
        self.backend = backend

    def run(self, schedule: PulseSchedule):
        self.backend.on_start(schedule)
        for event in sorted(schedule.events, key=lambda e: (e.start_ns, e.register, e.target or -1)):
            self.backend.on_event(event)
        return self.backend.on_finish(schedule)


class QasmBuilder:
    def __init__(self, register: str, num_qubits: int):
        self.reg = register
        self.n = num_qubits
        self.op_lines: List[str] = []
        self.cregs: Dict[str, int] = {}
        self.qregs: Dict[str, int] = {self.reg: self.n}
        self.tmp_counter = 0

    def ensure_creg(self, name: str, size: int):
        if name in self.cregs:
            return
        self.cregs[name] = size

    def tmp_creg(self, size: int) -> str:
        name = f"tmp{self.tmp_counter}"
        self.tmp_counter += 1
        self.ensure_creg(name, size)
        return name

    def emit(self, text: str):
        self.op_lines.append(text)

    def ensure_qreg(self, name: str, size: int):
        if name in self.qregs:
            self.qregs[name] = max(self.qregs[name], size)
            return
        self.qregs[name] = size

    def render(self) -> str:
        header = ["OPENQASM 2.0;", 'include "qelib1.inc";']
        qreg_lines = [f"qreg {name}[{size}];" for name, size in self.qregs.items()]
        creg_lines = [f"creg {name}[{size}];" for name, size in self.cregs.items()]
        return "\n".join(header + qreg_lines + creg_lines + self.op_lines) + "\n"


class OpenQasmCompiler:
    """Very small translator for PsiScript primitives into OpenQASM 2 gates."""

    def __init__(self, register: str, num_qubits: int):
        self.register = register
        self.num_qubits = num_qubits
        self.builder = QasmBuilder(register, num_qubits)

    def compile(self, operations: List[PsiOperation]) -> str:
        for op in operations:
            handler = getattr(self, f"_emit_{op.kind}", None)
            if handler:
                handler(op)
            else:
                self.builder.emit(f"// TODO: unsupported op {op.kind}: {op.raw}")
        return self.builder.render()

    # --- Emitters ---

    def _emit_superpose(self, op: PsiOperation):
        targets = range(self.num_qubits) if op.targets == ["ALL"] else op.targets
        for q in targets:
            self.builder.emit(f"h {self.register}[{q}];")

    def _emit_phase(self, op: PsiOperation):
        controls = parse_conjunctive_controls(op.predicate or "", op.register)
        if controls is None:
            self.builder.emit(f"// TODO: Phase {op.angle} where {op.predicate} (non-conjunctive predicate)")
            return
        if not controls:
            # Global phase on |1> states of qubit 0 (single-qubit diag)
            self._emit_with_when([f"u1({op.angle}) {self.register}[0]; // global phase marker"], op.when)
            return

        if len(controls) == 1:
            idx, val = controls[0]
            prefix = []
            suffix = []
            if val == 0:
                prefix.append(f"x {self.register}[{idx}];")
                suffix.append(f"x {self.register}[{idx}];")
            self._emit_with_when(prefix + [f"u1({op.angle}) {self.register}[{idx}];"] + suffix, op.when)
            return

        if len(controls) == 2:
            # Use cu1 for 2-control case (one control, one target), best-effort.
            (c_idx, c_val), (t_idx, t_val) = controls
            pre, post = [], []
            if c_val == 0:
                pre.append(f"x {self.register}[{c_idx}];")
                post.append(f"x {self.register}[{c_idx}];")
            if t_val == 0:
                pre.append(f"x {self.register}[{t_idx}];")
                post.append(f"x {self.register}[{t_idx}];")
            body = [f"cu1({op.angle}) {self.register}[{c_idx}],{self.register}[{t_idx}];"]
            self._emit_with_when(pre + body + post, op.when)
            return

        self.builder.emit(f"// TODO: multi-control phase for predicate '{op.predicate}' not lowered")

    def _emit_flip(self, op: PsiOperation):
        controls = parse_conjunctive_controls(op.predicate or "", op.register)
        target = op.targets[0]
        if controls is None:
            self.builder.emit(f"// TODO: Flip target {target} where {op.predicate} (non-conjunctive predicate)")
            return
        if not controls:
            self._emit_with_when([f"x {self.register}[{target}];"], op.when)
            return

        if len(controls) == 1:
            c_idx, val = controls[0]
            pre, post = [], []
            if val == 0:
                pre.append(f"x {self.register}[{c_idx}];")
                post.append(f"x {self.register}[{c_idx}];")
            self._emit_with_when(pre + [f"cx {self.register}[{c_idx}],{self.register}[{target}];"] + post, op.when)
            return

        if len(controls) == 2:
            (c1, v1), (c2, v2) = controls
            pre, post = [], []
            if v1 == 0:
                pre.append(f"x {self.register}[{c1}];")
                post.append(f"x {self.register}[{c1}];")
            if v2 == 0:
                pre.append(f"x {self.register}[{c2}];")
                post.append(f"x {self.register}[{c2}];")
            self._emit_with_when(pre + [f"ccx {self.register}[{c1}],{self.register}[{c2}],{self.register}[{target}];"] + post, op.when)
            return

        self.builder.emit(f"// TODO: multi-control flip for predicate '{op.predicate}' not lowered")

    def _emit_reflect(self, op: PsiOperation):
        axis = (op.axis or "").upper()
        if "MEAN" not in axis:
            self.builder.emit(f"// TODO: Reflect axis '{op.axis}' not lowered")
            return

        n = self.num_qubits
        # Grover diffusion: H^n X^n (multi-CZ) X^n H^n
        for q in range(n):
            self.builder.emit(f"h {self.register}[{q}];")
        for q in range(n):
            self.builder.emit(f"x {self.register}[{q}];")

        controls = list(range(n - 1))  # control on all but last qubit
        target = n - 1
        self._emit_multi_control_z(controls, target)

        for q in range(n):
            self.builder.emit(f"x {self.register}[{q}];")
        for q in range(n):
            self.builder.emit(f"h {self.register}[{q}];")

    def _emit_measure(self, op: PsiOperation):
        if op.measure_all:
            dest = op.classical_target or f"meas_{self.register}_{self.builder.tmp_counter}"
            self.builder.ensure_creg(dest, self.num_qubits)
            self.builder.emit(f"measure {self.register} -> {dest};")
            return

        dest = op.classical_target or self.builder.tmp_creg(1)
        if dest not in self.builder.cregs:
            self.builder.ensure_creg(dest, 1)
        self.builder.emit(f"measure {self.register}[{op.targets[0]}] -> {dest}[0];")

    def _emit_analog(self, op: PsiOperation):
        self.builder.emit(f"// Analog scope for {op.register} {op.targets}: {op.raw}")

    def _emit_align(self, op: PsiOperation):
        self.builder.emit(f"// Align block start: {op.raw}")

    def _emit_branch(self, op: PsiOperation):
        label = op.metadata.get("label", "") if hasattr(op, "metadata") else ""
        self.builder.emit(f"// Align branch {label}")

    def _emit_rotate(self, op: PsiOperation):
        self.builder.emit(f"// Rotate (pulse) not lowered: {op.raw}")

    def _emit_wait(self, op: PsiOperation):
        self.builder.emit(f"// Wait (pulse) not lowered: {op.raw}")

    def _emit_shiftphase(self, op: PsiOperation):
        self.builder.emit(f"// ShiftPhase (virtual Z) not lowered: {op.raw}")

    def _emit_setfreq(self, op: PsiOperation):
        self.builder.emit(f"// SetFreq (frame) not lowered: {op.raw}")

    def _emit_play(self, op: PsiOperation):
        self.builder.emit(f"// Play (waveform) not lowered: {op.raw}")

    def _emit_acquire(self, op: PsiOperation):
        self.builder.emit(f"// Acquire (readout) not lowered: {op.raw}")

    # --- helpers ---

    def _emit_with_when(self, gate_lines: List[str], when: Optional[str]):
        if not when:
            for line in gate_lines:
                self.builder.emit(line)
            return

        cond = self._lower_when_condition(when)
        if cond is None:
            self.builder.emit(f"// TODO: when guard '{when}' not lowered")
            for line in gate_lines:
                self.builder.emit(line)
            return

        for line in gate_lines:
            self.builder.emit(f"if ({cond}) {line}")

    def _lower_when_condition(self, expr: str) -> Optional[str]:
        match = re.match(r"(\w+)\s*==\s*1", expr.strip())
        if match:
            name = match.group(1)
            if name not in self.builder.cregs:
                self.builder.ensure_creg(name, 1)
            return f"{name}==1"
        match = re.match(r"(\w+)\s*==\s*0", expr.strip())
        if match:
            name = match.group(1)
            if name not in self.builder.cregs:
                self.builder.ensure_creg(name, 1)
            return f"{name}==0"
        return None

    def _emit_multi_control_z(self, controls: List[int], target: int):
        """
        Best-effort multi-controlled Z using H-target, multi-controlled X, H-target.
        """
        if not controls:
            self.builder.emit(f"z {self.register}[{target}];")
            return

        self.builder.emit(f"h {self.register}[{target}];")
        self._emit_multi_control_x(controls, target)
        self.builder.emit(f"h {self.register}[{target}];")

    def _emit_multi_control_x(self, controls: List[int], target: int):
        """
        Decompose multi-controlled X with an ancilla chain (k-2 ancillas for k>2).
        """
        k = len(controls)
        reg = self.register
        if k == 0:
            self.builder.emit(f"x {reg}[{target}];")
            return
        if k == 1:
            self.builder.emit(f"cx {reg}[{controls[0]}],{reg}[{target}];")
            return
        if k == 2:
            self.builder.emit(f"ccx {reg}[{controls[0]}],{reg}[{controls[1]}],{reg}[{target}];")
            return

        anc_count = k - 2
        anc_name = f"anc_{reg}"
        self.builder.ensure_qreg(anc_name, anc_count)

        # Compute chain
        self.builder.emit(f"ccx {reg}[{controls[0]}],{reg}[{controls[1]}],{anc_name}[0];")
        for i in range(2, k - 1):
            src_anc = i - 2
            dst_anc = i - 1
            self.builder.emit(f"ccx {reg}[{controls[i]}],{anc_name}[{src_anc}],{anc_name}[{dst_anc}];")

        # Final controlled X on target
        self.builder.emit(f"ccx {reg}[{controls[-1]}],{anc_name}[{anc_count - 1}],{reg}[{target}];")

        # Uncompute chain
        for i in reversed(range(2, k - 1)):
            src_anc = i - 2
            dst_anc = i - 1
            self.builder.emit(f"ccx {reg}[{controls[i]}],{anc_name}[{src_anc}],{anc_name}[{dst_anc}];")
        self.builder.emit(f"ccx {reg}[{controls[0]}],{reg}[{controls[1]}],{anc_name}[0];")


def main():
    parser = argparse.ArgumentParser(description="Compile a PsiScript file into OpenQASM 2.0 and a pulse schedule.")
    parser.add_argument("script", help="Path to .psi program to compile")
    parser.add_argument("--register", help="Register name to compile (defaults to first declared)")
    parser.add_argument("--out", type=Path, help="Destination .qasm file (stdout if omitted)")
    parser.add_argument(
        "--pulse-json",
        type=Path,
        help="Write pulse schedule to a JSON file (use '-' to print to stdout).",
    )
    parser.add_argument(
        "--pulse-table",
        action="store_true",
        help="Print a text table of the pulse schedule to stdout.",
    )
    parser.add_argument(
        "--simulate-pulses",
        action="store_true",
        help="Replay the pulse schedule into a logging backend (no physics yet).",
    )
    args = parser.parse_args()

    ps_parser = PsiScriptParser(args.script)
    registers, operations = ps_parser.parse()
    target_register = args.register or next(iter(registers.keys()))
    if target_register not in registers:
        raise SystemExit(f"Register '{target_register}' not declared.")

    filtered_ops = [op for op in operations if op.register == target_register]
    compiler = OpenQasmCompiler(target_register, registers[target_register])
    qasm = compiler.compile(filtered_ops)

    schedule: Optional[PulseSchedule] = None
    wants_pulses = args.pulse_json or args.pulse_table or args.simulate_pulses
    if wants_pulses:
        scheduler = PulseScheduler(
            ps_parser,
            registers,
            default_register=target_register,
            target_register=target_register,
        )
        schedule = scheduler.build()

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(qasm, encoding="utf-8")
        print(f"Wrote OpenQASM to {args.out}")
    else:
        print(qasm)

    if args.pulse_json:
        pulse_text = schedule.to_json() if schedule else "[]"
        if str(args.pulse_json) == "-":
            print(pulse_text)
        else:
            args.pulse_json.parent.mkdir(parents=True, exist_ok=True)
            args.pulse_json.write_text(pulse_text, encoding="utf-8")
            print(f"Wrote pulse schedule to {args.pulse_json}")

    if args.pulse_table:
        print(schedule.to_table() if schedule else "(no pulse events)")

    if args.simulate_pulses:
        backend = LoggingPulseBackend()
        summary = PulseSimulator(backend).run(schedule or PulseSchedule())
        print(f"Pulse simulation complete: {summary}")


if __name__ == "__main__":
    main()
