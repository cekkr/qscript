"""
Shared qscript helpers: parsing, dataclasses, and simple predicate utilities.

Designed to be reused by the viewer (state simulator + visualizer)
and the compiler (OpenQASM emitter). Updated for qscript v1.2 to
recognize the hybrid analog/pulse layer syntax while keeping legacy
logic-layer flows intact. Named logical gates use the standard-library catalog
in quantum_gates.py; pulse timing remains separate from logical rotations.
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
    gate: Optional[str] = None
    parameters: List[float] = field(default_factory=list)
    inverse: bool = False


@dataclass
class StepSnapshot:
    label: str
    detail: str
    amplitudes: object  # numpy array, but kept generic to avoid hard dependency here
    measurement: Optional[Dict[str, object]] = None
    classical_bits: Dict[str, int] = field(default_factory=dict)
    operation: Optional[PsiOperation] = None
    comparison: Optional[Dict[str, object]] = None


# --- Parser ---


class QScriptParser:
    """Lightweight parser for the qscript samples in this repository."""

    def __init__(self, path: str):
        self.path = path
        self.statements: List[_Statement] = []

    def parse(self) -> Tuple[Dict[str, int], List[PsiOperation]]:
        with open(self.path, "r", encoding="utf-8") as handle:
            statements = self._gather_statements(handle.readlines())
            self.statements = statements

        registers: Dict[str, int] = {}
        self._collect_registers(statements, registers)

        if not registers:
            raise ValueError("No registers declared in the qscript.")
        if any(n < 1 for n in registers.values()):
            raise ValueError("Registers must contain at least one qubit")

        operations: List[PsiOperation] = []
        default_register = next(iter(registers.keys()))
        self._walk(statements, operations, default_register=default_register)

        from quantum_gates import validate_gate
        for op in operations:
            if op.register not in registers:
                raise ValueError(f"Undeclared register {op.register!r}: {op.raw}")
            if op.kind == "gate":
                validate_gate(op.gate, op.targets, op.parameters, registers[op.register])
            elif any(type(q) is int and not 0 <= q < registers[op.register] for q in op.targets):
                raise ValueError(f"Qubit outside register: {op.raw}")
            if op.predicate:
                for reg, index in re.findall(r"(\w+)\[(\d+)\]", op.predicate):
                    if reg != op.register or int(index) >= registers[reg]:
                        raise ValueError(f"Predicate must address valid qubits in {op.register}: {op.predicate}")

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
        buf, depth, quote = "", 0, None
        source = "".join(lines)
        pos = 0
        while pos < len(source):
            char = source[pos]
            if quote:
                buf += char
                if char == quote and (pos == 0 or source[pos - 1] != "\\"):
                    quote = None
            elif source[pos:pos+2] == "//":
                end = source.find("\n", pos)
                pos = len(source) if end < 0 else end
                continue
            elif char in "\"'":
                quote = char
                buf += char
            elif char in "([":
                depth += 1
                buf += char
            elif char in ")]":
                depth -= 1
                if depth < 0:
                    raise ValueError("Unbalanced call or target list")
                buf += char
            elif depth == 0 and char in ";{}\n":
                if buf.strip(): tokens.append(buf.strip())
                if char != "\n": tokens.append(char)
                buf = ""
            else:
                buf += " " if char == "\n" else char
            pos += 1
        if depth or quote:
            raise ValueError("Unclosed call, target list, or string")
        if buf.strip(): tokens.append(buf.strip())

        idx = 0

        def parse_block(nested=False) -> List[_Statement]:
            nonlocal idx
            statements: List[_Statement] = []
            while idx < len(tokens):
                token = tokens[idx]
                idx += 1
                if token == ";":
                    continue
                if token == "}":
                    if not nested: raise ValueError("Unexpected closing brace")
                    return statements
                if token == "{": raise ValueError("Block needs a header")
                header = token
                children: List[_Statement] = []
                if idx < len(tokens) and tokens[idx] == "{":
                    idx += 1  # consume "{"
                    children = parse_block(nested=True)
                if idx < len(tokens) and tokens[idx] == ";":
                    idx += 1  # consume optional ";"
                statements.append(_Statement(text=header, children=children))
            if nested: raise ValueError("Unclosed block")
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
        from quantum_gates import GATES, ALIASES, canonical_name

        method = re.fullmatch(r"(\w+)\.(\w+)\s*\((.*)\)", stmt, re.DOTALL)
        if method:
            reg, verb, args = method.groups()
            if scope == "analog" and verb in {"Phase", "Flip", "Reflect", "Superpose", "Gate", "Turn", "Interact"}:
                raise ValueError("Logic operations belong outside Analog scope")
            if verb not in {"Phase", "Flip", "Reflect", "Superpose"} and (verb in {"Gate", "Turn", "Interact"} or verb.upper() in GATES or verb.upper() in ALIASES):
                if scope == "analog":
                    raise ValueError("Logic gates belong outside Analog scope")
                params = _parse_key_values(args)
                if any(":" not in part for part in _split_args(args)):
                    raise ValueError("Gate arguments must use name: value syntax")
                if verb == "Turn":
                    axis = params.get("axis", "Z").upper()
                    if axis not in {"X", "Y", "Z"}: raise ValueError("Turn axis must be X, Y, or Z")
                    name = "R" + axis
                elif verb == "Interact":
                    axes = params.get("axes", "XX").upper()
                    if axes not in {"XX", "YY", "ZZ", "XY", "ZX"}: raise ValueError("Unsupported interaction axes")
                    name = "R" + axes
                else:
                    name = params.get("name", "") if verb == "Gate" else verb
                name = canonical_name(name)
                spec = GATES[name]
                allowed = {"targets", "target", "when", "inverse", "params"} | set(spec.parameters)
                if verb == "Gate": allowed.add("name")
                if verb == "Turn": allowed.add("axis")
                if verb == "Interact": allowed.add("axes")
                if len(spec.parameters) == 1: allowed.add("angle")
                unknown = set(params) - allowed
                if unknown: raise ValueError(f"Unsupported {name} arguments: {sorted(unknown)}")
                targets = _parse_targets(params.get("targets", params.get("target", "[]")))
                if "params" in params:
                    if set(params) & set(spec.parameters): raise ValueError("Use params or named gate parameters")
                    values = [eval_angle(v) for v in _split_args(params["params"].strip("[]"))]
                else:
                    values = []
                    for key in spec.parameters:
                        value = params.get(key, params.get("angle") if len(spec.parameters) == 1 else None)
                        if value is None: raise ValueError(f"Missing {key} for {name}")
                        values.append(eval_angle(value))
                inverse = params.get("inverse", "false").lower()
                if inverse not in ("true", "false"): raise ValueError("inverse must be true or false")
                return PsiOperation("gate", reg, targets, gate=name, parameters=values,
                                    inverse=inverse == "true", when=params.get("when"), raw=stmt), {}

        if ".Superpose" in stmt:
            reg, args = _split_call(stmt, ".Superpose")
            params = _parse_key_values(args)
            targets = _parse_targets(params.get("targets", "ALL"))
            return PsiOperation(kind="superpose", register=reg, targets=targets, when=params.get("when"), raw=stmt, scope=scope), {}

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
            return PsiOperation(kind="reflect", register=reg, axis=axis, when=params.get("when"), raw=stmt, scope=scope), {}

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
            ctx = {"default_register": reg, "analog_context": (reg, branch_idx)}
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
        assignment = re.fullmatch(r"(?:let\s+(\w+)\s*=\s*)?(.*)", stmt)
        classical, call = assignment.groups()
        method = re.fullmatch(r"(\w+)\.Measure\((.*)\)", call)
        function = re.fullmatch(r"Measure\((.*)\)", call)
        if method:
            reg, args = method.groups()
            if any(":" not in part for part in _split_args(args)):
                raise ValueError("Measurement arguments must use name: value syntax")
            params = _parse_key_values(args)
            if set(params) - {"target", "when"}: raise ValueError("Unknown measurement argument")
            idx = int(params["target"]) if "target" in params else None
        elif function:
            parts = _split_args(function.group(1))
            if not parts: raise ValueError("Measure needs a register or qubit")
            ref = re.fullmatch(r"(\w+)(?:\[(\d+)\])?", parts[0])
            if not ref: raise ValueError("Invalid measurement target")
            reg, index = ref.groups()
            idx = int(index) if index is not None else None
            if any(":" not in part for part in parts[1:]):
                raise ValueError("Measurement arguments must use name: value syntax")
            params = _parse_key_values(",".join(parts[1:]))
            if set(params) - {"when"}: raise ValueError("Unknown measurement argument")
        else:
            return None
        return PsiOperation("measure", reg, [idx] if idx is not None else [], measure_all=idx is None,
                            classical_target=classical, when=params.get("when"), raw=stmt)


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
    sanitized = re.sub(r"!(?!=)", " not ", expr.replace("&&", " and ").replace("||", " or ")).strip()
    sanitized = re.sub(r"\b\w+\[(\d+)\]", r"bits[\1]", sanitized)
    sanitized = re.sub(r"\b(true|false)\b", lambda m: m.group(0).title(), sanitized)
    code = compile(sanitized, "<where>", "eval")
    return lambda bits: bool(eval(code, {"__builtins__": {}}, {"bits": bits}))


def build_classical_predicate(expr: str) -> Callable[[Dict[str, int]], bool]:
    sanitized = re.sub(r"!(?!=)", " not ", expr.replace("&&", " and ").replace("||", " or ")).strip()
    sanitized = re.sub(r"\b(true|false)\b", lambda m: m.group(0).title(), sanitized)

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
        match = re.fullmatch(rf"{re.escape(register)}\[(\d+)\]\s*==\s*([01])", term)
        if match:
            controls.append((int(match.group(1)), int(match.group(2))))
            continue
        match_simple = re.fullmatch(rf"{re.escape(register)}\[(\d+)\]", term)
        if match_simple:
            controls.append((int(match_simple.group(1)), 1))
            continue
        return None
    if len({q for q, _ in controls}) != len(controls): return None
    return controls
