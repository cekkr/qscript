"""
PsiScript -> OpenQASM 2.0 sketch compiler.

This is intentionally minimal: it lowers the common PsiScript samples into
qelib1 gates, emits comments when a predicate is too complex to lower, and
keeps classical guards (`when:`) as OpenQASM `if` statements.

Run (from repo root):
    python compiler/qasm_compiler.py psiscripts/teleport.psi --out build/teleport.qasm
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from psi_lang import PsiOperation, PsiScriptParser, parse_conjunctive_controls


class QasmBuilder:
    def __init__(self, register: str, num_qubits: int):
        self.reg = register
        self.n = num_qubits
        self.lines: List[str] = [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            f"qreg {self.reg}[{self.n}];",
        ]
        self.cregs: Dict[str, int] = {}
        self.tmp_counter = 0

    def ensure_creg(self, name: str, size: int):
        if name in self.cregs:
            return
        self.cregs[name] = size
        self.lines.append(f"creg {name}[{size}];")

    def tmp_creg(self, size: int) -> str:
        name = f"tmp{self.tmp_counter}"
        self.tmp_counter += 1
        self.ensure_creg(name, size)
        return name

    def emit(self, text: str):
        self.lines.append(text)

    def render(self) -> str:
        return "\n".join(self.lines) + "\n"


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
        self.builder.emit(f"// Reflect around mean not lowered (psi op: {op.raw})")

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


def main():
    parser = argparse.ArgumentParser(description="Compile a PsiScript file into OpenQASM 2.0 (best-effort).")
    parser.add_argument("script", help="Path to .psi program to compile")
    parser.add_argument("--register", help="Register name to compile (defaults to first declared)")
    parser.add_argument("--out", type=Path, help="Destination .qasm file (stdout if omitted)")
    args = parser.parse_args()

    ps_parser = PsiScriptParser(args.script)
    registers, operations = ps_parser.parse()
    target_register = args.register or next(iter(registers.keys()))
    if target_register not in registers:
        raise SystemExit(f"Register '{target_register}' not declared.")

    filtered_ops = [op for op in operations if op.register == target_register]
    compiler = OpenQasmCompiler(target_register, registers[target_register])
    qasm = compiler.compile(filtered_ops)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(qasm, encoding="utf-8")
        print(f"Wrote OpenQASM to {args.out}")
    else:
        print(qasm)


if __name__ == "__main__":
    main()
