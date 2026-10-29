"""Standard-library gate, synthesis and emitted-QASM equivalence checks."""

import cmath
import math
import re
import unittest
from dataclasses import replace

from compiler.qasm_compiler import OpenQasmCompiler
from psi_lang import PsiOperation, build_quantum_predicate
from quantum_gates import GATES, adjoint, canonical_name, decompose_gate, gate_matrix, identity, matmul


def evolve(state, op, n):
    """Small independent list-based oracle; no NumPy or viewer dependency."""
    out = state[:]
    predicate = build_quantum_predicate(op.predicate) if op.predicate else lambda bits: True
    if op.kind == "phase":
        return [v * (cmath.exp(1j*op.angle) if predicate([(i >> q)&1 for q in range(n)]) else 1) for i, v in enumerate(state)]
    if op.kind == "flip":
        for i, v in enumerate(state):
            if predicate([(i >> q)&1 for q in range(n)]): out[i ^ (1 << op.targets[0])] = v
        return out
    if op.kind == "superpose":
        for q in op.targets:
            old = out[:]
            for i in range(len(out)):
                if (i >> q)&1: continue
                j = i | (1 << q)
                out[i], out[j] = (old[i]+old[j])/math.sqrt(2), (old[i]-old[j])/math.sqrt(2)
        return out
    raise AssertionError(op.kind)


def primitive_matrix(op):
    n = len(op.targets)
    local = replace(op, targets=list(reversed(range(n))))
    columns = []
    for col in zip(*identity(2**n)):
        state = list(col)
        for primitive in decompose_gate(local): state = evolve(state, primitive, n)
        columns.append(state)
    return list(map(list, zip(*columns)))


def qasm_state(qasm, basis, register="q"):
    """Execute emitted qelib primitives including clean work qubits."""
    declarations = re.findall(r"qreg (\w+)\[(\d+)\];", qasm)
    wires, offset = {}, 0
    for name, size in declarations:
        for i in range(int(size)): wires[f"{name}[{i}]"] = offset+i
        offset += int(size)
    state = [0j] * 2**offset
    state[basis] = 1
    for line in qasm.splitlines():
        line = line.split("//")[0].strip()
        match = re.fullmatch(r"(h|x|z|u1|cu1|cx|ccx)(?:\(([^)]+)\))? (.*);", line)
        if not match: continue
        name, angle, refs = match.groups()
        targets = [wires[v.strip()] for v in refs.split(",")]
        if name == "h": op = PsiOperation("superpose", register, targets)
        elif name in {"x", "cx", "ccx"}:
            predicate = " && ".join(f"{register}[{q}] == 1" for q in targets[:-1]) or None
            op = PsiOperation("flip", register, targets[-1:], predicate=predicate)
        else:
            predicate = " && ".join(f"{register}[{q}] == 1" for q in targets)
            op = PsiOperation("phase", register, angle=math.pi if name == "z" else float(angle), predicate=predicate)
        state = evolve(state, op, offset)
    return state


class TestGateCatalog(unittest.TestCase):
    def assertMatrixClose(self, a, b, tolerance=1e-9):
        self.assertEqual(len(a), len(b))
        self.assertLess(max(abs(x-y) for ar, br in zip(a, b) for x, y in zip(ar, br)), tolerance)

    def test_reference_list_coverage(self):
        expected = "I GLOBALPHASE X Y Z S SX H CX ACX CZ DCX SWAP ISWAP P T CP CS RX RY RZ RXX RYY RZZ RXY SQRTSWAP SQRTISWAP SWAPPOW CSWAP U BARENCO B CSX CAN DB ECR FSIM GIVENS MAGIC SYC CZS DEUTSCH MARGOLUS PERES CCX CFSWAP".split()
        self.assertTrue(set(expected).issubset(GATES))
        self.assertEqual(canonical_name("Toffoli"), "CCX")
        self.assertEqual(canonical_name("sqrt_iswap"), "SQRTISWAP")

    def test_every_reference_unitary_and_exact_primitive_expansion(self):
        for name, spec in GATES.items():
            for value in (0, 0.317, -1.13, math.pi/2, math.pi):
                params = [value * (i+1) for i in range(len(spec.parameters))]
                for inverse in (False, True):
                    with self.subTest(gate=name, value=value, inverse=inverse):
                        ref = gate_matrix(name, *params, inverse=inverse)
                        self.assertMatrixClose(matmul(adjoint(ref), ref), identity(len(ref)))
                        op = PsiOperation("gate", "q", list(range(spec.qubits)), gate=name, parameters=params, inverse=inverse)
                        self.assertMatrixClose(primitive_matrix(op), ref)
                        self.assertTrue(all(p.kind in {"phase", "superpose", "flip"} for p in decompose_gate(op)))

    def test_every_gate_qasm_equivalent_up_to_one_global_phase(self):
        for name, spec in GATES.items():
            for inverse in (False, True):
                with self.subTest(gate=name, inverse=inverse):
                    params = [0.34*(i+1) for i in range(len(spec.parameters))]
                    op = PsiOperation("gate", "q", list(reversed(range(spec.qubits))), gate=name, parameters=params, inverse=inverse)
                    qasm = OpenQasmCompiler("q", spec.qubits).compile([op])
                    self.assertNotIn("TODO", qasm)
                    reference = gate_matrix(name, *params, inverse=inverse)
                    phase = None
                    for basis in range(len(reference)):
                        state = qasm_state(qasm, basis)
                        expected = [row[basis] for row in reference] + [0j]*(len(state)-len(reference))
                        if phase is None:
                            pivot = max(range(len(expected)), key=lambda i: abs(expected[i]))
                            phase = state[pivot] / expected[pivot]
                            self.assertAlmostEqual(abs(phase), 1)
                        self.assertLess(max(abs(v-phase*w) for v, w in zip(state, expected)), 1e-8)

    def test_roots_and_interaction_conventions(self):
        for root, base in [("SX", "X"), ("SQRTSWAP", "SWAP"), ("SQRTISWAP", "ISWAP")]:
            self.assertMatrixClose(matmul(gate_matrix(root), gate_matrix(root)), gate_matrix(base))
        self.assertMatrixClose(gate_matrix("SYC"), gate_matrix("FSIM", math.pi/2, math.pi/6))
        self.assertMatrixClose(gate_matrix("RXY", 0.76), matmul(gate_matrix("RXX", 0.38), gate_matrix("RYY", 0.38)))
        self.assertMatrixClose(gate_matrix("SWAPPOW", 1), gate_matrix("SWAP"))
        self.assertAlmostEqual(gate_matrix("FSIM", 0.3, 0.2)[3][3], cmath.exp(-0.2j))

    def test_qasm_guards_fail_closed_and_guard_basis_changes(self):
        op = PsiOperation("gate", "q", [0, 1], gate="RYY", parameters=[0.4], when="m == 1")
        measure = PsiOperation("measure", "q", [0], classical_target="m")
        qasm = OpenQasmCompiler("q", 2).compile([measure, op])
        gates = [l for l in qasm.splitlines() if l.startswith(("h ", "x ", "u1(", "cx "))]
        self.assertEqual(gates, [])
        self.assertIn("if (m==1) h", qasm)
        for guard in ("m == 1 || m == 0", "missing == 1", "m == 10"):
            with self.assertRaises(ValueError): OpenQasmCompiler("q", 2).compile([measure, replace(op, when=guard)])
            with self.assertRaises(ValueError):
                OpenQasmCompiler("q", 2).compile([measure, PsiOperation("gate", "q", [0], gate="I", when=guard)])

    def test_qasm_rejects_incomplete_predicates(self):
        for predicate in ("q[0] == 1 || q[1] == 1", "q[0] == 10", "q[0] == 1 junk"):
            with self.assertRaises(ValueError):
                OpenQasmCompiler("q", 2).compile([PsiOperation("phase", "q", angle=0.2, predicate=predicate)])

    def test_diffusion_guard_covers_entire_ancilla_network(self):
        measure = PsiOperation("measure", "q", [0], classical_target="m")
        qasm = OpenQasmCompiler("q", 5).compile([measure, PsiOperation("reflect", "q", axis="Axis.MEAN", when="m == 1")])
        for line in qasm.splitlines():
            if line.startswith(("h ", "x ", "z ", "cx ", "ccx ")): self.fail(line)

    def test_diffusion_operator_and_clean_ancillas(self):
        for n in range(1, 6):
            qasm = OpenQasmCompiler("q", n).compile([PsiOperation("reflect", "q", axis="Axis.MEAN")])
            for basis in range(2**n):
                state = qasm_state(qasm, basis)
                expected = [complex((i == basis) - 2/(2**n)) for i in range(2**n)]
                expected += [0j] * (len(state)-len(expected))
                self.assertLess(max(abs(a-b) for a, b in zip(state, expected)), 1e-10)

    def test_classical_destination_width_cannot_change(self):
        with self.assertRaisesRegex(ValueError, "size"):
            OpenQasmCompiler("q", 2).compile([
                PsiOperation("measure", "q", measure_all=True, classical_target="m"),
                PsiOperation("measure", "q", [0], classical_target="m")])


if __name__ == "__main__":
    unittest.main()
