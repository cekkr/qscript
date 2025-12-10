# PsiScript v1.1 - Technical Reference Manual

## 1. Philosophy: Interference Sculpting

PsiScript is a high-level quantum description language built around **Interference Sculpting**. Instead of thinking about qubits as spinning arrows, you treat the register as a block of raw possibility and sculpt it by tagging, interfering, and finally collapsing.

- **Medium:** A Hilbert space with $2^N$ simultaneous basis states.
- **Tool:** Complex phase (imaginary numbers) that tags regions of that space.
- **Mechanism:** Constructive and destructive interference that carves away the wrong answers and amplifies the right ones.

The syntax remains lightweight and familiar (JS/Python flavored), but the semantics are framed around carving probability mass rather than rotating geometric vectors.

---

## 2. Syntax at a Glance

```psi
// Declaration (multiple registers allowed)
let work = Register(3), scratch = Register(1)

// Quantum-time operations (sculpt the wavefunction)
work.Superpose(targets: ALL)                       // Expansion
work.Phase(angle: PI, where: work[0] == work[1])   // Tag with a phase chisel
work.Flip(target: 2, where: work[0] && !work[1])   // Pivot/route data

// Measurement boundary (collapse)
let c0 = Measure(work[0])
let c1 = Measure(work[1])

// Classical-time control (per-branch, no entanglement)
if (c0) { work.Flip(target: 2, when: true) }
if (c1) { work.Phase(angle: PI, where: work[2], when: true) }
```

**Key rules**
- **Declaration is inferred:** `let name = Register(3)` introduces a computational space of size $2^3$; multiple registers are fine.
- **Indexing:** `reg[i]` always refers to the *i*th qubit inside that register.
- **Guards:** `where:` is a **quantum predicate** evaluated across the entire superposition; it creates entanglement and phase tags. `when:` is a **classical guard** evaluated after measurements.
- **Measurement is a wall:** After `Measure`, you are in classical-time until you call a primitive again.
- **Surface verbs stay unitary:** Primitives compose into a single sculpting step; measurement is kept as a top-level verb to signal irreversibility.

---

## 3. Primitive Semantics (v1.1)

### 3.1 `Superpose(targets)` — The Expansion
Creates the raw block of possibilities.

- **Syntax:** `Register.Superpose(targets: ALL | [i0, i1, ...] | i)`
- **Meaning:** Instantiate every basis state with equal potential. Whether 3 qubits or 30, this step inflates the register to all $2^N$ indices.
- **Circuit intuition:** Maps to Hadamards on the targets (depth O(1)).
- **Scaling note:** This is where exponential parallelism appears; more qubits = more parallel realities to sculpt.

---

### 3.2 `Phase(angle, where)` — The Chisel
Tags regions of the hyperspace with complex phase.

- **Syntax:** `Register.Phase(angle: PI, where: reg[0] == reg[1])`
- **Meaning:** Apply a phase to every state satisfying the quantum predicate. `angle: PI` marks states as “invalid” (negative amplitude); fractional angles (e.g., `PI/2`, `PI/4`) encode frequency relationships as in QFT.
- **Imaginary plane:** Phase moves amplitude into the imaginary axis; later interference converts these tags into probability shifts.
- **Circuit intuition:** Implements an oracle (compute–phase–uncompute) using controlled-phase families.

---

### 3.3 `Reflect(axis)` — The Interference Trigger
Turns phase tags into probability changes.

- **Syntax:** `Register.Reflect(axis: Axis.MEAN)`
- **Meaning:** Invert around the mean so tagged states destructively interfere and untagged states amplify. This is the moment the “chisel marks” carve away the wrong answers.
- **Circuit intuition:** Grover-style diffusion (H → X → multi-controlled Z → X → H).

---

### 3.4 `Flip(target, where?, when?)` — The Pivot
Conditionally reroutes indices to create entanglement or reorder data.

- **Syntax:** `Register.Flip(target: 1, where: reg[0] == 1)` or `Register.Flip(target: 1, when: classicalBit)`
- **Meaning:** Conditional bit flip that reorients the computational subspace. With `where`, it entangles/pivots states; with `when`, it applies a classical correction.
- **Circuit intuition:** Compiles to X/CX/Toffoli with helper X gates for `== 0` controls.

---

## 4. Registers, Scope, and Scaling

- Multiple registers are allowed; operations act on one register at a time. Cross-register conditions are explicit (e.g., `data.Flip(target: 2, where: anc[0])`).
- Classical `Bit` values originate from `Measure(register[index])` or host literals.
- Functions/macros can accept registers; the language stays declarative and compact.
- **Scaling intuition:** `where` predicates evaluate over the entire $2^N$ space at once. The goal is to carve a single correct state out of exponentially many candidates by iterating `Phase` + `Reflect`.

---

## 5. Execution Order: Quantum-Time vs Classical-Time

- **Quantum-time:** All `Superpose`, `Phase`, `Reflect`, and `Flip` calls before a measurement compose into one sculpting unitary. Multiple `where` predicates can overlap and interfere.
- **Measurement boundary:** `Measure` collapses targeted qubits (or an entire register) and produces classical bits. Subsequent `when:` guards use those bits; further `where:` clauses still operate on any remaining quantum data.
- **Classical-time:** Standard `if`, `for`, etc., control flow. `when:` keeps classical corrections explicit without suggesting extra entanglement.

---

## 6. Practical Example: Equality Tagging

PsiScript view:

```psi
let q = Register(2)
q.Phase(angle: PI, where: q[0] == q[1]) // mark 00 and 11 with a negative tag
```

Transpiled circuit (OpenQASM sketch):

```assembly
reg q[2]    // System
reg a[1]    // Ancilla
x a[0]; h a[0];           // Prepare |-> for phase kickback
cx q[0], a[0];            // Compute XOR
cx q[1], a[0];
x a[0];                   // Target equality
z a[0];                   // Phase tag
x a[0]; cx q[1], a[0];    // Uncompute
cx q[0], a[0];
```

---

## 7. Hardware Considerations

- **Topology:** Non-adjacent `where` predicates may insert SWAP ladders; depth costs should be surfaced.
- **Ancilla:** Phase oracles allocate helper qubits for kickback and clean them up with uncomputation.
- **Precision:** Algorithm accuracy depends on how precisely `Phase` can isolate the desired state within the large search space, not just on qubit count.
