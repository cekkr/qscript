# PsiScript v1.0 - Technical Reference Manual

## 1\. Overview

PsiScript is a high-level, geometry-oriented quantum description language. Programs describe **constraints** and **geometric transformations** on a state vector using four primitives: `Superpose`, `Phase`, `Reflect`, and `Flip`. The transpiler handles gate selection, ancilla management, and uncomputation.

**Philosophy:** Keep the scripting model as close as possible to a familiar scripting language (Python/JS style variables and conditionals), while making interference and quantum/classical boundaries explicit.

---

## 2\. Syntax at a Glance

```psi
// Declaration (multiple registers allowed)
let work = Register(3), scratch = Register(1)

// Quantum-time operations (run before any measurement)
work.Superpose(targets: ALL)
work.Phase(angle: PI, where: work[0] == work[1])
work.Flip(target: 2, where: work[0] && !work[1])

// Measurement boundary
let c0 = Measure(work[0])
let c1 = Measure(work[1])

// Classical-time control (runs per classical branch, does not create entanglement)
if (c0) { work.Flip(target: 2, when: true) }
if (c1) { work.Phase(angle: PI, where: work[2], when: true) }
```

**Key rules**
- **Declaration is inferred:** `let name = Register(3)` introduces a qubit register; no C#/Java-style typing required. You may declare multiple registers in one line.
- **Indexing:** `reg[i]` always refers to the *i*th qubit inside that register.
- **Conditions:** `where:` is a quantum predicate (evaluated in superposition and compiled into an oracle). `when:` is a classical guard (evaluated after measurement results exist). Use `where` for entangling logic; use `when` for host-side branching.
- **Measurement is a wall:** Once you `Measure`, the following statements are purely classical until you call a primitive on an existing register again.
- **Why `Measure(reg[i])` and not `reg[i].measure()`?** Measurement is irreversible and leaves the quantum domain; making it a top-level verb (not a method) signals the classical boundary to the programmer and avoids suggesting it composes like a unitary call chain.

---

## 3\. Primitive Reference & Synthesis

### 3.1 `Superpose(targets)`
Distributes probability amplitude equally across the target subspace.

  * **Syntax:** `Register.Superpose(targets: ALL | [i0, i1, ...] | i)`
  * **Physical Meaning:** Create coherence.
  * **Circuit Synthesis:** Maps to Hadamard gates on each target qubit (parallel depth O(1)).

---

### 3.2 `Phase(angle, where)`
Rotates the phase of the quantum states that satisfy the predicate. Primary way to encode logic/data.

  * **Syntax:** `Register.Phase(angle: PI, where: reg[0] == reg[1])`
  * **Physical Meaning:** Multiply the amplitude of matching states by $e^{i\theta}$ (with $\theta=\pi$ giving a sign flip).
  * **Circuit Synthesis (Compute–Phase–Uncompute oracle):**
      1. **Allocate ancilla** prepared for phase kickback (e.g., $|-\rangle$).
      2. **Compute predicate** into the ancilla (e.g., XOR for equality).
      3. **Inject phase** via Z/CZ on the ancilla.
      4. **Uncompute** to erase entanglement and return ancilla to $|0\rangle$.

---

### 3.3 `Reflect(axis)`
Inverts amplitudes around a geometric axis (typically the mean).

  * **Syntax:** `Register.Reflect(axis: Axis.MEAN)`
  * **Physical Meaning:** Amplify probability for states marked with negative phase.
  * **Circuit Synthesis (Diffusion operator):** H on all qubits → X on all → multi-controlled Z → X on all → H on all. MCZ is decomposed to Toffolis/ancilla ladders as needed.

---

### 3.4 `Flip(target, where?, when?)`
Swaps amplitudes between basis vectors; expresses conditional logic and entanglement.

  * **Syntax:** `Register.Flip(target: 1, where: reg[0] == 1)` or `Register.Flip(target: 1, when: classicalBit)`
  * **Physical Meaning:** Conditional bit flip.
  * **Circuit Synthesis:**
      * **Quantum guard (`where`):** Compiles to controlled-X / Toffoli with automatic helper X gates for `== 0` conditions.
      * **Classical guard (`when`):** Executes only if the classical condition is true; the emitted circuit is unconditional inside that branch.

---

## 4\. Registers, Scope, and Multiple Workspaces

- You can own multiple registers simultaneously for clarity (e.g., `let data = Register(3), anc = Register(2)`). Operations act on one register at a time; crossing registers requires an explicit shared predicate (e.g., `data.Flip(target: 2, where: anc[0])`).
- Classical `Bit` values come from `Measure(register[index])` or host-provided literals.
- Functions/macros can accept registers as arguments; the language keeps the surface syntax lightweight and scripting-friendly.
- **Scaling intuition:** Increasing qubit count grows the computational space exponentially (n qubits → 2^n amplitudes). PsiScript’s `Superpose + Phase + Reflect` patterns become dramatically more useful when n grows beyond a handful, enabling search/amplification, hidden-pattern finding, and distributed entanglement (e.g., GHZ, teleportation chains).

---

## 5\. Interference and Execution Order

- **Quantum-time:** All `Superpose`, `Phase`, `Reflect`, and `Flip` calls before a measurement compose into a single unitary. Predicates under `where` are evaluated in superposition, so multiple conditions can interfere constructively/destructively.
- **Measurement boundary:** `Measure` collapses the register slice you read. Subsequent `where` predicates still act on the remaining qubits, but past measurement results only exist as classical `Bit`s.
- **Classical-time:** Use standard `if`, `for`, etc., with `when:` on primitives to express per-branch corrections (e.g., teleportation corrections). This separation avoids ambiguous "personalized IFs" while keeping quantum logic cohesive.

---

## 6\. Practical Example: Equality Check

PsiScript view:

```psi
let q = Register(2)
q.Phase(angle: PI, where: q[0] == q[1]) // mark 00 and 11
```

Transpiled circuit (OpenQASM sketch):

```assembly
reg q[2]    // System
reg a[1]    // Ancilla
x a[0]; h a[0];           // Prepare |-> for phase kickback
cx q[0], a[0];            // Compute XOR
cx q[1], a[0];
x a[0];                   // Invert to target equality
z a[0];                   // Phase injection
x a[0]; cx q[1], a[0];    // Uncompute
cx q[0], a[0];
```

---

## 7\. Hardware Constraints & Optimization

The compiler inserts SWAP networks when topology requires it.

  * **Constraint:** `where` clauses involving distant qubits (e.g., `where: Q[0] == Q[10]`).
  * **Synthesis:** Bucket-brigade SWAPs bring qubits together, apply the logic, and swap back.
  * **Warning:** Added SWAP depth increases decoherence risk; tooling should surface this cost.
