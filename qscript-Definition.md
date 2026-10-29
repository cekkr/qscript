# qscript v1.2 — Language and Learning Manual

qscript describes a quantum computation in two views. The **logic layer** says
how to change a quantum state. The **analog layer** records timed instructions
for a physical wire, such as a rotation lasting 20 nanoseconds. The tools in this
repository implement an ideal logic simulator and an experimental compiler and
pulse scheduler. A pulse description does not execute hardware.

This manual starts with the ideas needed to read a program, then explains how
named gates become sequences of small primitives. You can use the language
without learning every matrix formula. The later recipe sections supply those
formulas when you want to understand or reproduce a gate.

## Contents

1. [A first program, line by line](#1-a-first-program-line-by-line)
2. [States, amplitudes, probability and phase](#2-states-amplitudes-probability-and-phase)
3. [Registers, order and syntax](#3-registers-order-and-syntax)
4. [The four logic primitives](#4-the-four-logic-primitives)
5. [Quantum controls and classical conditions](#5-quantum-controls-and-classical-conditions)
6. [Calling named gates](#6-calling-named-gates)
7. [Reading primitive recipes](#7-reading-primitive-recipes)
8. [Single-qubit gate recipes](#8-single-qubit-gate-recipes)
9. [Two-qubit interactions, step by step](#9-two-qubit-interactions-step-by-step)
10. [Controlled gates, swaps and three-qubit gates](#10-controlled-gates-swaps-and-three-qubit-gates)
11. [The remaining named gates](#11-the-remaining-named-gates)
12. [How arbitrary controlled rotations reach the primitives](#12-how-arbitrary-controlled-rotations-reach-the-primitives)
13. [Measurement and repeated experiments](#13-measurement-and-repeated-experiments)
14. [Reading the 3D wave viewer](#14-reading-the-3d-wave-viewer)
15. [The analog layer and time](#15-the-analog-layer-and-time)
16. [Compilation, numerical comparison and current limits](#16-compilation-numerical-comparison-and-current-limits)

## 1. A first program, line by line

Save this as a `.psi` file:

```psi
let pair = Register(2);
pair.Superpose(targets: 0);
pair.Flip(target: 1, where: pair[0] == 1);
let result = pair.Measure();
```

`Register(2)` creates two qubits, numbered 0 and 1. They start in state `|00>`.
A **qubit** has two computational basis states, written `|0>` and `|1>`. A
**register** groups qubits into one joint quantum state. The notation `|...>`
(called a *ket*) labels a state; it is not a comparison or a string literal.

`Superpose(targets: 0)` changes qubit 0 from `|0>` into
`(|0> + |1>)/sqrt(2)`. For the whole register, this gives
`(|00> + |01>)/sqrt(2)`. The factor `1/sqrt(2)` makes each of the two outcomes
have probability one half.

`Flip(target: 1, where: pair[0] == 1)` exchanges 0 and 1 on qubit 1 only in
the part of the state where qubit 0 is 1. It changes `|01>` into `|11>`, while
leaving `|00>` alone. The resulting joint state is
`(|00> + |11>)/sqrt(2)`, a **Bell state**.

The qubits are now **entangled**: this joint state cannot be written as an
independent state for qubit 0 multiplied by an independent state for qubit 1.
Measuring the whole register returns either integer 0 (`00`) or integer 3
(`11`), each with probability one half. It never returns `01` or `10` in this
ideal example. One run gives one result, not both results.

Run the existing version of this example with:

```sh
python3 -m pip install -r requirements-viewer.txt
python3 viewer-references/psi_interference_viewer.py qscripts/bell_pair.psi --step 2 --seed 1
```

The viewer starts after the second operation. Use Previous/Next to follow the
program, or Play/pause to explore the selected gate's intermediate wave shapes.

## 2. States, amplitudes, probability and phase

### An amplitude is not a probability

A single-qubit pure state can be written as:

```text
|psi> = alpha |0> + beta |1>
|alpha|² + |beta|² = 1
```

`alpha` and `beta` are **amplitudes**: numbers that can have a real part and an
imaginary part. The imaginary unit `i` satisfies `i² = -1`. For a number
`z = x + i y`, its squared magnitude is `|z|² = x² + y²`.

Measurement probabilities are squared magnitudes. If `alpha = 1/sqrt(2)` and
`beta = -i/sqrt(2)`, both outcomes still have probability one half. A negative
or imaginary amplitude is not a negative or imaginary probability.

For two qubits there are four amplitudes, one for each of `00`, `01`, `10`,
and `11`. N qubits require `2**N` amplitudes in the classical simulator. This
list is the **statevector**. The sum of its squared magnitudes must be 1;
this condition is called **normalization**.

### Phase matters when amplitudes meet

An amplitude's **phase** is its angle in the complex plane. Multiplication by
`exp(i theta)` turns that angle by `theta` radians without changing magnitude.
Here `exp` denotes the exponential function. A full turn is `2*PI` radians;
`PI` is half a turn. Useful values are:

| Multiplier | Angle | Effect on an amplitude |
| --- | --- | --- |
| `1` | 0 | Leave it unchanged. |
| `i` | `PI/2` | Turn its phase by a quarter turn. |
| `-1` | `PI` | Reverse its sign. |
| `-i` | `-PI/2` | Turn it by a quarter turn in the opposite direction. |

The states `(|0> + |1>)/sqrt(2)` and `(|0> - |1>)/sqrt(2)` have the same
immediate measurement probabilities. Apply Superpose again, however, and the
first becomes `|0>` while the second becomes `|1>`. Amplitudes add before
probabilities are calculated: equal signs reinforce, opposite signs cancel.
This is **interference**.

```psi
let q = Register(1);
q.Superpose(targets: 0);
q.Phase(angle: PI, where: q[0] == 1);
q.Superpose(targets: 0);
let result = q.Measure(); // always 1 in this ideal experiment
```

The Phase operation changes a relative sign, not the probabilities at that
step. The following Superpose makes the sign difference observable.

A **global phase** multiplies every amplitude by the same `exp(i theta)`.
It changes no relative phases and cannot change measurement predictions. A
**relative phase** changes some amplitudes compared with others. The simulator
retains global phase so exact numerical matrix comparisons remain meaningful.

### What a gate matrix means

A **gate** is a reversible transformation of quantum amplitudes. Its matrix
multiplies the statevector. For example, X has matrix `[[0,1],[1,0]]`: it swaps
the amplitudes of `|0>` and `|1>`. A **unitary** matrix preserves normalization
and has an inverse. Its **adjoint**, written `U†`, is its complex-conjugate
transpose; for a unitary gate, `U†` undoes U.

In a matrix, each column tells you what happens to one input basis state.
A diagonal matrix such as `diag(1, i)` leaves the `|0>` amplitude alone and
multiplies the `|1>` amplitude by i. No amplitude moves between those states.
A gate acting on several wires uses a larger matrix for their joint state.

## 3. Registers, order and syntax

`let reg = Register(N)` requires a positive literal integer. A wire index starts
at zero: a three-qubit register has wires 0, 1, and 2. `reg[0]` inside a quantum
predicate refers to the bit value of a basis-state label. It does not secretly
measure that wire.

Register bitstrings print the highest-numbered wire on the left:

| Printed state of three wires | q2 | q1 | q0 | Integer |
| --- | ---: | ---: | ---: | ---: |
| `001` | 0 | 0 | 1 | 1 |
| `100` | 1 | 0 | 0 | 4 |
| `101` | 1 | 0 | 1 | 5 |

Thus **q0 is the least significant bit**. This explains why the first program's
Superpose on q0 produced `00` and `01`, rather than `00` and `10`.

Named-gate matrices have a separate **operand order**. In
`q.Gate(name: CX, targets: [0,2])`, the first operand is the control, q0;
the second is the target, q2. Its local matrix uses basis `|q0 q2>`, while the
full register still prints `|q2 q1 q0>`. The tools embed the local matrix into
the register using that mapping. Operand order matters even when indices are
not adjacent.

Calls use `key: value` arguments. Semicolons are optional; calls can span lines.
`//` starts a comment outside a string. Angles accept arithmetic with `PI`,
`pi`, or `tau` (`tau = 2*PI`). For example, `-PI/4` means minus one eighth of a
full turn. All logic angles are in radians.

The tools process one selected register at a time: the first declaration by
default, or `--register name`. Multiple declarations do not establish a joint
state between registers. Cross-register quantum controls are rejected.

## 4. The four logic primitives

A **primitive** is a small operation used to express other operations. qscript's
logic vocabulary has four primitives. The named-gate catalog uses just the first
three below; Reflect remains a convenient whole-register interference operation.

### Superpose: mix the two amplitudes of a wire

```psi
let q = Register(2);
q.Superpose(targets: 0);
q.Superpose(targets: [0, 1]);
q.Superpose(targets: ALL);
```

On each selected wire, Superpose applies the **Hadamard** gate H:

```text
input |0> -> (|0> + |1>)/sqrt(2)
input |1> -> (|0> - |1>)/sqrt(2)
```

Its effect depends on the incoming state. It does not always create an equal
probability distribution: two applications on the same wire cancel each other.
`ALL` means every wire in this register; a list applies H separately to each
listed wire, without automatically coupling them.

### Phase: turn selected amplitudes without moving them

```psi
let q = Register(2);
q.Phase(angle: PI/2, where: q[0] == 1);
q.Phase(angle: PI, where: q[0] == 1 && q[1] == 1);
q.Phase(angle: PI/3); // global phase: all amplitudes turn together
```

The first call multiplies amplitudes whose q0 bit is 1 by i. The second changes
the sign of the `11` amplitude only. Neither call changes the computational-basis
probabilities immediately. Without `where`, Phase affects the whole state.

In particular, `Phase(angle: t, where: q[a] == 1)` is the phase-shift gate
P(t), not exactly RZ(t). Their relative action is the same, but they differ
by a global phase. Section 8 includes the extra global phase needed for exact RZ.

### Flip: exchange pairs of basis-state amplitudes

```psi
let q = Register(3);
q.Flip(target: 1);
q.Flip(target: 1, where: q[0] == 1);
q.Flip(target: 2, where: q[0] == 1 && q[1] == 1);
```

An unconditional Flip is X: exchange 0 and 1 on the target wire. With a quantum
condition it performs that exchange only in the selected part of the state.
The second example is CX (controlled X); the third is CCX (Toffoli).

The condition must remain true or false when the target flips. A condition on
other wires satisfies this requirement. `Flip(target: 0, where: q[0] == 0)`
does not: it would try to merge two distinct inputs into one output and would
not be a reversible gate. The simulator rejects such a transformation.

### Reflect: turn a phase pattern into a new amplitude pattern

```psi
let q = Register(2);
q.Superpose(targets: ALL);
q.Phase(angle: PI, where: q[0] == 1 && q[1] == 1);
q.Reflect(axis: Axis.MEAN);
```

Reflect computes the mean of all register amplitudes and replaces each amplitude
`a` with `2*mean - a`. The mean is a complex amplitude, not an average of
probabilities. Only `Axis.MEAN` is implemented.

In this example the amplitudes before tagging are `[1/2,1/2,1/2,1/2]`.
Tagging `11` gives `[1/2,1/2,1/2,-1/2]`, whose mean is `1/4`.
Reflection gives `[0,0,0,1]`: measurement would now find `11` with certainty.
This exact two-qubit example explains the mechanism; it is not a promise that
one reflection solves arbitrary search problems.

## 5. Quantum controls and classical conditions

A **control** decides when an operation acts. qscript distinguishes two kinds:

| Form | What it reads | What happens |
| --- | --- | --- |
| `where: q[0] == 1` | A basis-state bit, coherently across the quantum state | Apply the operation to the selected amplitudes; do not measure. |
| `when: bit == 1` | A stored classical integer, usually from measurement | Apply or skip the entire operation for this run. |

`&&` means AND, `||` means OR, `!` means NOT, `==` means equals, and `!=`
means differs from. The ideal simulator evaluates these Boolean predicates.
OpenQASM export supports a narrower quantum form: conjunctions such as
`q[0] == 1 && q[2] == 0` (or a truthy `q[0]`). It rejects unsupported predicates
rather than silently changing their meaning.

Classical OpenQASM guards must be `measured_register == nonnegative_integer`,
where the integer fits the measured register. The ideal simulator supports
broader classical Boolean expressions. Use measured names explicitly: missing
classical names currently evaluate as zero in the simulator.

All four primitives accept a classical `when:`. When a named gate expands into
many primitives, its guard applies to every step, including temporary basis
changes and their undo operations. Otherwise a skipped gate could still change
the state.

## 6. Calling named gates

```psi
let q = Register(3);
q.Gate(name: U, target: 0, theta: PI/2, phi: 0, lambda: PI/4);
q.Turn(axis: Y, target: 2, angle: PI/3);
q.Interact(axes: XX, targets: [0, 2], angle: PI/2);
q.Gate(name: CAN, targets: [2, 1], params: [PI/8, PI/9, PI/10]);
q.Gate(name: CCX, targets: [0, 1, 2], inverse: true);
```

`Gate` selects a named transformation. `target:` supplies one wire;
`targets: [...]` supplies an ordered list of distinct wires. Required numeric
parameters must be finite. Use their names or a `params: [...]` list in the
order given in the [complete catalog](explain/gate-reference.md#complete-catalog).
Single-parameter gates also accept `angle:` in place of their parameter name.

`Turn(axis: X|Y|Z, ...)` is shorthand for a logical RX, RY or RZ gate. The axes
label three different ways to mix amplitudes and phase; the recipes below define
them precisely. `Interact(axes: XX|YY|ZZ|XY|ZX, ...)` is shorthand for a two-wire
interaction. These calls add no new irreducible primitive and have no duration.

Direct named methods also work: `q.RXX(targets: [0,2], angle: PI/2)` is equivalent
to `q.Gate(name: RXX, targets: [0,2], angle: PI/2)`. The original method
`q.Phase(...)` keeps its predicate-based meaning; to select the named global
phase entry explicitly, use `Gate(name: GLOBALPHASE, ...)`.

`inverse: true` asks for the inverse transformation. Intrinsic controls occupy
the leading operands, as in CX `[control,target]` and CCX
`[control1,control2,target]`. Named gates reject extra `where:` arguments;
use the named controlled version or the primitive recipes. Logic calls belong
outside `Analog` scopes.

## 7. Reading primitive recipes

Every arrow below means **do the left operation first, then the right one**.
This is execution order, like lines in a program. In conventional matrix
notation, `A → B` corresponds to the product `B A`, because matrices act on
column vectors from the right. Confusing these orders changes a gate.

The letters a, b and c below stand for wire indices, not classical result names.
The following abbreviations are explanatory notation, **not additional qscript
functions or supported macro definitions**:

| Recipe notation | Actual qscript primitive |
| --- | --- |
| `H(a)` | `q.Superpose(targets: a)` |
| `X(a)` | `q.Flip(target: a)` |
| `P(a,t)` | `q.Phase(angle: t, where: q[a] == 1)` |
| `G(t)` | `q.Phase(angle: t)` — global phase |
| `CX(a,b)` | `q.Flip(target: b, where: q[a] == 1)` |
| `CP(a,b,t)` | `q.Phase(angle: t, where: q[a] == 1 && q[b] == 1)` |
| `CCX(a,b,c)` | `q.Flip(target: c, where: q[a] == 1 && q[b] == 1)` |

Replace symbolic indices and angles with actual values when writing a program.
Longer recipes use RX, RY, RZ, interactions and SWAP as intermediate shorthand;
the following sections expand each one down to this table. There is no hidden
hardware operation at the end of the chain.

Recipes are **exact, including global phase**, unless a difference is explicitly
stated. Some are shorter equivalent sequences than the current synthesizer's
Euler-based output. To inspect the exact emitted primitive records, use:

```python
from psi_lang import PsiOperation
from quantum_gates import decompose_gate

operation = PsiOperation("gate", "q", [0, 1], gate="RXX", parameters=[0.7])
for step in decompose_gate(operation):
    print(step.kind, step.targets, step.angle, step.predicate)
```

This Python helper requires only the standard library. It describes a gate on
register q; it does not create or run a register. The exact primitive count is
an implementation detail, not a promise of optimal synthesis.

## 8. Single-qubit gate recipes

### Fixed gates and phase shifts

| Gate | Sequence in execution order | Practical meaning |
| --- | --- | --- |
| I | Empty sequence | Do nothing. |
| GLOBALPHASE(t) | `G(t)` | Turn every amplitude by the same phase. |
| H | `H(a)` | Mix the two amplitudes with a relative minus sign on one branch. |
| X | `X(a)` | Exchange the amplitudes of 0 and 1. |
| Y | `P(a,PI) → X(a) → G(PI/2)` | Exchange them with factors +i and -i. |
| Z | `P(a,PI)` | Reverse the sign of the 1 amplitude. |
| P(t) | `P(a,t)` | Turn only the 1 amplitude by t. |
| S | `P(a,PI/2)` | A quarter-turn phase shift; applying it twice gives Z. |
| T | `P(a,PI/4)` | An eighth-turn phase shift; applying it twice gives S. |
| SDG | `P(a,-PI/2)` | Undo S. |
| TDG | `P(a,-PI/4)` | Undo T. |
| SX | `G(PI/4) → RX(a,PI/2)` | A square root of X: applying it twice gives X. |
| SXDG | `RX(a,-PI/2) → G(-PI/4)` | Undo SX. |

“Square root” here means composition: two applications equal the original gate.
It does not mean taking the square root of each matrix entry.

### Rotations from phase and superposition

```text
RZ(a,t): G(-t/2) → P(a,t)
RX(a,t): H(a) → RZ(a,t) → H(a)
RY(a,t): P(a,-PI/2) → RX(a,t) → P(a,PI/2)
```

RZ multiplies the 0 amplitude by `exp(-i t/2)` and the 1 amplitude by
`exp(+i t/2)`. That explains both the half-angle and the global-phase correction.
RX uses H to express that same phase operation in a different basis; the second
H brings the description back. RY adds quarter-turn phase changes around RX.
A **basis change** temporarily expresses the same state using different reference
states, so a simple phase operation can produce a different logical effect.

Here is RZ(PI/3) written entirely with primitives:

```psi
let q = Register(1);
// Equivalent named form: q.Gate(name: RZ, target: 0, angle: PI/3);
q.Phase(angle: -PI/6);
q.Phase(angle: PI/3, where: q[0] == 1);
```

The general single-qubit gate `U(theta,phi,lambda)` has the recipe:

```text
P(a,lambda) → RY(a,theta) → P(a,phi)
```

It has three parameters because it combines amplitude mixing with phase changes
before and after that mixing. Its matrix, with `c = cos(theta/2)` and
`s = sin(theta/2)`, is:

```text
[ c                  -exp(i lambda) s     ]
[ exp(i phi) s        exp(i(phi+lambda)) c ]
```

For example RX(PI/2) takes `|0>` to `(|0> - i|1>)/sqrt(2)`. RX(PI) gives
`-i|1>`, which has the same measurement predictions as X applied to `|0>`,
but carries a different global phase. Keep that phase when comparing matrices.

## 9. Two-qubit interactions, step by step

An interaction acts on a joint state. Applying separate single-qubit gates can
rotate independent qubits, but cannot turn an initially independent pair into
an entangled pair. The two-wire operations below can do so, depending on the
input state and angle. They need not entangle every input.

### ZZ: compute parity, turn phase, undo the bookkeeping

**Parity** tells whether two bits are different. It is 0 for `00` and `11`,
and 1 for `01` and `10`. The ZZ interaction has recipe:

```text
RZZ(a,b,t): CX(a,b) → RZ(b,t) → CX(a,b)
```

The first CX temporarily replaces b with `a XOR b`, storing the parity on b.
RZ then assigns phase `exp(-i t/2)` to even parity and `exp(+i t/2)` to odd
parity. The last CX restores the original basis labels. This restoration is
called **uncomputation**: remove temporary information without measuring it,
while retaining the phase that was applied.

RZZ is not the same as CP. RZZ gives different phases to even and odd parity;
CP changes the `11` amplitude only. They are useful for different operations.

### XX, YY and ZX: the same mechanism in a different basis

| Interaction | Before the RZZ sequence | After the RZZ sequence |
| --- | --- | --- |
| RXX(a,b,t) | `H(a) → H(b)` | `H(a) → H(b)` |
| RYY(a,b,t) | `P(a,-PI/2) → H(a) → P(b,-PI/2) → H(b)` | `H(a) → P(a,PI/2) → H(b) → P(b,PI/2)` |
| RZX(a,b,t) | `H(b)` | `H(b)` |

Read each row as “before → RZZ(a,b,t) → after.” These are temporary basis
changes, not measurements. XX can move amplitude between `00` and `11`, as
well as between `01` and `10`. ZZ itself changes phases without moving basis
population; surrounding basis changes turn that into amplitude mixing.

RXX(PI/2) in actual primitive syntax is:

```psi
let q = Register(2);
// Equivalent named form: q.Gate(name: RXX, targets: [0, 1], angle: PI/2);
q.Superpose(targets: [0, 1]);
q.Flip(target: 1, where: q[0] == 1);
q.Phase(angle: -PI/4);
q.Phase(angle: PI/2, where: q[1] == 1);
q.Flip(target: 1, where: q[0] == 1);
q.Superpose(targets: [0, 1]);
```

Starting at `|00>`, the result is `(|00> - i|11>)/sqrt(2)`. Each qubit measured
alone has a 50/50 distribution, but their joint outcomes are correlated.
The relative -i is phase information that later gates can reveal.

### XY: exchange one excitation between the wires

qscript's XY means the **sum of XX and YY interactions**, not the tensor
product X on one wire and Y on the other:

```text
RXY(a,b,t): RXX(a,b,t/2) → RYY(a,b,t/2)
```

An **excitation** here simply means a 1 in a computational-basis label. XY
leaves `00` and `11` unchanged and mixes `01` with `10`:

```text
|01> -> cos(t/2)|01> - i sin(t/2)|10>
|10> -> cos(t/2)|10> - i sin(t/2)|01>
```

Thus XY(PI/2) turns a single excitation on one wire into an entangled
superposition of the two possible locations. It does not create the `00`/`11`
pair produced by XX acting on `00`.

The mathematical definitions are `RAA(t) = exp(-i t A⊗A/2)` for A = X, Y or
Z, and `RXY(t) = exp[-i t (X⊗X + Y⊗Y)/4]`. The symbol `⊗` combines operators
on different wires into a joint operator. These definitions explain the factors
of 2 and 4; use the recipes if the exponential notation is unfamiliar.

## 10. Controlled gates, swaps and three-qubit gates

### Direct controls

| Gate and operands | Primitive recipe | When it acts |
| --- | --- | --- |
| CX(a,b) | `CX(a,b)` from section 7 | Flip b when a=1. |
| ACX(a,b) | `Flip(target: b, where: q[a] == 0)` | Flip b when a=0. |
| CZ(a,b) | `CP(a,b,PI)` | Change the sign of 11. |
| CS(a,b) | `CP(a,b,PI/2)` | Multiply 11 by i. |
| CP(a,b,t) | `CP(a,b,t)` from section 7 | Turn the phase of 11 by t. |
| CY(a,b) | `P(b,-PI/2) → CX(a,b) → P(b,PI/2)` | Apply Y to b when a=1. |
| CCX(a,b,c), Toffoli | `CCX(a,b,c)` from section 7 | Flip c when both a and b are 1. |
| CCZ(a,b,c) | `Phase(t=PI, where: a=1 AND b=1 AND c=1)` | Change the sign of 111 only. |

The CCZ row uses explanatory condition notation: write actual qscript indexed
names and `&&`, as in the examples. It is one Phase primitive, even though
OpenQASM may need temporary work qubits to implement it. Such work qubits are
called **ancillas**; the compiler restores them to their starting state.

CH, CSX, CRX, CRY and CRZ mean controlled H, SX, RX, RY and RZ. Their general
primitive construction is described in section 12. Replacing a global phase in
an uncontrolled recipe is not enough to create its controlled version: a phase
applied only to the control=1 part becomes a relative phase. It must be retained.

### SWAP and related gates

```text
SWAP(a,b): CX(a,b) → CX(b,a) → CX(a,b)
DCX(a,b):  CX(a,b) → CX(b,a)
FSWAP(a,b): SWAP(a,b) → CP(a,b,PI)
```

SWAP exchanges the states carried by two wires. It works for an unknown
superposition, not just for classical bit values. All three CX steps are needed;
DCX has only two steps and is a different gate. FSWAP also changes the sign of
11, so it is a **fermionic** swap convention rather than an ordinary swap.

```psi
let q = Register(2);
// Equivalent named form: q.Gate(name: SWAP, targets: [0, 1]);
q.Flip(target: 1, where: q[0] == 1);
q.Flip(target: 0, where: q[1] == 1);
q.Flip(target: 1, where: q[0] == 1);
```

### Controlled swaps and other three-wire recipes

CSWAP(c,a,b), also called Fredkin, exchanges a and b only when c=1. Add the
same extra control to every Flip of the SWAP recipe:

```psi
let q = Register(3);
// Equivalent named form: q.Gate(name: CSWAP, targets: [0, 1, 2]);
q.Flip(target: 2, where: q[0] == 1 && q[1] == 1);
q.Flip(target: 1, where: q[0] == 1 && q[2] == 1);
q.Flip(target: 2, where: q[0] == 1 && q[1] == 1);
```

CFSWAP(c,a,b), also called fermionic Fredkin, is that sequence followed by
Phase(PI) on the basis state where c=a=b=1. PERES(a,b,c) is
`CCX(a,b,c) → CX(a,b)`: first compute the conditional flip, then update b.

MARGOLUS(a,b,c) is `CCX(a,b,c)` followed by Phase(PI) where a=1, b=0, c=1.
That phase is not disposable: it distinguishes Margolus from Toffoli. The
RCCX alias in this repository selects this specific Margolus convention;
other libraries may choose other relative phases. `M` means MAGIC here, not
Margolus. Full aliases appear in the [catalog](explain/gate-reference.md#complete-catalog).

## 11. The remaining named gates

The following recipes finish the catalog by reusing the building blocks already
expanded above. Parameters describe gate angles, not pulse durations.

### Exchange gates and fractional swaps

| Gate | Sequence in execution order |
| --- | --- |
| ISWAP | `RXY(a,b,-PI)` |
| SQRTISWAP | `RXY(a,b,-PI/2)` |
| DB (Dagwood Bumstead) | `RXY(a,b,3*PI/4)` |
| FSIM(theta,phi) | `RXY(a,b,2*theta) → CP(a,b,-phi)` |
| SYC (Sycamore) | `RXY(a,b,PI) → CP(a,b,-PI/6)` |
| SWAPPOW(alpha) | `G(PI*alpha/4) → RXX(a,b,PI*alpha/2) → RYY(a,b,PI*alpha/2) → RZZ(a,b,PI*alpha/2)` |
| SQRTSWAP | The SWAPPOW recipe with alpha=1/2. |

ISWAP exchanges 01 and 10 with a factor +i. It is not SWAP: that phase can
matter in a later interference experiment. SQRTISWAP and SQRTSWAP each square
to the gate in their name, but they are different roots of different gates.
SWAPPOW uses a dimensionless power alpha: 0 gives identity, 1 gives SWAP, and
1/2 gives SQRTSWAP. Alpha is not itself an angle in radians.

FSIM combines excitation exchange with an extra phase on 11. This implementation
uses `exp(-i phi)` on 11, following Google's convention. The reviewed Wikipedia
FSIM row uses the opposite sign; negate phi to reproduce that row. SYC equals
FSIM(PI/2,PI/6) under the implemented convention. The [matrix reference](explain/gate-reference.md)
records this discrepancy and its sources.

### Canonical interaction, Berkeley B, ECR and Magic

| Gate | Sequence in execution order |
| --- | --- |
| CAN(aAngle,bAngle,cAngle) on wires a,b | `RXX(a,b,-2*aAngle) → RYY(a,b,-2*bAngle) → RZZ(a,b,-2*cAngle)` |
| B (Berkeley) | The CAN recipe with angles PI/4, PI/8, 0. |
| ECR | `RZX(a,b,PI/2) → X(a)` |
| MAGIC | `P(a,PI/2) → P(b,PI/2) → CP(a,b,-PI) → SWAP(a,b) → H(a) → CX(a,b)` |

CAN combines three independent pair-interaction strengths. Its three interaction
matrices commute, meaning their order can be exchanged without changing the
result. The table nevertheless gives the order used by the synthesizer.
For clarity, `aAngle` is a numeric parameter and wire a is an index; they are
not the same variable. The public CAN parameter names remain `a`, `b`, `c`.

B is one fixed choice of those strengths. ECR means echoed cross resonance,
but the logical implementation is the ideal matrix defined by the recipe;
it does not simulate the laboratory echo pulses. Its first operand is the Z
side of RZX and is the wire flipped afterward. MAGIC is a change to a useful
entangled basis, built from phase shifts, a swap and a Bell-style transform.

### Givens, CZS and the odd-subspace construction

The **odd subspace** consists of 01 and 10: the states with exactly one 1.
Suppose W is a one-qubit transformation that we want to apply within these two
states while leaving 00 and 11 alone. Define this explanatory block:

```text
ODD(a,b,W): CX(a,b) → CU(b,a,W) → CX(a,b)
```

CU(control,target,W) means controlled W; section 12 expands it into primitives.
The first CX maps the original odd states to labels with b=1. Controlled W
then mixes their a bit. The last CX returns to the original labeling. In this
block W's first basis state corresponds to original 01, its second to original 10.

GIVENS(t) uses `ODD(a,b, RY(2*t))`. Consequently its 01/10 block is the real
rotation `[[cos(t),-sin(t)],[sin(t),cos(t)]]`. It exchanges amplitude with a
real sign pattern, unlike XY's factors of -i.

For CZS(theta,phi,gamma), define `s = sin(theta/2)`, `c = cos(theta/2)` and
`E = exp(i gamma)`. Here c and s are numbers, not wire indices. Use:

```text
W = [ c² - E s²                 (1+E) exp(-i phi) s c ]
    [ (1+E) exp(i phi) s c       s² - E c²             ]

CZS: ODD(a,b,W) → CP(a,b,gamma+PI)
```

The ODD block transforms 01 and 10. The final CP gives 11 its required
`-exp(i gamma)` phase; 00 remains unchanged. W is an ordinary two-by-two
unitary and is reduced by the general construction below.

CCZS(c,a,b) adds an outer control c. Its sequence is
`CX(a,b) → CCU(c,b,a,W) → CX(a,b)`, followed by Phase(gamma+PI) where c=a=b=1.
CCU applies W on its last wire only when both leading wires are 1. The
unconditional CX pair is deliberate: when c=0, the middle operation does
nothing and the two CX operations undo each other.

### Barenco and Deutsch

BARENCO(alpha,phi,theta) is `CU(a,b,W)`, with the following W recipe on b:

```text
RZ(b,-phi) → RX(b,2*theta) → RZ(b,phi) → G(alpha)
```

This first changes the direction of an X rotation through phase rotations,
then gives the active control branch its phase alpha. Apply the general
controlled-unitary construction to the entire W, including that phase.

DEUTSCH(theta) is `CCU(a,b,c,W)`, where
`W = G(PI/2) → RX(c,2*theta)`. Its active matrix is
`i*cos(theta)*I + sin(theta)*X`. At theta=PI/2 it becomes CCX. At other angles
it mixes the target amplitudes only in the a=b=1 branch.

## 12. How arbitrary controlled rotations reach the primitives

This section explains the shared last step used for CH, CSX, CRX, CRY, CRZ,
Barenco, Deutsch, Givens and CZS. You can call these gates by name without
calculating these angles yourself.

Any single-qubit unitary W can be expressed in **Euler form**:

```text
W = exp(i delta) RZ(p) RY(t) RZ(l)     (matrix multiplication order)
```

Euler form describes a general rotation as three simpler rotations, plus a
possible global phase. In execution order, W itself is:

```text
RZ(target,l) → RY(target,t) → RZ(target,p) → G(delta)
```

For the public gate U(theta,phi,lambda), one possible choice is
`t=theta`, `p=phi`, `l=lambda`, `delta=(phi+lambda)/2`.
For other matrices, the implementation's `_euler` helper calculates angles
from the entries, including special cases where a sine or cosine is zero.
Different angle choices can describe the same matrix.

CU(c,a,W) expands to the following sequence:

```text
RZ(a,(l-p)/2)
→ CX(c,a)
→ RZ(a,-(l+p)/2) → RY(a,-t/2)
→ CX(c,a)
→ RY(a,t/2) → RZ(a,p)
→ P(c,delta)
```

If c=0, the rotations cancel. If c=1, the two flips change how the rotations
combine, giving W on a. The final P on the control supplies the phase of the
active branch. Using `G(delta)` there would phase both control branches and
would implement the wrong relative phase.

For two controls, choose a unitary square root V with `V V = W`. Then:

```text
CCU(c1,c2,a,W):
CU(c2,a,V) → CX(c1,c2) → CU(c2,a,V†) → CX(c1,c2) → CU(c1,a,V)
```

Each CU expands by the preceding rule. The middle CX pair restores c2.
This controlled-square-root construction is how the current synthesizer reduces
Deutsch and controlled odd-subspace gates. It is not a new primitive. The
implementation uses a stable two-by-two matrix square-root calculation and
checks these expansions against analytic matrices in the gate tests.

Finally, to invert **any** named-gate recipe, reverse its sequence and invert
each step. H and X (including controlled X) undo themselves; negate every Phase
angle. `inverse: true` performs exactly this operation on the primitive records.
Do not merely negate every parameter of a general gate while keeping its order.

## 13. Measurement and repeated experiments

Measurement returns a classical result and changes the quantum state. It is
not a unitary gate and has no inverse gate that recovers an unknown input.

```psi
let pair = Register(2);
pair.Superpose(targets: 0);
pair.Flip(target: 1, where: pair[0] == 1);
let alice = Measure(pair[0]);
pair.Flip(target: 1, when: alice == 1);
let output = pair.Measure();
```

Before measuring, the state is `(00+11)/sqrt(2)`. If `alice` is 0, the state
becomes `00`; if it is 1, the state becomes `11`. The classical correction
then flips q1 only in the second case, giving `01`. Thus the final result is
00 or 01, and q1 is always zero. The result is local feed-forward, not a
communication service.

`Measure(reg[i])` measures one wire; the other wires retain the conditional
state selected by that outcome. `reg.Measure()` or `Measure(reg)` measures the
whole register. Assigned results are integers, with the bit ordering in section 3.
`reg.Measure(target: i, when: condition)` and `Measure(reg[i], when: condition)`
also work. A skipped measurement neither changes the state nor writes a result.

A **projector** P_m keeps only the part of the state consistent with outcome m.
For example, measuring one qubit as 0 uses matrix `[[1,0],[0,0]]` on that wire.
The retained part is normalized afterward:

```text
probability of m: p_m = <psi|P_m|psi>
new state:         P_m|psi> / sqrt(p_m)
```

`<psi|` is the conjugate-transpose row corresponding to the state column
`|psi>`. If the retained probability is one half, divide the retained amplitudes
by `sqrt(1/2)` so their squared magnitudes again sum to 1. The simulator samples
only possible outcomes and keeps independent snapshots of earlier states.

A **shot** is one complete repetition starting from the initial state. Use
`--shots 500` to estimate outcome frequencies from 500 runs. Each run repeats
intermediate measurements and classical corrections. `--seed 1` makes sampling
repeatable; it does not force an outcome with probability 1. In a branching
circuit, exact probabilities shown for one trajectory can differ from shot
frequencies aggregated over all trajectories.

## 14. Reading the 3D wave viewer

### Continuous wave lens: see amplitudes combine

```sh
python3 viewer-references/psi_interference_viewer.py qscripts/interactions.psi --step 1
python3 viewer-references/psi_interference_viewer.py qscripts/exchange.psi --step 2 --wave-mode real
python3 viewer-references/psi_interference_viewer.py qscripts/wave_interference.psi --step 2 --wave-mode real
```

The default `--view waves` shows the state **before**, **during** and **after**
one circuit operation. Previous/Next or the Circuit step slider changes that
operation. Gate fraction chooses an intermediate point; Play/pause animates it.
Circuit switches supplied scripts. `--qubits 0 2` chooses which wires to inspect.
The default step is -1, meaning the last operation; specify `--step 1` to begin
at the first gate rather than after a final measurement.

A gate-register state has a finite list of amplitudes, not an intrinsic physical
surface in ordinary space. To display a continuous wave, the viewer explicitly
assigns two orthonormal shapes to each qubit:

```text
phi0(x) = pi^(-1/4) exp(-x²/2)        Gaussian mode for |0>
phi1(x) = sqrt(2) x phi0(x)          signed two-lobe mode for |1>
Psi(x,y) = sum_ab c_ab phi_a(x) phi_b(y)
```

**Orthonormal** means each mode has integrated squared magnitude 1, and their
mutual overlap is zero. Consequently this representation preserves the state's
inner products and represents its coefficients without conflating 0 and 1.
`c_ab` is the amplitude with the first selected wire equal to a and the second
equal to b. The sum has four terms. For a single selected wire, a fixed vacuum
mode supplies the second display coordinate.

The axes are chosen configuration coordinates for the two wires, not the
physical positions of a superconducting qubit or two particles moving toward
each other. A coordinate-space density is not the same as a computational-basis
measurement histogram. Gates act on the coefficients; the displayed shapes
then change according to the equation above. An entangled pure wave cannot
be factored as `f(x)*g(y)`, even if its individual-wire views look simple.

Density mode shows `|Psi|²`. Real and Imaginary modes show the signed real or
imaginary part of Psi; a negative lobe is an amplitude sign, not negative
probability. For pure states, color indicates phase. Use both shape and color: an imaginary
component can change while the real-height surface looks almost unchanged.
Global phase can rotate these real/imaginary views without changing any
measurement prediction.

The during-gate view follows a mathematical unitary path: it turns each
unitary eigenvalue's phase by the chosen fraction of its principal angle.
An **eigenvector** is a state a gate changes only by a multiplier; that multiplier
is its **eigenvalue**. Fraction 0 gives the input and fraction 1 the output.
There can be several paths between them. This path is not a calibrated pulse
trajectory, and a named gate's animated path need not match the path traced by
executing its expanded primitives individually. Measurement jumps at fraction 1;
it is not displayed as a reversible smooth gate. Pulse annotations do not move
the logic state.

### Mixed states and the diagnostic workbench

A full simulator state is pure: one amplitude vector describes it. If you
inspect only part of an entangled register, no single amplitude vector generally
describes that part. Its **reduced density matrix** records the statistics and
coherences that remain after ignoring the other wires. This process of ignoring
unselected wires is the **partial trace**. A **mixed** reduced state is not
assigned a fabricated pure wavefunction; the wave lens displays its joint
density instead, using a density color scale rather than a pure-state phase scale.

```sh
python3 viewer-references/psi_interference_viewer.py qscripts/interactions.psi --view workbench --step 1 --shots 500 --seed 1
```

The workbench supplies complementary views:

| View or quantity | How to read it |
| --- | --- |
| Basis bars | Height is probability, or signed real/imaginary amplitude after switching mode. Labels are computational-basis states. |
| Density matrix | Diagonal entries are basis probabilities; off-diagonal entries carry coherence between basis states. |
| Bloch vector | A three-coordinate description of one qubit; its components are average X, Y and Z measurement values. Pure single-qubit states have length 1; locally mixed states have shorter vectors. |
| Purity `Tr(rho²)` | Sum of diagonal entries after squaring rho. It is 1 for a pure state and smaller for a mixed state. |
| Entropy | Uncertainty associated with the reduced state's eigenvalues, in bits; zero for a pure state. |
| Connected Pauli correlations | How much a pair's joint averages differ from independent averages: `<AB> - <A><B>`. A and B are X, Y or Z on the selected wires. |
| Concurrence | A two-qubit entanglement measure: 0 means no pair entanglement; 1 means maximal pair entanglement. |
| Mutual information | Total pair correlation, including classical correlation; it is not an entanglement measure by itself. |
| Matrix comparison | Analytic gate versus its primitive expansion, including numerical error. Re/Im selects the matrix component. |
| Measurement panel | Before-collapse probabilities and shot frequencies; state panels show the sampled collapsed state. Small projector matrices explain the selected outcome. |

A zero Bloch vector does not mean “no state.” Each member of a Bell pair has
zero local vector, even though their joint state is pure and entangled. Conversely,
a pair selected from a three-qubit GHZ state is classically correlated but has
zero pair concurrence. Correlation and pair entanglement are different questions.
The [matrix reference](explain/gate-reference.md#viewer-mathematics-and-comparison)
gives the diagnostic equations.

Workbench controls are Left/right for steps, Q for another wire pair, C for
another circuit, W for wave/bar mode and M for matrix real/imaginary parts.
These keyboard shortcuts describe the workbench; the wave lens uses its labeled
buttons and sliders. Native GUI behavior depends on the Matplotlib backend.

## 15. The analog layer and time

Logic gates describe a state transformation. A physical device needs timed
signals to realize such a transformation. qscript's analog vocabulary records
that lower-level intent, without yet implementing a hardware interface.

```psi
let memory = Register(2);
Align {
    branch memory[0] {
        Rotate(axis: X, angle: PI, duration: 40ns);
        Wait(duration: 20ns);
        Rotate(axis: -X, angle: PI, duration: 40ns);
    }
    branch memory[1] { Wait(duration: 100ns); }
}
Analog(target: memory[0]) { ShiftPhase(angle: PI/8); }
```

`Analog(target: reg[i]) { ... }` establishes the addressed wire. A branch header
can also supply an inherited wire. Within a branch, sequential durations add.
`Align` starts its branches together and advances enclosing time by the longest
branch. Here the first lasts 40+20+40 = 100 ns and the second lasts 100 ns, so
the following frame change starts at 100 ns.

| Verb | Meaning and current implementation |
| --- | --- |
| Rotate(axis, angle, duration, shape?) | Record a signed-X/Y/Z pulse rotation, time and optional envelope metadata. |
| Wait(duration) | Advance the scheduled time without a drive operation. |
| ShiftPhase(angle) | Record a frame phase change; the ideal pulse Bloch backend treats it as a Z rotation. |
| SetFreq(hz) | Record the intended drive frequency, in cycles per second. |
| Play(waveform, channel) | Record which waveform should be sent to which output channel. |
| Acquire(duration, kernel) | Record acquisition/readout intent and processing metadata. It does not measure the logic statevector. |

A **frame** is the phase/frequency reference used to describe a drive. An
**envelope** is the shape of the drive strength over time. The current scheduler
retains such metadata; it does not generate sampled voltages. `ns` means
nanoseconds. `dt` is currently converted with factor 1 rather than a calibrated
hardware tick. Malformed or unknown units are permissive, not validated timing.

`q.Turn(...)` and `Rotate(...)` are deliberately different: Turn is a logical
unitary with no duration; Rotate records timed pulse intent. Logic operations
and quantum `where:` belong outside Analog. Some pulse verbs currently accept
ignored `where` metadata, which must not be interpreted as quantum control.

The separate pulse Bloch backend starts independent wires at +Z (the |0> pole)
and applies ideal rotations and phase shifts. It imports no prior logic state
and models neither entanglement nor noise, waveform physics, readout or physical
emission. Pulse operations are annotations in the logic viewer and comments in
OpenQASM. An echo-shaped schedule is not evidence of simulated noise cancellation.

## 16. Compilation, numerical comparison and current limits

### Verify a named gate or a complete circuit

```sh
python3 compiler/qasm_compiler.py qscripts/interactions.psi --out build/interactions.qasm
python3 compiler/qasm_compiler.py qscripts/ghost_filter.psi --pulse-table --simulate-bloch
python3 viewer-references/psi_interference_viewer.py --matrix RXX --params PI/2
MPLBACKEND=Agg python3 viewer-references/psi_interference_viewer.py qscripts/bell_unitary.psi qscripts/bell_primitives.psi --unitary --report build/bell.json --no-show
```

The last command compares the same Bell transform expressed with named gates
and with primitives, over every input basis state. Comparing only an output
from |00> would not verify the rest of a gate's matrix. `--unitary` also compares
reference and primitive matrices, and records differences with and without a
common global phase. It requires unitary operations without measurement,
classical guards or pulse annotations, and limits dense matrices to eight qubits.

OpenQASM 2 omits global phase with explicit comments. It supports the catalog's
primitive expansions and conjunction-based controls, but rejects complex
unsupported oracles and guards. A helper ancilla must be restored after use;
a declaration or successful text export alone is not a proof of correctness.
The test suite checks emitted instruction behavior with a local independent
evaluator; external QASM conformance and hardware validation are not claimed.

### Save pictures and numerical data

`--save path.png` saves the selected view. `--report path.json` writes an array
of per-circuit reports containing the full complex final state, probabilities,
classical results, measurements, shots, selected reductions at each step and
analytic-versus-primitive gate matrices/errors. Complex arrays are represented
as separate `real` and `imag` lists. `--no-show` uses a headless rendering backend.
Output options create parent directories and overwrite their destinations.

`--initial 101` prepares that basis input instead of all zeroes; the Python
simulator also accepts a normalized complex array. `--register` selects a register.
Reports retain full distributions, while the workbench caps basis bars at 128
and histogram outcomes at 16, labeling truncation. Statevectors and snapshots
still require exponentially growing classical memory.

The [README](README.md#animated-3d-wavefunctions) includes actual screenshots.
`python3 assets/generate_screenshots.py` regenerates them with the optional viewer
dependencies. The independent `viewer-references/wave_viewer.py` is a separate
analytic spatial teaching model; it does not load circuits.

### Implemented syntax versus future intent

Custom `def pulse SoftFlip(...) { ... }` and `reg.apply(SoftFlip, ...)` remain
planned. General if, repeat and function blocks are not interpreted: unknown
block bodies are currently visited once, rather than implementing their apparent
control flow. Write explicit operations and operation-level `when:` guards.

Use trusted local source: expressions use Python evaluation and are not a secure
sandbox. There is no joint-register simulator, noisy joint-state model, calibrated
hardware execution, topology optimizer or optimal-synthesis guarantee. The
[agent handbook](AGENTS.md#known-gaps-and-planned-work) records implementation gaps
and planned work, and the [example guide](qscripts/EXAMPLES.md) distinguishes
working examples from algorithm sketches.
