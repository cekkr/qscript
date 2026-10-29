# Gate and matrix reference

The implemented catalog covers every qubit-gate table row in the
[requested list](https://en.wikipedia.org/wiki/List_of_quantum_logic_gates)
([reviewed revision](https://en.wikipedia.org/w/index.php?title=List_of_quantum_logic_gates&oldid=1375005600)).
Hyperlinked hardware procedures and higher-dimensional qudit generalizations are
not additional simulated hardware models. All entries are ideal logical unitaries.

`quantum_gates.py` provides a standard-library analytic `gate_matrix(name, *params)`
and a separate `decompose_gate(operation)` implementation. Every named gate
expands into **Superpose, Phase, and Flip**. Reflect remains the mean-reflection
primitive. `Turn`, `Interact`, and `Gate` are readable conveniences, not new
irreducible instructions or pulse operations. Parameter angles are radians.
For an introduction without assumed quantum background and explicit sequences
in execution order, see the [manual's primitive recipes](../qscript-Definition.md#7-reading-primitive-recipes).

## Operands, phases, and usage

```psi
let q = Register(3);
q.Gate(name: U, target: 0, theta: PI/2, phi: PI/3, lambda: -PI/4);
q.Turn(axis: Y, target: 2, angle: PI/7);
q.Interact(axes: XX, targets: [0, 2], angle: PI/2);
q.Gate(name: CAN, targets: [2, 1], params: [PI/8, PI/9, PI/10]);
q.Gate(name: CCX, targets: [2, 0, 1], inverse: true);
```

Direct method aliases such as `q.RXX(targets: [0,2], angle: PI/2)` also work.
Use either named parameters or `params: [...]` in the table's parameter order.
Single-parameter gates also accept `angle:` in place of their parameter name.
All gates accept `inverse: true` for the conjugate transpose and a classical
`when:`. Intrinsic controls occupy the leading operands; extra `where:` on
named gates is rejected. Use primitive predicates for quantum control.

- Register amplitude index `i` represents `|q[n-1] ... q[0]>`; **q0 is the low bit**.
- Local gate matrices use `|targets[0] ... targets[-1]>`: the **first operand is
  the most significant local bit**. Thus CX `[0,2]` controls q0 and targets q2.
  Applying a local matrix embeds it into the register with this explicit mapping.
- `Phase(angle: a, where: predicate)` multiplies matching amplitudes by `exp(ia)`.
  Without `where`, it multiplies **the entire state** by `exp(ia)`. This fixes the
  former viewer/compiler disagreement. For `diag(1, exp(ia))`, use P or `where: q[i]`.
- P(a) and RZ(a) differ by a global phase. Exact simulation and reference
  comparison retain it. OpenQASM 2 omits global phases with explicit comments;
  QASM equivalence tests permit one common phase across the whole matrix.
- FSIM uses Google's convention `diag(..., exp(-i phi))`. The reviewed list's
  FSIM row has `exp(+i phi)`, inconsistent with its Sycamore row. To reproduce
  that FSIM row, negate `phi`. SYC = FSIM(PI/2, PI/6).
- ECR uses the displayed matrix below, with the first operand on the left of
  tensor products. IBM's default little-endian argument ordering prints the
  bit-permuted matrix; compare operand order before comparing arrays.
- M means **MAGIC**. The simplified Toffoli is MARGOLUS/RCCX. The RCCX alias
  uses the real Margolus matrix below; other libraries can choose different
  relative phases for a relative-phase Toffoli.

## Complete catalog

| Names (canonical first) | Qubits | Parameters, in order | Definition |
| --- | ---: | --- | --- |
| I / ID / IDENTITY | 1 | — | Identity |
| GLOBALPHASE / PH / PHASE | 1 | angle | exp(i angle) I |
| X / NOT; Y; Z | 1 | — | Pauli operators |
| H / HADAMARD | 1 | — | Hadamard |
| S / SQRTZ; T | 1 | — | P(PI/2); P(PI/4) |
| SX / V / SQRTX / SQRTNOT | 1 | — | Principal square root of X |
| P / PHASESHIFT / U1 | 1 | angle | diag(1, exp(i angle)) |
| RX; RY; RZ | 1 | angle | exp(-i angle Pauli/2) |
| U / U3 | 1 | theta, phi, lambda | General single-qubit matrix below |
| CX / CNOT / XOR | 2 | — | Controlled X |
| ACX / C0X / ANTICNOT / XNOR | 2 | — | X on second operand when first is 0 |
| CZ / CPF / CSIGN | 2 | — | diag(1,1,1,-1) |
| DCX / DCNOT | 2 | — | CX(a,b), then CX(b,a); not Toffoli |
| SWAP | 2 | — | Exchange both bits |
| ISWAP | 2 | — | Exchange 01 and 10 with factor +i |
| CP / CPHASE / CR | 2 | angle | diag(1,1,1,exp(i angle)) |
| CS | 2 | — | CP(PI/2) |
| RXX / XX; RYY / YY; RZZ / ZZ | 2 | angle | Pauli-pair interaction |
| RXY / XY | 2 | angle | exp[-i angle (XX+YY)/4], **not** exp(-i angle X⊗Y/2) |
| SQRTSWAP | 2 | — | SWAPPOW(1/2) |
| SQRTISWAP | 2 | — | RXY(-PI/2) |
| SWAPPOW / SWAPALPHA | 2 | alpha | SWAP raised to a real power |
| CSWAP / FREDKIN | 3 | — | Controlled SWAP |
| BARENCO | 2 | alpha, phi, theta | Controlled equatorial rotation with phase |
| B / BERKELEY | 2 | — | CAN(PI/4, PI/8, 0) |
| CSX / CV | 2 | — | Controlled SX |
| CAN / N | 2 | a, b, c | exp[i(a XX + b YY + c ZZ)] |
| DB / DAGWOOD | 2 | — | RXY(3 PI/4) |
| ECR | 2 | — | Echoed cross-resonance matrix below |
| FSIM | 2 | theta, phi | Exchange angle theta and negative conditional phase phi |
| GIVENS / G | 2 | angle | Real rotation in the 01/10 subspace |
| MAGIC / M | 2 | — | Magic-basis transformation below |
| SYC / SYCAMORE | 2 | — | FSIM(PI/2, PI/6) |
| CZS | 2 | theta, phi, gamma | CZ-SWAP matrix below |
| DEUTSCH / D | 3 | theta | Controlled-controlled [i cos(theta) I + sin(theta) X] |
| MARGOLUS / RCCX | 3 | — | CCX with an additional minus sign on input 101 |
| PERES / PG | 3 | — | CCX(a,b,c), then CX(a,b) |
| CCX / CCNOT / TOFFOLI / TOFF | 3 | — | Controlled-controlled X |
| CFSWAP / FFREDKIN | 3 | — | Controlled fermionic SWAP; 111 acquires -1 |

Additional useful entries: SDG, TDG, SXDG; CY, CH, CRX, CRY, CRZ; CCZ;
RZX(angle) = exp(-i angle Z⊗X/2); FSWAP; and CCZS(theta,phi,gamma),
which is controlled CZS. `inverse: true` works for every entry.

## Mathematical definitions

Let c = cos(theta/2), s = sin(theta/2).

```text
X = [0 1]    Y = [0 -i]    Z = [1  0]    H = 1/sqrt(2) [1  1]
    [1 0]        [i  0]        [0 -1]                  [1 -1]

U(theta,phi,lambda) = [c                  -exp(i lambda) s       ]
                      [exp(i phi) s       exp(i(phi+lambda)) c   ]

SX = 1/2 [1+i  1-i]
         [1-i  1+i]
```

Controlled U is `I ⊕ U`, with the control as the first operand.
BARENCO's active block is
`exp(i alpha) [[cos(theta), -i exp(-i phi) sin(theta)],
               [-i exp(i phi) sin(theta), cos(theta)]]`.
DEUTSCH's active 2×2 block acts only when its first two operands equal 1.
Controlled arbitrary blocks use an Euler decomposition and controlled square-root
recursion; see [Barenco et al.](https://arxiv.org/abs/quant-ph/9503016).

For A in X,Y,Z, `RAA(t) = cos(t/2) I₄ - i sin(t/2) A⊗A`.
RXX and RYY are basis changes around a parity-compute → RZ → uncompute
network. RXY(t) = RXX(t/2) RYY(t/2). These angles are important:
RXX(PI/2)|00> = (|00> - i|11>)/sqrt(2), whereas RXY preserves excitation
number. [IBM's RXX definition](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.circuit.library.RXXGate)
uses the same half-angle normalization.

CAN(a,b,c) = RXX(-2a) RYY(-2b) RZZ(-2c). The three generators commute.
The B gate is the special choice above; see
[Zhang et al.](https://arxiv.org/abs/quant-ph/0312193).
With E = exp(i PI alpha), SWAPPOW's 01/10 block has diagonal (1+E)/2
and off-diagonal (1-E)/2, while 00 and 11 remain unchanged. Its synthesis
is `exp(i PI alpha/4)` times RXX, RYY and RZZ, each at PI alpha/2.

```text
ECR = 1/sqrt(2) [ 0   0  1  i]    MAGIC = 1/sqrt(2) [1  i  0  0]
                [ 0   0  i  1]                      [0  0  i  1]
                [ 1  -i  0  0]                      [0  0  i -1]
                [-i   1  0  0]                      [1 -i  0  0]
```

ECR = (X⊗I) RZX(PI/2) in this operand order.
[IBM's ECR reference](https://quantum.cloud.ibm.com/docs/api/qiskit/qiskit.circuit.library.ECRGate)
explains its ordering convention. GIVENS(t) is identity on 00 and 11, with
01/10 block `[[cos(t), -sin(t)], [sin(t), cos(t)]]`.

FSIM(theta,phi) has the same fixed 00 state, 01/10 block
`[[cos(theta), -i sin(theta)], [-i sin(theta), cos(theta)]]`, and 11 entry
`exp(-i phi)`, following [Google's definition](https://quantumai.google/reference/python/cirq/FSimGate).

For CZS, let c = cos(theta/2), s = sin(theta/2), E = exp(i gamma).
The 00 entry is 1, the 11 entry is -E, and the 01/10 block is
`[[c²-E s², (1+E) exp(-i phi) s c],
  [(1+E) exp(i phi) s c, s²-E c²]]`.
CCZS = I₄ ⊕ CZS; CFSWAP = CCZS(PI/2,0,0). See
[Gu et al.](https://arxiv.org/abs/2108.11358).

## Viewer mathematics and comparison

The simulator evolves named gates through their primitive decomposition.
Separately, it embeds the analytic local matrix and compares its predicted
state. The matrix panels compare the entire local operator, not just its action
on |0>. They toggle between real and imaginary parts; JSON reports retain both.
`--unitary` compares full reference and primitive circuit matrices (up to eight
qubits) and compares equal-sized supplied circuits, including a comparison up
to global phase. Measurements, classical guards, and pulse annotations do not
define a single circuit unitary and are rejected by that option.

The diagnostic workbench (`--view workbench`) uses discrete basis bars: probability is |amplitude|²,
and color is phase. W switches to signed real/imaginary amplitudes. These are
register amplitudes, not a physical spatial wavefunction. The standalone
`wave_viewer.py` remains an analytic spatial teaching model.

For selected wires A, the reduced state is `rho_A = Tr_rest |psi><psi|`.
The Bloch vector is `(Tr(rho X), Tr(rho Y), Tr(rho Z))`, so a locally mixed
entangled qubit can have zero Bloch-vector length. Purity is Tr(rho²), entropy
is `-sum(lambda log2 lambda)`, and the correlation panel shows
`<Pauli_A Pauli_B> - <Pauli_A><Pauli_B>`.

Pair concurrence uses the ordered square roots of eigenvalues of
`rho (Y⊗Y) rho* (Y⊗Y)`: `max(0, r1-r2-r3-r4)`, following
[Wootters](https://arxiv.org/abs/quant-ph/9709029).
Mutual information is S(A)+S(B)-S(AB). Correlation or a mixed local state alone
does not establish pair entanglement: a reduced GHZ pair has concurrence zero
despite classical correlation. Values near zero/one have floating-point error.

Measurement follows `p_m = <psi|P_m|psi>` and updates the selected trajectory
to `P_m|psi>/sqrt(p_m)`. Its panel retains the probabilities **before** collapse;
the wavefunction/density panels show the state **after** collapse. The matrix
panels show the sampled projector and the resulting reduced state (up to eight
dimensions). Independent shots rerun the entire circuit, including mid-circuit
outcomes and corrections.
For branch-dependent circuits, the displayed exact pre-measurement probabilities
belong to this trajectory, whereas shot bars aggregate all trajectories.

## Validation and limits

The standard-library suite tests every reference's unitarity, exact primitive
expansion, parameter edge cases, adjoints and emitted QASM equivalence (one
overall phase allowed), using a small independent qelib instruction evaluator.
Optional NumPy tests cover arbitrary states, nonadjacent/reversed operands,
Bell/GHZ reductions, QFT versus the DFT matrix, collapse, seeded shots, and
feed-forward. Agg rendering tests exercise viewer callbacks and exports.
There is no external QASM conformance/hardware test or synthesis-cost optimum.

One selected register is simulated at a time; cross-register controls are
rejected. Statevectors and snapshots use exponential memory. Plots show at most
128 basis bars and 16 probability outcomes, labeled when truncated; reports
retain the full distributions. Pulse envelopes, noise, calibration, entangling
pulse physics, and live hardware remain outside this ideal logic simulator.

## Continuous wave lens

The circuit viewer defaults to `--view waves`: before/during/after continuous
3D surfaces with a gate-fraction slider and Play/pause. `--wave-mode real` or
`imaginary` shows signed wave amplitudes; density is the default. Use
`--view workbench` for the diagnostic panels described above.
The wave encoding uses Gaussian phi0 and first Hermite phi1 modes:
Psi(x,y) = sum_ab c_ab phi_a(x) phi_b(y), in selected operand order.
These orthonormal coordinates illustrate interference and entanglement; they
are not hardware position or microwave fields. Mixed reductions display the
density kernel diagonal instead of a fabricated pure wavefunction. Gate
interpolation uses principal eigenphases of the ideal unitary; measurements
jump at fraction 1 and pulse annotations remain unchanged.
See the README screenshots and `assets/generate_screenshots.py` for reproducible
XX, XY, phase and measurement examples; `qscripts/wave_interference.psi` gives
a phase-tag/decode circuit (H Z H = X) followed by exchange.
