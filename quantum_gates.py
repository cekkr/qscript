"""Exact gate references and synthesis into qscript's sculpting primitives.

No numerical/GUI dependency. Local matrices use |targets[0] ... targets[-1]>
(first operand most significant); register statevectors keep q0 least significant.
See explain/gate-reference.md for conventions and sources.
"""

import cmath
import math
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class GateSpec:
    qubits: int
    parameters: tuple = ()


GATES = {
    **{n: GateSpec(1) for n in ("I", "X", "Y", "Z", "H", "S", "T", "SX", "SDG", "TDG", "SXDG")},
    **{n: GateSpec(1, ("angle",)) for n in ("GLOBALPHASE", "P", "RX", "RY", "RZ")},
    "U": GateSpec(1, ("theta", "phi", "lambda")),
    **{n: GateSpec(2) for n in ("CX", "ACX", "CY", "CZ", "CH", "CS", "CSX", "DCX", "SWAP", "ISWAP", "SQRTSWAP", "SQRTISWAP", "B", "DB", "ECR", "MAGIC", "SYC", "FSWAP")},
    **{n: GateSpec(2, ("angle",)) for n in ("CP", "CRX", "CRY", "CRZ", "RXX", "RYY", "RZZ", "RXY", "RZX", "GIVENS")},
    "SWAPPOW": GateSpec(2, ("alpha",)),
    "BARENCO": GateSpec(2, ("alpha", "phi", "theta")),
    "CAN": GateSpec(2, ("a", "b", "c")),
    "FSIM": GateSpec(2, ("theta", "phi")),
    "CZS": GateSpec(2, ("theta", "phi", "gamma")),
    **{n: GateSpec(3) for n in ("CCX", "CCZ", "CSWAP", "CFSWAP", "MARGOLUS", "PERES")},
    "DEUTSCH": GateSpec(3, ("theta",)),
    "CCZS": GateSpec(3, ("theta", "phi", "gamma")),
}
ALIASES = {
    "IDENTITY": "I", "ID": "I", "NOT": "X", "HADAMARD": "H",
    "PH": "GLOBALPHASE", "PHASE": "GLOBALPHASE", "PHASESHIFT": "P", "U1": "P",
    "V": "SX", "SQRTX": "SX", "SQRTNOT": "SX", "SQRTZ": "S", "U3": "U",
    "CNOT": "CX", "XOR": "CX", "XNOR": "ACX", "C0X": "ACX", "ANTICNOT": "ACX",
    "CPF": "CZ", "CSIGN": "CZ", "CPHASE": "CP", "CR": "CP", "CV": "CSX",
    "DCNOT": "DCX", "XX": "RXX", "YY": "RYY", "ZZ": "RZZ", "XY": "RXY",
    "SWAPALPHA": "SWAPPOW", "FREDKIN": "CSWAP", "BERKELEY": "B", "N": "CAN",
    "DAGWOOD": "DB", "G": "GIVENS", "M": "MAGIC", "SYCAMORE": "SYC",
    "D": "DEUTSCH", "RCCX": "MARGOLUS", "PG": "PERES", "TOFFOLI": "CCX",
    "TOFF": "CCX", "CCNOT": "CCX", "FFREDKIN": "CFSWAP", "CFSWAP": "CFSWAP",
}


def canonical_name(name):
    key = str(name).strip("\"'").upper().replace("_", "").replace("-", "")
    key = ALIASES.get(key, key)
    if key not in GATES:
        raise ValueError(f"Unknown gate {name!r}; choose from {', '.join(GATES)}")
    return key


def validate_gate(name, targets, parameters, num_qubits=None):
    name = canonical_name(name)
    spec = GATES[name]
    if len(targets) != spec.qubits or len(set(targets)) != len(targets):
        raise ValueError(f"{name} needs {spec.qubits} distinct ordered targets")
    if any(type(q) is not int or q < 0 or (num_qubits is not None and q >= num_qubits) for q in targets):
        raise ValueError(f"Invalid targets for {name}: {targets}")
    if len(parameters) != len(spec.parameters) or any(not math.isfinite(p) for p in parameters):
        raise ValueError(f"{name} needs finite parameters {spec.parameters}")
    return name


def identity(size):
    return [[complex(i == j) for j in range(size)] for i in range(size)]


def adjoint(matrix):
    return [[complex(value).conjugate() for value in col] for col in zip(*matrix)]


def matmul(a, b):
    return [[sum(x * y for x, y in zip(row, col)) for col in zip(*b)] for row in a]


def _controlled(matrix):
    result = identity(2 * len(matrix))
    for i, row in enumerate(matrix):
        result[i + len(matrix)][len(matrix):] = row[:]
    return result


def gate_matrix(name, *parameters, inverse=False):
    """Analytic reference, independent of the primitive decomposition below."""
    name = canonical_name(name)
    spec = GATES[name]
    validate_gate(name, list(range(spec.qubits)), parameters)
    pi, exp = math.pi, cmath.exp
    m = identity(2 ** spec.qubits)
    if name == "I":
        pass
    elif name == "GLOBALPHASE":
        m = [[exp(1j * parameters[0]), 0], [0, exp(1j * parameters[0])]]
    elif name in ("X", "Y", "Z", "H", "S", "T", "SX", "SDG", "TDG", "SXDG"):
        m = {"X": [[0, 1], [1, 0]], "Y": [[0, -1j], [1j, 0]], "Z": [[1, 0], [0, -1]],
             "H": [[1 / math.sqrt(2), 1 / math.sqrt(2)], [1 / math.sqrt(2), -1 / math.sqrt(2)]],
             "S": [[1, 0], [0, 1j]], "T": [[1, 0], [0, exp(1j * pi / 4)]],
             "SX": [[(1 + 1j) / 2, (1 - 1j) / 2], [(1 - 1j) / 2, (1 + 1j) / 2]]}.get(name)
        if m is None:
            m = adjoint(gate_matrix({"SDG": "S", "TDG": "T", "SXDG": "SX"}[name]))
    elif name in ("P", "RX", "RY", "RZ"):
        t = parameters[0]
        c, s = math.cos(t / 2), math.sin(t / 2)
        m = {"P": [[1, 0], [0, exp(1j * t)]], "RX": [[c, -1j * s], [-1j * s, c]],
             "RY": [[c, -s], [s, c]], "RZ": [[exp(-1j * t / 2), 0], [0, exp(1j * t / 2)]]}[name]
    elif name == "U":
        t, p, l = parameters
        c, s = math.cos(t / 2), math.sin(t / 2)
        m = [[c, -exp(1j * l) * s], [exp(1j * p) * s, exp(1j * (p + l)) * c]]
    elif name in ("CX", "CY", "CZ", "CH", "CS", "CSX", "CP", "CRX", "CRY", "CRZ", "CCX", "CCZ"):
        base = {"CCX": "CX", "CCZ": "CZ"}.get(name, name[1:])
        m = _controlled(gate_matrix(base, *parameters))
    elif name == "ACX":
        m = [[0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    elif name in ("SWAP", "DCX", "PERES"):
        permutations = {"SWAP": [0, 2, 1, 3], "DCX": [0, 3, 1, 2], "PERES": [0, 1, 2, 3, 6, 7, 5, 4]}
        m = [[complex(i == permutations[name][j]) for j in range(len(m))] for i in range(len(m))]
    elif name in ("ISWAP", "SQRTISWAP", "RXY", "FSIM", "SYC", "DB", "GIVENS"):
        t = {"ISWAP": -pi / 2, "SQRTISWAP": -pi / 4, "SYC": pi / 2, "DB": 3 * pi / 8}.get(name)
        if t is None:
            t = parameters[0] / 2 if name == "RXY" else parameters[0]
        c, s = math.cos(t), math.sin(t)
        m[1][1] = m[2][2] = c
        m[1][2], m[2][1] = (-s, s) if name == "GIVENS" else (-1j * s, -1j * s)
        if name in ("FSIM", "SYC"):
            # Standard Cirq/Google convention; Wikipedia's FSIM row has opposite phi.
            m[3][3] = exp(-1j * (pi / 6 if name == "SYC" else parameters[1]))
    elif name in ("SQRTSWAP", "SWAPPOW"):
        alpha = 0.5 if name == "SQRTSWAP" else parameters[0]
        e = exp(1j * pi * alpha)
        m[1][1] = m[2][2] = (1 + e) / 2
        m[1][2] = m[2][1] = (1 - e) / 2
    elif name in ("CSWAP", "CFSWAP", "FSWAP"):
        m = gate_matrix("SWAP")
        if name in ("CFSWAP", "FSWAP"):
            m[3][3] = -1
        if name != "FSWAP":
            m = _controlled(m)
    elif name in ("RXX", "RYY", "RZZ", "RZX"):
        axes = name[1:]
        a, b = gate_matrix(axes[0]), gate_matrix(axes[1])
        p = [[a[i // 2][j // 2] * b[i % 2][j % 2] for j in range(4)] for i in range(4)]
        c, s = math.cos(parameters[0] / 2), math.sin(parameters[0] / 2)
        m = [[c * (i == j) - 1j * s * p[i][j] for j in range(4)] for i in range(4)]
    elif name in ("CAN", "B"):
        a, b, c = (pi / 4, pi / 8, 0) if name == "B" else parameters
        ep, em = exp(1j * c), exp(-1j * c)
        m = [[ep * math.cos(a - b), 0, 0, 1j * ep * math.sin(a - b)],
             [0, em * math.cos(a + b), 1j * em * math.sin(a + b), 0],
             [0, 1j * em * math.sin(a + b), em * math.cos(a + b), 0],
             [1j * ep * math.sin(a - b), 0, 0, ep * math.cos(a - b)]]
    elif name == "BARENCO":
        a, p, t = parameters
        m = _controlled([[exp(1j * a) * math.cos(t), -1j * exp(1j * (a - p)) * math.sin(t)],
                         [-1j * exp(1j * (a + p)) * math.sin(t), exp(1j * a) * math.cos(t)]])
    elif name == "ECR":
        m = [[v / math.sqrt(2) for v in row] for row in
             [[0, 0, 1, 1j], [0, 0, 1j, 1], [1, -1j, 0, 0], [-1j, 1, 0, 0]]]
    elif name == "MAGIC":
        m = [[v / math.sqrt(2) for v in row] for row in
             [[1, 1j, 0, 0], [0, 0, 1j, 1], [0, 0, 1j, -1], [1, -1j, 0, 0]]]
    elif name in ("CZS", "CCZS"):
        t, p, g = parameters
        e, c, s = exp(1j * g), math.cos(t / 2), math.sin(t / 2)
        m = [[1, 0, 0, 0], [0, c*c - e*s*s, (1+e)*exp(-1j*p)*s*c, 0],
             [0, (1+e)*exp(1j*p)*s*c, s*s - e*c*c, 0], [0, 0, 0, -e]]
        if name == "CCZS":
            m = _controlled(m)
    elif name == "DEUTSCH":
        t = parameters[0]
        m = _controlled(_controlled([[1j * math.cos(t), math.sin(t)], [math.sin(t), 1j * math.cos(t)]]))
    elif name == "MARGOLUS":
        m = gate_matrix("CCX")
        m[5][5] = -1
    else:
        raise ValueError(f"Missing reference for {name}")
    return adjoint(m) if inverse else m


def _sqrt_unitary(u):
    det = u[0][0] * u[1][1] - u[0][1] * u[1][0]
    s = cmath.sqrt(det)
    if abs(u[0][0] + u[1][1] + 2*s) < 1e-10:
        s = -s
    d = cmath.sqrt(u[0][0] + u[1][1] + 2*s)
    return [[(u[i][j] + s * (i == j)) / d for j in range(2)] for i in range(2)]


def _euler(u):
    theta = 2 * math.atan2(abs(u[1][0]), abs(u[0][0]))
    if abs(u[1][0]) < 1e-12:
        delta, phi, lam = cmath.phase(u[0][0]), 0, cmath.phase(u[1][1]) - cmath.phase(u[0][0])
    elif abs(u[0][0]) < 1e-12:
        delta, phi, lam = 0, cmath.phase(u[1][0]), cmath.phase(-u[0][1])
    else:
        delta = cmath.phase(u[0][0])
        phi, lam = cmath.phase(u[1][0]) - delta, cmath.phase(-u[0][1]) - delta
    return delta + (phi + lam) / 2, theta, phi, lam


def decompose_gate(op):
    """Return only Superpose/Phase/Flip operations; preserve exact global phase.

    Named gates have intrinsic controls in their ordered targets. Additional
    quantum guards are rejected (use primitive predicates); classical guards
    apply to every emitted primitive, including temporary basis changes.
    """
    from psi_lang import PsiOperation

    name = validate_gate(op.gate, op.targets, op.parameters)
    if op.predicate:
        raise ValueError("Use intrinsic controlled gates or primitive where predicates with Gate")
    result = []
    reg, pi = op.register, math.pi

    def emit(kind, targets=(), angle=0.0, controls=()):
        predicate = " && ".join(f"{reg}[{q}] == {v}" for q, v in controls) or None
        result.append(PsiOperation(kind, reg, list(targets), angle=angle, predicate=predicate, when=op.when))

    def phase(angle, controls=()):
        emit("phase", angle=angle, controls=controls)

    def x(q, controls=()):
        emit("flip", (q,), controls=controls)

    def h(q):
        emit("superpose", (q,))

    def rz(q, angle):
        phase(-angle / 2)
        phase(angle, ((q, 1),))

    def rx(q, angle):
        h(q); rz(q, angle); h(q)

    def ry(q, angle):
        phase(-pi / 2, ((q, 1),)); rx(q, angle); phase(pi / 2, ((q, 1),))

    def unitary(u, target, controls=()):
        if len(controls) > 1:
            # Barenco recursion: controlled sqrt(U), compute/uncompute parity.
            c, rest = controls[0], controls[1:]
            v = _sqrt_unitary(u)
            unitary(v, target, rest)
            x(rest[-1], tuple((q, 1) for q in controls[:-1]))
            unitary(adjoint(v), target, rest)
            x(rest[-1], tuple((q, 1) for q in controls[:-1]))
            unitary(v, target, controls[:-1])
            return
        alpha, theta, phi, lam = _euler(u)
        if not controls:
            rz(target, lam); ry(target, theta); rz(target, phi); phase(alpha)
        else:
            c = controls[0]
            rz(target, (lam - phi) / 2)
            x(target, ((c, 1),))
            rz(target, -(lam + phi) / 2); ry(target, -theta / 2)
            x(target, ((c, 1),))
            ry(target, theta / 2); rz(target, phi)
            phase(alpha, ((c, 1),))

    def interaction(a, b, axes, angle):
        if axes == "XY":
            interaction(a, b, "XX", angle / 2); interaction(a, b, "YY", angle / 2)
            return
        for q, axis in zip((a, b), axes):
            if axis == "Y": phase(-pi / 2, ((q, 1),))
            if axis in "XY": h(q)
        x(b, ((a, 1),)); rz(b, angle); x(b, ((a, 1),))
        for q, axis in zip((a, b), axes):
            if axis in "XY": h(q)
            if axis == "Y": phase(pi / 2, ((q, 1),))

    def swap(a, b, controls=()):
        x(b, controls + ((a, 1),)); x(a, controls + ((b, 1),)); x(b, controls + ((a, 1),))

    def odd_block(a, b, u, controls=()):
        x(b, ((a, 1),))
        unitary(u, a, controls + (b,))
        x(b, ((a, 1),))

    t = op.targets
    p = op.parameters
    if GATES[name].qubits == 1:
        q = t[0]
        if name == "I": pass
        elif name == "H": h(q)
        elif name == "X": x(q)
        elif name == "GLOBALPHASE": phase(p[0])
        elif name in ("P", "Z", "S", "T", "SDG", "TDG"):
            angle = p[0] if name == "P" else {"Z": pi, "S": pi/2, "T": pi/4, "SDG": -pi/2, "TDG": -pi/4}[name]
            phase(angle, ((q, 1),))
        elif name in ("RX", "RY", "RZ"):
            {"RX": rx, "RY": ry, "RZ": rz}[name](q, p[0])
        else: unitary(gate_matrix(name, *p), q)
    elif name in ("CX", "ACX", "CCX"):
        x(t[-1], tuple((q, 0 if name == "ACX" else 1) for q in t[:-1]))
    elif name in ("CZ", "CS", "CP", "CCZ"):
        angle = p[0] if name == "CP" else (pi/2 if name == "CS" else pi)
        phase(angle, tuple((q, 1) for q in t))
    elif name in ("CY", "CH", "CSX", "CRX", "CRY", "CRZ", "BARENCO", "DEUTSCH"):
        u = gate_matrix(name, *p)
        unitary([row[-2:] for row in u[-2:]], t[-1], tuple(t[:-1]))
    elif name == "DCX":
        x(t[1], ((t[0], 1),)); x(t[0], ((t[1], 1),))
    elif name in ("SWAP", "CSWAP", "CFSWAP", "FSWAP"):
        controls = tuple((q, 1) for q in t[:-2])
        swap(*t[-2:], controls)
        if name in ("CFSWAP", "FSWAP"): phase(pi, tuple((q, 1) for q in t))
    elif name in ("RXX", "RYY", "RZZ", "RXY", "RZX"):
        interaction(*t, name[1:], p[0])
    elif name in ("ISWAP", "SQRTISWAP", "DB", "FSIM", "SYC"):
        angle = {"ISWAP": -pi, "SQRTISWAP": -pi/2, "DB": 3*pi/4, "SYC": pi}.get(name)
        if angle is None: angle = 2*p[0]
        interaction(*t, "XY", angle)
        if name in ("FSIM", "SYC"): phase(-pi/6 if name == "SYC" else -p[1], tuple((q, 1) for q in t))
    elif name in ("SQRTSWAP", "SWAPPOW", "CAN", "B"):
        if name in ("SQRTSWAP", "SWAPPOW"):
            angle = pi * (0.5 if name == "SQRTSWAP" else p[0]) / 2
            angles = (angle, angle, angle)
            phase(angle / 2)
        else:
            abc = (pi/4, pi/8, 0) if name == "B" else p
            angles = tuple(-2*v for v in abc)
        for axes, angle in zip(("XX", "YY", "ZZ"), angles): interaction(*t, axes, angle)
    elif name == "ECR":
        interaction(*t, "ZX", pi/2); x(t[0])
    elif name in ("GIVENS", "CZS", "CCZS"):
        m = gate_matrix("CZS" if name == "CCZS" else name, *p)
        controls = tuple(t[:-2])
        odd_block(*t[-2:], [row[1:3] for row in m[1:3]], controls)
        phase(cmath.phase(m[3][3]), tuple((q, 1) for q in t))
    elif name == "MAGIC":
        a, b = t
        phase(pi/2, ((a, 1),)); phase(pi/2, ((b, 1),)); phase(-pi, ((a, 1), (b, 1)))
        swap(a, b); h(a); x(b, ((a, 1),))
    elif name in ("MARGOLUS", "PERES"):
        a, b, c = t
        x(c, ((a, 1), (b, 1)))
        if name == "PERES": x(b, ((a, 1),))
        else: phase(pi, ((a, 1), (b, 0), (c, 1)))
    else:
        raise ValueError(f"Missing synthesis for {name}")
    if op.inverse:
        result = [replace(s, angle=-s.angle) if s.kind == "phase" else s for s in reversed(result)]
    return result
