# PsiScript Algorithm Suite 🌌

Welcome to the **PsiScript** examples repository.

PsiScript v1.2 keeps the **Interference Sculpting** logic layer and adds a **pulse layer**. You still expand a massive block of possibilities, tag regions with complex phase, trigger interference, and pivot data—but you can now drop into `Analog { ... }` to describe the physical drive trajectories (rotations, waits, frame shifts) that make those logical moves happen.
1. **Logic primitives:** `Superpose`, `Phase`, `Reflect`, `Flip`.
2. **Pulse primitives:** `Analog`, `Rotate`, `Wait`, `ShiftPhase`, `SetFreq`, `Play`, `Acquire`, with `Align` for parallel branches.

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

### 3. `ghost_filter.psi` (Pulse Echo / Dynamical Decoupling)
**Goal:** Keep a single qubit “alive” while it idles by applying an echo sequence at the pulse layer.

* **Step 1: Seed the register.** `let memory = Register(1)` then `memory.Superpose(targets: ALL)` preps the block.
* **Step 2: Pulse layer echo.** Inside `Analog(target: memory[0])` a `Rotate`–`Wait`–`Rotate` sequence with explicit durations and shapes cancels accumulated phase noise. Wrapped in `Align` to emphasize the time-aligned flow.
* **Step 3: Measure.** Collapse to see the survived amplitude after the pulse treatment.

---

### 4. `grover_sat.psi` (3-SAT Solver / Database Search)
**Goal:** Find the specific input variables that satisfy a complex boolean formula without checking them one by one.

* **Step 1: Expand the search space.** `logic_space.Superpose(targets: ALL)` instantiates all 8 candidates.
* **Step 2: Tag the target.** `logic_space.Phase(angle: PI, where: ...)` marks satisfying states with a negative phase (the delete tag).
* **Step 3: Interfere.** `logic_space.Reflect(axis: Axis.MEAN)` converts the tag into amplitude gain for the marked candidate and suppression for everything else.
* **Step 4: Iterate sculpting.** Repeat the tag + reflect pair to sharpen the solution before measurement.

---

### 5. `qft_3.psi` (Quantum Fourier Transform)
**Goal:** Transform data from amplitude encoding to frequency encoding. This is the engine behind Shor's Algorithm (breaking encryption).

* **Logic:** QFT encodes frequency into **phase tags** that fall off geometrically. The tags, not rotations, are the payload.
* **Step 1: MSB tagging.** Superpose Q0, then apply coarse/fine tags (`PI/2`, `PI/4`) conditioned on lower qubits to encode periodicity.
* **Step 2 & 3: Middle/LSB.** Repeat tagging for Q1 and Q2 with decreasing angles.
* **Step 4: Pivot order.** Swap ends with `Flip` so the frequency bits emerge in the standard order.
* *Note:* This shows `Phase` as frequency etching, not deletion.

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

| Primitive | Syntax | Physics / Intent | Description |
| :--- | :--- | :--- | :--- |
| **Superpose** | `.Superpose(targets: ALL | [i...])` | **Hadamard (H)** | Expansion: create the block of possibilities. |
| **Phase** | `.Phase(angle: θ, where: predicate)` | **Z / Controlled Phase / Oracle** | Chisel: tag regions in the imaginary plane (delete tags or frequency tags). |
| **Reflect** | `.Reflect(axis: Axis.MEAN)` | **Diffusion Operator** | Interference trigger: turn tags into probability changes. |
| **Flip** | `.Flip(target: i, where: predicate \| when: classical)` | **X / CNOT / Toffoli** | Pivot: reroute indices / apply classical fixes without new tags. |
| **Analog** | `Analog(target: reg[i]) { ... }` | **Enter pulse-time** | Drive a specific wire with explicit durations; suspends `where:`. |
| **Rotate** | `Rotate(axis: X, angle: PI/2, duration: 20ns, shape: Gaussian(...))` | **Bloch trajectory** | Physical rotation with a shaped envelope. |
| **Wait** | `Wait(duration: 10ns)` | **Idle / free evolution** | Explicit buffer time. |
| **ShiftPhase / SetFreq** | `ShiftPhase(angle: PI/8)`, `SetFreq(hz: 5.1e9)` | **Frame ops** | Virtual Z or drive-frame hop. |
| **Play / Acquire** | `Play(waveform, channel)`, `Acquire(duration: 300ns, kernel: boxcar)` | **Raw emit/readout** | Arbitrary waveform playback and readout capture. |
| **Align / branch** | `Align { branch q[0] { ... } }` | **Parallel timing** | Run branches in parallel; finish when the longest branch ends. |

---
*PsiScript v1.2 - Hybrid Logic/Pulse Framework*
