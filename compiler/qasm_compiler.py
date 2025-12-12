"""
PsiScript -> OpenQASM 2.0 sketch compiler.

This is intentionally minimal: it lowers the common PsiScript samples into
qelib1 gates, emits comments when a predicate is too complex to lower, and
keeps classical guards (`when:`) as OpenQASM `if` statements.

PsiScript v1.2 adds an Analog/pulse layer. Those operations are parsed but not
lowered here; they are emitted as comments to preserve intent in the output.

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
