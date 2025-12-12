"""
PsiScript pulse-layer compiler.

Builds a simple, timestamped schedule from Analog/Rotate/Wait/ShiftPhase/SetFreq/Play/Acquire
statements so synthesis scripts can be consumed by Python tooling without relying on OpenQASM.
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

from psi_lang import PsiOperation, PsiScriptParser  # noqa: E402


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

    def per_target(self) -> Dict[Tuple[str, Optional[int]], List[PulseEvent]]:
        grouped: Dict[Tuple[str, Optional[int]], List[PulseEvent]] = {}
        for evt in self.events:
            key = (evt.register, evt.target)
            grouped.setdefault(key, []).append(evt)
        for key_events in grouped.values():
            key_events.sort(key=lambda e: e.start_ns)
        return grouped

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


class PulseLayerCompiler:
    """Compile PsiScript pulse-layer statements into a flat, timestamped schedule."""

    def __init__(self, script_path: str, target_register: Optional[str] = None):
        self.script_path = script_path
        self.parser = PsiScriptParser(script_path)
        self.registers, _ = self.parser.parse()
        self.register_filter = target_register
        if target_register and target_register not in self.registers:
            raise ValueError(f"Register '{target_register}' not declared.")
        self.default_register = target_register or next(iter(self.registers.keys()))

    def compile(self) -> PulseSchedule:
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

    # --- Internal walkers ---

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

        base_kwargs = dict(
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

        include_event = not self.register_filter or op.register == self.register_filter
        event = PulseEvent(**base_kwargs) if include_event else None
        return event, duration

    # --- Utilities ---

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
            "dt": 1.0,  # treat dt as a time step for relative alignment
        }.get(unit, 1.0)
        return value * factor

    def _split_number_unit(self, text: str) -> Tuple[float, str]:
        cleaned = text.strip()
        match = re.match(r"([-+]?\d*\.?\d+(?:e[-+]?\d+)?)\s*([a-zA-Z]+)?", cleaned)
        if not match:
            return 0.0, ""
        value = float(match.group(1))
        unit = (match.group(2) or "ns").lower()
        return value, unit


def main():
    parser = argparse.ArgumentParser(description="Build a pulse schedule from a PsiScript program.")
    parser.add_argument("script", help="Path to a .psi file")
    parser.add_argument("--register", help="Filter to a specific register (defaults to all)")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text table")
    args = parser.parse_args()

    compiler = PulseLayerCompiler(args.script, target_register=args.register)
    schedule = compiler.compile()
    if args.json:
        print(schedule.to_json())
    else:
        print(schedule.to_table())


if __name__ == "__main__":
    main()
