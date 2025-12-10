# PsiScript Algorithm Suite 🌌

Welcome to the **PsiScript** examples repository.

PsiScript v1.1 frames quantum code as **Interference Sculpting**. You expand a massive block of possibilities, tag regions with complex phase, trigger interference to carve away wrong answers, and pivot data into place for reading. The four primitives stay the same but their meaning is:
1. **`Superpose`** — Expansion (create the block of marble).
2. **`Phase`** — The chisel (tag logic into the imaginary plane).
3. **`Reflect`** — Interference trigger (convert tags into probability shifts).
4. **`Flip`** — Pivot/route (conditional index rerouting or classical correction).

---

## 📂 Script Breakdown

### 1. `bell_pair.psi` (The "Hello World" of Quantum)
**Goal:** Create a pair of entangled qubits (EPR Pair). This is the fundamental unit of quantum connectivity.

* **Step 1: Initialization.** `let pair = Register(2)` seeds the 4-state space.
* **Step 2: Expansion.** `pair.Superpose(targets: 0)` creates the raw block (`|00> + |10>`).
* **Step 3: Pivot to entangle.** `pair.Flip(target: 1, where: pair[0] == 1)` routes half the block so tags align; the surviving realities become `|00>` and `|11>`.
* **Outcome:** The qubits are perfectly correlated; measurement collapses to either `00` or `11`.

---

### 2. `teleport.psi` (Quantum Teleportation)
**Goal:** Transmit the exact quantum state of a "Payload" qubit to a distant location using entanglement and classical communication.

* **Step 1: Build the bridge.** `let system = Register(3)` then `system.Superpose(targets: 1)` and `system.Flip(target: 2, where: system[1] == 1)` sculpt an EPR backbone.
* **Step 2: Alice tags the payload into the bridge.** `Flip` and `Superpose` entangle Q0 with Q1 so the payload’s phase information is spread across the shared hyperspace.
* **Step 3: Collapse on Alice's side.** `let c1 = Measure(system[0]); let c2 = Measure(system[1]);` slices away her portion of the block.
* **Step 4: Classical transfer.** Alice forwards `(c1, c2)`; no quantum link remains.
* **Step 5: Bob pivots using classical guards.** `system.Flip(target: 2, when: c2 == 1)` and `system.Phase(angle: PI, where: system[2] == 1, when: c1 == 1)` align the surviving reality. Qubit 2 matches the original payload.

---

### 3. `grover_sat.psi` (3-SAT Solver / Database Search)
**Goal:** Find the specific input variables that satisfy a complex boolean formula without checking them one by one.

* **Step 1: Expand the search space.** `logic_space.Superpose(targets: ALL)` instantiates all 8 candidates.
* **Step 2: Tag the target.** `logic_space.Phase(angle: PI, where: ...)` marks satisfying states with a negative phase (the delete tag).
* **Step 3: Interfere.** `logic_space.Reflect(axis: Axis.MEAN)` converts the tag into amplitude gain for the marked candidate and suppression for everything else.
* **Step 4: Iterate sculpting.** Repeat the tag + reflect pair to sharpen the solution before measurement.

---

### 4. `qft_3.psi` (Quantum Fourier Transform)
**Goal:** Transform data from amplitude encoding to frequency encoding. This is the engine behind Shor's Algorithm (breaking encryption).

* **Logic:** QFT encodes frequency into **phase tags** that fall off geometrically. The tags, not rotations, are the payload.
* **Step 1: MSB tagging.** Superpose Q0, then apply coarse/fine tags (`PI/2`, `PI/4`) conditioned on lower qubits to encode periodicity.
* **Step 2 & 3: Middle/LSB.** Repeat tagging for Q1 and Q2 with decreasing angles.
* **Step 4: Pivot order.** Swap ends with `Flip` so the frequency bits emerge in the standard order.
* *Note:* This shows `Phase` as frequency etching, not deletion.

---

### 5. `adder.psi` (Ripple Carry Adder)
**Goal:** Perform classical arithmetic (A + B) using quantum reversible logic.
*Inputs:* Q0 (A), Q1 (B). *Outputs:* Q1 (Sum), Q2 (Carry).

* **Step 1: Carry pivot.** `reg.Flip(target: 2, where: reg[0] == 1 && reg[1] == 1)` routes the carry bit using a conditional pivot (Toffoli).
* **Step 2: Sum pivot.** `reg.Flip(target: 1, where: reg[0] == 1)` implements XOR as a controlled pivot.
* *Insight:* Pure `Flip` flows recover classical reversible logic; no sculpting/phase tagging required.

---

### 6. `ghz.psi` (Three-Way Entanglement)
**Goal:** Build a GHZ state `( |000> + |111> ) / sqrt(2)` that shows perfect three-party correlation.

* **Step 1: Seed the block.** `ghz.Superpose(targets: 0)` starts the two-peak landscape.
* **Step 2: Pivot to share phase.** Controlled `Flip` calls copy the phase tag to the remaining qubits.
* **Outcome:** Only `000` or `111` survive collapse; mixed outcomes vanish.

---

### 7. `bernstein_vazirani.psi` (Hidden String Recovery)
**Goal:** Learn a hidden classical string `s` with a single oracle query using phase kickback.

* **Step 1: Spread queries.** `bv.Superpose(targets: ALL)` expands to every candidate.
* **Step 2: Phase oracle.** `bv.Phase(angle: PI, where: ...)` tags any query with parity 1 with a negative amplitude.
* **Step 3: Decode tags.** Another `bv.Superpose(targets: ALL)` converts the phase pattern back into amplitude peaks.
* **Outcome:** Measurement yields `101` with certainty; the negative tag was sculpted into a unique survivor.

---

## 🛠 PsiScript Primitive Reference

| Primitive | Syntax | Physics (Transpiler Output) | Description |
| :--- | :--- | :--- | :--- |
| **Superpose** | `.Superpose(targets: ALL | [i...])` | **Hadamard (H)** | Expansion: create the block of possibilities. |
| **Phase** | `.Phase(angle: θ, where: predicate)` | **Z / Controlled Phase / Oracle** | Chisel: tag regions in the imaginary plane (delete tags or frequency tags). |
| **Reflect** | `.Reflect(axis: Axis.MEAN)` | **Diffusion Operator** | Interference trigger: turn tags into probability changes. |
| **Flip** | `.Flip(target: i, where: predicate | when: classical)` | **X / CNOT / Toffoli** | Pivot: reroute indices / apply classical fixes without new tags. |

---
*PsiScript v1.1 - Interference Sculpting Framework*
