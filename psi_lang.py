"""
Shared PsiScript helpers: parsing, dataclasses, and simple predicate utilities.

Designed to be reused by the viewer (state simulator + visualizer)
and the compiler (OpenQASM emitter). Updated for PsiScript v1.2 to
recognize the hybrid analog/pulse layer syntax while keeping legacy
logic-layer flows intact.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


# --- Internal structures ---


@dataclass
class _Statement:
    text: str
    children: List["_Statement"] = field(default_factory=list)


# --- Dataclasses ---


@dataclass
class PsiOperation:
    kind: str
    register: str
    targets: List[int] = field(default_factory=list)
    angle: float = 0.0
    predicate: Optional[str] = None
    when: Optional[str] = None
    axis: Optional[str] = None
    classical_target: Optional[str] = None
    measure_all: bool = False
    raw: str = ""
    scope: str = "logic"
    duration: Optional[str] = None
    shape: Optional[str] = None
    waveform: Optional[str] = None
    channel: Optional[str] = None
    frequency: Optional[str] = None
    kernel: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class StepSnapshot:
    label: str
    detail: str
    amplitudes: object  # numpy array, but kept generic to avoid hard dependency here
    measurement: Optional[Dict[str, object]] = None
    classical_bits: Dict[str, int] = field(default_factory=dict)


# --- Parser ---


class PsiScriptParser:
    """Lightweight parser for the PsiScript samples in this repository."""

    def __init__(self, path: str):
        self.path = path

    def parse(self) -> Tuple[Dict[str, int], List[PsiOperation]]:
        with open(self.path, "r", encoding="utf-8") as handle:
            statements = self._gather_statements(handle.readlines())

        registers: Dict[str, int] = {}
        self._collect_registers(statements, registers)

        if not registers:
            raise ValueError("No registers declared in the PsiScript.")

        operations: List[PsiOperation] = []
        default_register = next(iter(registers.keys()))
        self._walk(statements, operations, default_register=default_register)

        return registers, operations

    def _collect_registers(self, statements: List[_Statement], registers: Dict[str, int]):
        for stmt in statements:
            regs = re.findall(r"(\w+)\s*=\s*Register\((\d+)\)", stmt.text)
            for name, count in regs:
                registers[name] = int(count)
            if stmt.children:
                self._collect_registers(stmt.children, registers)

    def _gather_statements(self, lines: List[str]) -> List[_Statement]:
        tokens: List[str] = []
        for line in lines:
            without_comment = line.split("//", 1)[0].strip()
            if not without_comment:
                continue
            buf = ""
            for char in without_comment:
                if char in ";{}":
                    if buf.strip():
                        tokens.append(buf.strip())
                    tokens.append(char)
                    buf = ""
                else:
                    buf += char
            if buf.strip():
                tokens.append(buf.strip())

        idx = 0

        def parse_block() -> List[_Statement]:
            nonlocal idx
            statements: List[_Statement] = []
            while idx < len(tokens):
                token = tokens[idx]
                idx += 1
                if token == ";":
                    continue
                if token == "}":
                    break
                header = token
                children: List[_Statement] = []
                if idx < len(tokens) and tokens[idx] == "{":
                    idx += 1  # consume "{"
                    children = parse_block()
                if idx < len(tokens) and tokens[idx] == ";":
                    idx += 1  # consume optional ";"
                statements.append(_Statement(text=header, children=children))
            return statements

        return parse_block()

    def _walk(
        self,
        statements: List[_Statement],
        operations: List[PsiOperation],
        default_register: Optional[str],
        scope: str = "logic",
        analog_context: Optional[Tuple[Optional[str], Optional[int]]] = None,
    ):
        for stmt in statements:
            op_result, ctx_update = self._parse_operation(
                stmt.text,
                scope=scope,
                analog_context=analog_context,
                default_register=default_register,
            )
            if op_result:
                if isinstance(op_result, list):
                    operations.extend(op_result)
                else:
                    operations.append(op_result)

            next_default = ctx_update.get("default_register", default_register)
            next_scope = ctx_update.get("scope", scope)
            next_analog = ctx_update.get("analog_context", analog_context)

            if stmt.children:
                self._walk(
                    stmt.children,
                    operations,
                    default_register=next_default,
                    scope=next_scope,
                    analog_context=next_analog,
                )

    def _parse_operation(
        self,
        stmt: str,
        *,
        scope: str,
        analog_context: Optional[Tuple[Optional[str], Optional[int]]],
        default_register: Optional[str],
    ) -> Tuple[Optional[PsiOperation], Dict[str, object]]:
        if ".Superpose" in stmt:
            reg, args = _split_call(stmt, ".Superpose")
            params = _parse_key_values(args)
            targets = _parse_targets(params.get("targets", "ALL"))
            return PsiOperation(kind="superpose", register=reg, targets=targets, raw=stmt, scope=scope), {}

        if ".Phase" in stmt:
            reg, args = _split_call(stmt, ".Phase")
            params = _parse_key_values(args)
            angle = eval_angle(params.get("angle", "0"))
            predicate = params.get("where")
            when = params.get("when")
            return (
                PsiOperation(
                    kind="phase",
                    register=reg,
                    angle=angle,
                    predicate=predicate,
                    when=when,
                    raw=stmt,
                    scope=scope,
                ),
                {},
            )

        if ".Flip" in stmt:
            reg, args = _split_call(stmt, ".Flip")
            params = _parse_key_values(args)
            target = int(params.get("target", "0"))
            predicate = params.get("where")
            when = params.get("when")
            return (
                PsiOperation(
                    kind="flip",
                    register=reg,
                    targets=[target],
                    predicate=predicate,
                    when=when,
                    raw=stmt,
                    scope=scope,
                ),
                {},
            )

        if ".Reflect" in stmt:
            reg, args = _split_call(stmt, ".Reflect")
            params = _parse_key_values(args)
            axis = params.get("axis", "Axis.MEAN")
            return PsiOperation(kind="reflect", register=reg, axis=axis, raw=stmt, scope=scope), {}

        if "Measure" in stmt:
            op = self._parse_measurement(stmt)
            if op:
                op.scope = scope
                return op, {}

        if stmt.startswith("Analog"):
            args = _extract_args(stmt, "Analog")
            params = _parse_key_values(args)
            target_ref = params.get("target", "")
            reg_name, target_idx = _parse_target_ref(target_ref)
            reg = reg_name or default_register or ""
            op = PsiOperation(
                kind="analog",
                register=reg,
                targets=[target_idx] if target_idx is not None else [],
                raw=stmt,
                scope="analog",
                metadata=params,
            )
            return op, {"scope": "analog", "analog_context": (reg, target_idx), "default_register": reg}

        if stmt.startswith("Align"):
            op = PsiOperation(kind="align", register=default_register or "", raw=stmt, scope="align")
            return op, {"scope": "align"}

        if stmt.startswith("branch"):
            label = stmt.split(" ", 1)[1].strip() if " " in stmt else "branch"
            branch_reg, branch_idx = _parse_target_ref(label)
            reg = branch_reg or default_register or ""
            metadata = {"label": label}
            targets = [branch_idx] if branch_idx is not None else []
            op = PsiOperation(kind="branch", register=reg, targets=targets, raw=stmt, scope=scope, metadata=metadata)
            ctx = {"default_register": reg}
            return op, ctx

        if stmt.startswith("Rotate"):
            args = _extract_args(stmt, "Rotate")
            params = _parse_key_values(args)
            axis = params.get("axis")
            angle = _safe_eval_angle(params.get("angle", "0"))
            duration = params.get("duration")
            shape = params.get("shape")
            target_ref = params.get("target", "")
            reg_name, target_idx = _parse_target_ref(target_ref)
            if target_idx is None and analog_context:
                target_idx = analog_context[1]
            reg = reg_name or (analog_context[0] if analog_context else None) or default_register or ""
            targets = [target_idx] if target_idx is not None else []
            op = PsiOperation(
                kind="rotate",
                register=reg,
                targets=targets,
                axis=axis,
                angle=angle,
                duration=duration,
                shape=shape,
                raw=stmt,
                scope=scope,
                metadata=params,
            )
            return op, {}

        if stmt.startswith("Wait"):
            args = _extract_args(stmt, "Wait")
            params = _parse_key_values(args)
            duration = params.get("duration", args.strip())
            target_idx = analog_context[1] if analog_context else None
            reg = (analog_context[0] if analog_context else None) or default_register or ""
            targets = [target_idx] if target_idx is not None else []
            op = PsiOperation(
                kind="wait",
                register=reg,
                duration=duration,
                targets=targets,
                raw=stmt,
                scope=scope,
                metadata=params,
            )
            return op, {}

        if stmt.startswith("ShiftPhase"):
            args = _extract_args(stmt, "ShiftPhase")
            params = _parse_key_values(args)
            angle = _safe_eval_angle(params.get("angle", args))
            reg = (analog_context[0] if analog_context else None) or default_register or ""
            target_idx = analog_context[1] if analog_context else None
            targets = [target_idx] if target_idx is not None else []
            op = PsiOperation(
                kind="shiftphase",
                register=reg,
                angle=angle,
                targets=targets,
                raw=stmt,
                scope=scope,
                metadata=params,
            )
            return op, {}

        if stmt.startswith("SetFreq"):
            args = _extract_args(stmt, "SetFreq")
            params = _parse_key_values(args)
            freq = params.get("hz", args.strip())
            reg = (analog_context[0] if analog_context else None) or default_register or ""
            target_idx = analog_context[1] if analog_context else None
            targets = [target_idx] if target_idx is not None else []
            op = PsiOperation(
                kind="setfreq",
                register=reg,
                targets=targets,
                frequency=freq,
                raw=stmt,
                scope=scope,
                metadata=params,
            )
            return op, {}

        if stmt.startswith("Play"):
            args = _extract_args(stmt, "Play")
            params = _parse_key_values(args)
            if not params and "," in args:
                waveform, channel = [a.strip() for a in args.split(",", 1)]
                params = {"waveform": waveform, "channel": channel}
            reg = (analog_context[0] if analog_context else None) or default_register or ""
            op = PsiOperation(
                kind="play",
                register=reg,
                waveform=params.get("waveform"),
                channel=params.get("channel"),
                raw=stmt,
                scope=scope,
                metadata=params,
            )
            return op, {}

        if stmt.startswith("Acquire"):
            args = _extract_args(stmt, "Acquire")
            params = _parse_key_values(args)
            duration = params.get("duration", args.strip())
            kernel = params.get("kernel")
            reg = (analog_context[0] if analog_context else None) or default_register or ""
            op = PsiOperation(
                kind="acquire",
                register=reg,
                duration=duration,
                kernel=kernel,
                raw=stmt,
                scope=scope,
                metadata=params,
            )
            return op, {}

        return None, {}

    def _parse_measurement(self, stmt: str) -> Optional[PsiOperation]:
        match_indexed = re.match(
            r"(?:let\s+(?P<c>\w+)\s*=\s*)?Measure\(\s*(?P<reg>\w+)\[(?P<idx>\d+)\]\s*\)", stmt
        )
        if match_indexed:
            classical = match_indexed.group("c")
            reg = match_indexed.group("reg")
            idx = int(match_indexed.group("idx"))
            return PsiOperation(
                kind="measure",
                register=reg,
                targets=[idx],
                classical_target=classical,
                raw=stmt,
            )

        match_method = re.match(
            r"(?:let\s+(?P<c>\w+)\s*=\s*)?(?P<reg>\w+)\.Measure\(\s*\)", stmt
        )
        if match_method:
            classical = match_method.group("c")
            reg = match_method.group("reg")
            return PsiOperation(
                kind="measure",
                register=reg,
                measure_all=True,
                classical_target=classical,
                raw=stmt,
            )

        return None


# --- Parsing helpers (module level) ---


def _split_call(stmt: str, token: str) -> Tuple[str, str]:
    reg = stmt.split(token, 1)[0].strip()
    start = stmt.index("(", stmt.index(token))
    end = stmt.rindex(")")
    return reg, stmt[start + 1 : end]


def _extract_args(stmt: str, token: str) -> str:
    if token not in stmt or "(" not in stmt or ")" not in stmt:
        return ""
    start = stmt.index("(", stmt.index(token))
    end = stmt.rfind(")")
    return stmt[start + 1 : end]


def _parse_key_values(args: str) -> Dict[str, str]:
    items: Dict[str, str] = {}
    parts = _split_args(args)
    for part in parts:
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        items[key.strip()] = value.strip()
    return items


def _split_args(arg_str: str) -> List[str]:
    parts: List[str] = []
    buf = ""
    depth = 0
    for char in arg_str:
        if char in "([":  # crude depth tracking for brackets
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            if buf.strip():
                parts.append(buf.strip())
            buf = ""
        else:
            buf += char
    if buf.strip():
        parts.append(buf.strip())
    return parts


def _parse_targets(value: str) -> List[int]:
    value = value.strip()
    if value.upper() == "ALL":
        return ["ALL"]  # sentinel
    if value.startswith("[") and value.endswith("]"):
        return [int(v.strip()) for v in value.strip("[]").split(",") if v.strip()]
    return [int(value)]


def _parse_target_ref(value: str) -> Tuple[Optional[str], Optional[int]]:
    value = value.strip()
    match = re.match(r"(\w+)\[(\d+)\]", value)
    if match:
        return match.group(1), int(match.group(2))
    if value:
        return value, None
    return None, None


# --- Expression utilities ---


def eval_angle(text: str) -> float:
    safe_locals = {"PI": math.pi, "pi": math.pi, "tau": math.tau}
    return float(eval(text, {"__builtins__": {}}, safe_locals))


def _safe_eval_angle(text: str) -> float:
    try:
        return eval_angle(text)
    except Exception:
        return 0.0


def build_quantum_predicate(expr: str) -> Callable[[List[int]], bool]:
    sanitized = expr.replace("&&", " and ").replace("||", " or ").replace("!", " not ")
    sanitized = re.sub(r"\b\w+\[(\d+)\]", r"bits[\1]", sanitized)
    sanitized = sanitized.replace("true", "True").replace("false", "False")
    code = compile(sanitized, "<where>", "eval")
    return lambda bits: bool(eval(code, {"__builtins__": {}}, {"bits": bits}))


def build_classical_predicate(expr: str) -> Callable[[Dict[str, int]], bool]:
    sanitized = expr.replace("&&", " and ").replace("||", " or ").replace("!", " not ")

    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in {"and", "or", "not", "True", "False"}:
            return token
        if token.isdigit():
            return token
        return f"c_bits.get('{token}', 0)"

    sanitized = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", repl, sanitized)
    code = compile(sanitized, "<when>", "eval")
    return lambda c_bits: bool(eval(code, {"__builtins__": {}}, {"c_bits": c_bits}))


def parse_conjunctive_controls(predicate: str, register: str) -> Optional[List[Tuple[int, int]]]:
    """
    Parse predicates of the shape: reg[i] == 1 && reg[j] == 0 && ...
    Returns list of (qubit_index, value) or None if unsupported (OR/equality across registers).
    """
    if predicate is None:
        return []
    if "||" in predicate:
        return None
    terms = [p.strip() for p in predicate.split("&&")]
    controls: List[Tuple[int, int]] = []
    for term in terms:
        if term.lower() in {"true", "1", ""}:
            continue
        match = re.match(rf"{register}\[(\d+)\]\s*==\s*([01])", term)
        if match:
            controls.append((int(match.group(1)), int(match.group(2))))
            continue
        match_simple = re.match(rf"{register}\[(\d+)\]$", term)
        if match_simple:
            controls.append((int(match_simple.group(1)), 1))
            continue
        return None
    return controls
