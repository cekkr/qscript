"""
Shared PsiScript helpers: parsing, dataclasses, and simple predicate utilities.

Designed to be reused by the viewer (state simulator + visualizer)
and the compiler (OpenQASM emitter).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


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
        operations: List[PsiOperation] = []

        for stmt in statements:
            regs = re.findall(r"(\w+)\s*=\s*Register\((\d+)\)", stmt)
            for name, count in regs:
                registers[name] = int(count)

            op = self._parse_operation(stmt.strip())
            if op:
                operations.append(op)

        if not registers:
            raise ValueError("No registers declared in the PsiScript.")

        return registers, operations

    def _gather_statements(self, lines: List[str]) -> List[str]:
        statements: List[str] = []
        buffer = ""
        for line in lines:
            without_comment = line.split("//", 1)[0].strip()
            if not without_comment:
                continue
            buffer += " " + without_comment
            while ";" in buffer:
                before, buffer = buffer.split(";", 1)
                if before.strip():
                    statements.append(before.strip())
                buffer = buffer.strip()
        if buffer.strip():
            statements.append(buffer.strip())
        return statements

    def _parse_operation(self, stmt: str) -> Optional[PsiOperation]:
        if ".Superpose" in stmt:
            reg, args = _split_call(stmt, ".Superpose")
            params = _parse_key_values(args)
            targets = _parse_targets(params.get("targets", "ALL"))
            return PsiOperation(kind="superpose", register=reg, targets=targets, raw=stmt)

        if ".Phase" in stmt:
            reg, args = _split_call(stmt, ".Phase")
            params = _parse_key_values(args)
            angle = eval_angle(params.get("angle", "0"))
            predicate = params.get("where")
            when = params.get("when")
            return PsiOperation(
                kind="phase",
                register=reg,
                angle=angle,
                predicate=predicate,
                when=when,
                raw=stmt,
            )

        if ".Flip" in stmt:
            reg, args = _split_call(stmt, ".Flip")
            params = _parse_key_values(args)
            target = int(params.get("target", "0"))
            predicate = params.get("where")
            when = params.get("when")
            return PsiOperation(
                kind="flip",
                register=reg,
                targets=[target],
                predicate=predicate,
                when=when,
                raw=stmt,
            )

        if ".Reflect" in stmt:
            reg, args = _split_call(stmt, ".Reflect")
            params = _parse_key_values(args)
            axis = params.get("axis", "Axis.MEAN")
            return PsiOperation(kind="reflect", register=reg, axis=axis, raw=stmt)

        if "Measure" in stmt:
            op = self._parse_measurement(stmt)
            if op:
                return op

        return None

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


# --- Expression utilities ---


def eval_angle(text: str) -> float:
    safe_locals = {"PI": math.pi, "pi": math.pi, "tau": math.tau}
    return float(eval(text, {"__builtins__": {}}, safe_locals))


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
