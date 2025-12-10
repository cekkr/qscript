# PsiScript Algorithm Suite 🌌

Welcome to the **PsiScript** examples repository.

PsiScript is a high-level theoretical quantum programming language designed to abstract away the physical "wires" of quantum circuits. Instead of thinking in gates (`H`, `CNOT`, `Z`), PsiScript allows the programmer to think in **Geometric Primitives** and **Logical Constraints**.

This repository contains 7 examples demonstrating how standard quantum algorithms are synthesized using the four PsiScript primitives (shown with the lightweight `let` declaration style and `where/when` guards):
1.  **`Superpose`** (Create Possibilities)
2.  **`Phase`** (Mark/Tag Logic)
3.  **`Reflect`** (Amplify Solutions)
4.  **`Flip`** (Move/Entangle Data)

---

## 📂 Script Breakdown

### 1. `bell_pair.psi` (The "Hello World" of Quantum)
**Goal:** Create a pair of entangled qubits (EPR Pair). This is the fundamental unit of quantum connectivity.

* **Step 1: Initialization.** `let pair = Register(2)` gives two qubits in `|00>`.
* **Step 2: `pair.Superpose(targets: 0)`**. We split Qubit 0 into a 50/50 probability state. The system is now in `|00> + |10>`.
* **Step 3: `pair.Flip(target: 1, where: pair[0] == 1)`**. This is the entanglement step. We tell the system: "If Qubit 0 is 1, then flip Qubit 1".
    * *Result:* The state `|10>` becomes `|11>`. The state `|00>` remains `|00>`.
    * *Outcome:* The qubits are now perfectly correlated. Measuring one instantly tells you the state of the other.

---

### 2. `teleport.psi` (Quantum Teleportation)
**Goal:** Transmit the exact quantum state of a "Payload" qubit to a distant location using entanglement and classical communication.

* **Step 1: The Bridge.** `let system = Register(3)` then `system.Superpose(targets: 1)` and `system.Flip(target: 2, where: system[1] == 1)` create the shared EPR pair (Q1-Q2).
* **Step 2: Alice's Action.** Alice entangles her Payload (Q0) with her half of the bridge (Q1) using `Flip` then `Superpose`. This "mixes" the information of the Payload into the entangled pair.
* **Step 3: Collapse.** Alice measures her two qubits. This destroys the original Payload state but projects its information onto Bob's qubit (Q2) in a scrambled form (`let c1 = Measure(system[0]); let c2 = Measure(system[1]);`).
* **Step 4: Classical Transfer.** Alice sends the 2 classical bits she measured to Bob (standard `if`/`when:` semantics).
* **Step 5: Bob's Correction.**
    * `system.Flip(target: 2, when: c2 == 1)` (bit flip).
    * `system.Phase(angle: PI, where: system[2] == 1, when: c1 == 1)` (phase flip).
    * *Result:* Bob's qubit is now physically identical to the original Payload.

---

### 3. `grover_sat.psi` (3-SAT Solver / Database Search)
**Goal:** Find the specific input variables that satisfy a complex boolean formula without checking them one by one.

* **Step 1: `logic_space.Superpose(targets: ALL)`**. We create 8 parallel realities (from `000` to `111`). All exist simultaneously with equal probability.
* **Step 2: The Oracle (`Phase`)**. We apply the logic constraints.
    * `logic_space.Phase(angle: PI, where: (logic_space[0] || logic_space[1]) && (!logic_space[0] || logic_space[2]))`
    * Instead of reading the data, we simply **rotate the phase** (flip the sign) of the matching state. The "correct" answer now points "Down" in the geometric space, while wrong answers point "Up".
* **Step 3: The Diffusion (`Reflect`)**. We apply `logic_space.Reflect(axis: Axis.MEAN)`.
    * Geometric magic happens here: The "Down" vector is reflected against the average, shooting up in probability. The "Up" vectors (wrong answers) shrink.
* **Step 4: Iteration.** We repeat steps 2 and 3 to maximize the contrast before measuring.

---

### 4. `qft_3.psi` (Quantum Fourier Transform)
**Goal:** Transform data from amplitude encoding to frequency encoding. This is the engine behind Shor's Algorithm (breaking encryption).

* **Logic:** QFT is a series of `Superpose` (Hadamard) and precise `Phase` rotations that depend on the distance between qubits.
* **Step 1: MSB Processing.** We superpose Qubit 0, then rotate it slightly (`q.Phase(angle: PI/2, where: q[0] == 1 && q[1] == 1)`, `q.Phase(angle: PI/4, where: q[0] == 1 && q[2] == 1)`). This encodes the frequency information into the phase.
* **Step 2 & 3: Recursive Processing.** We repeat the process for Q1 and Q2 with decreasing rotation angles.
* **Step 4: Swap.** Finally, we reverse the order of the qubits (`q.Flip(target: 0, where: q[2] == 1)` etc.) to match the standard binary output format.
* *Note:* This script demonstrates how PsiScript handles **Controlled-Phase Rotations** (`Phase... where...`) naturally.

---

### 5. `adder.psi` (Ripple Carry Adder)
**Goal:** Perform classical arithmetic (A + B) using quantum reversible logic.
*Inputs:* Q0 (A), Q1 (B). *Outputs:* Q1 (Sum), Q2 (Carry).

* **Step 1: Calculate Carry.** We check if *both* input bits are 1.
    * `reg.Flip(target: 2, where: reg[0] == 1 && reg[1] == 1)`.
    * This synthesizes a **Toffoli Gate** (CCNOT). If A=1 and B=1, the Carry (Q2) flips to 1.
* **Step 2: Calculate Sum.** We perform an XOR operation (A + B without carry).
    * `reg.Flip(target: 1, where: reg[0] == 1)`.
    * This synthesizes a **CNOT**. Q1 becomes `1` if the inputs are different, `0` if they are the same.
* *Insight:* This shows that classical logic is just a subset of quantum logic where we restrict ourselves to `Flip` operations and ignore superposition.

---

### 6. `ghz.psi` (Three-Way Entanglement)
**Goal:** Build a GHZ state `( |000> + |111> ) / sqrt(2)` that shows perfect three-party correlation.

* **Step 1: Seed coherence.** `ghz.Superpose(targets: 0)` creates a superposition on the first qubit.
* **Step 2: Fan-out via controlled flips.** `ghz.Flip(target: 1, where: ghz[0] == 1)` and `ghz.Flip(target: 2, where: ghz[0] == 1)` copy the phase bit to the other qubits.
* **Outcome:** Measuring any qubit determines the rest; there are no mixed outcomes like `010` or `101`.

---

### 7. `bernstein_vazirani.psi` (Hidden String Recovery)
**Goal:** Learn a hidden classical string `s` with a single oracle query using phase kickback.

* **Step 1: Spread queries.** `bv.Superpose(targets: ALL)` creates all candidate bitstrings.
* **Step 2: Phase oracle.** For `s = 101`, `bv.Phase(angle: PI, where: (bv[0] && !bv[2]) || (!bv[0] && bv[2]))` flips the sign when `x · s (mod 2) = 1`.
* **Step 3: Decode.** Another `bv.Superpose(targets: ALL)` converts the phase pattern back to amplitudes.
* **Outcome:** Measuring yields `101` with certainty, showing how PsiScript expresses phase oracles and global decoding succinctly.

---

## 🛠 PsiScript Primitive Reference

| Primitive | Syntax | Physics (Transpiler Output) | Description |
| :--- | :--- | :--- | :--- |
| **Superpose** | `.Superpose(targets: ALL | [i...])` | **Hadamard (H)** | Spreads "liquid" (probability) equally across states. |
| **Phase** | `.Phase(angle: θ, where: predicate)` | **Z / Phase / Oracle** | Rotates the needle direction. Used to inject logic/constraints. |
| **Reflect** | `.Reflect(axis: Axis.MEAN)` | **Diffusion Operator** | Interferes probabilities based on phase differences. Amplifies solutions. |
| **Flip** | `.Flip(target: i, where: predicate | when: classical)` | **X / CNOT / Toffoli** | Moves entire needles between clocks. Used for entanglement and boolean logic. |

---
*PsiScript v1.0 - Conceptual Framework for High-Level Quantum Computing*
