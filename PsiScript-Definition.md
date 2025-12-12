# PsiScript v1.2 - Hybrid Reference Manual

PsiScript now supports the **Zoom Philosophy**: you can script at the logic layer (interference sculpting) or drop into the pulse layer (geometric drive trajectories). The language keeps the light JS/Python-flavored syntax, but you can now describe both *what* the algorithm should do and *how* the hardware should move.

---

## 1. Zoom: Logic Layer ↔ Pulse Layer

- **Logic Layer (The Sculptor):** Expand the $2^N$ space, tag regions with complex phase, trigger interference, and pivot/route indices. This is the v1.1 “Interference Sculpting” model.
- **Pulse Layer (The Composer):** Enter `Analog { ... }` to specify *physical* rotations, waits, and frame updates with durations and waveforms.
- **Visual Flow:** Blocks map to circuit lines. `Align` expresses “do these branches in parallel until the longest finishes.”

---

## 2. Syntax at a Glance (Hybrid)

```psi
// 1) Declare and sculpt logically
let q = Register(2)
q.Superpose(targets: ALL)
q.Phase(angle: PI, where: q[0] == q[1])

// 2) Zoom into pulses for a custom correction on q[0]
Analog(target: q[0]) {
    Rotate(axis: X, angle: PI/2, duration: 20ns, shape: Gaussian(sigma: 4ns));
    Wait(duration: 10ns);
    Rotate(axis: -X, angle: PI/2, duration: 20ns, shape: Drag(beta: 0.5));
    ShiftPhase(angle: PI/8); // frame tweak
}

// 3) Back to logic-time
q.Reflect(axis: Axis.MEAN)
let result = Measure(q[0])
```

`where:` remains a **quantum predicate** on superpositions; `when:` is a **classical guard** after measurement. `Analog` suspends `where:`—you are driving the wire directly with explicit time.

---

## 3. Logic Layer (Interference Sculpting)

### Registers & Guards
- `let reg = Register(N)` creates a $2^N$-dimensional space. Multiple registers are fine.
- `where:` entangles/tag states across the full superposition. `when:` gates classical corrections after measurement.
- Measurement is the irreversible wall; everything before it composes into one unitary sculpting step.

### Primitives
- **`Superpose(targets)` — Expansion**  
  Inflate the search space (`ALL` or indexed list). Circuit intuition: Hadamards.

- **`Phase(angle, where)` — Phase Etching**  
  Tag regions in the imaginary plane. `PI` marks deletes; fractional angles encode frequency (QFT-style). Circuit intuition: controlled-phase oracles.

- **`Reflect(axis)` — Interference Trigger**  
  Invert around the mean (Grover diffusion) to convert tags into probability shifts.

- **`Flip(target, where?, when?)` — Pivot/Route**  
  Conditional X. With `where` it entangles/reorders; with `when` it applies classical fixes (teleportation corrections, etc.).

---

## 4. Pulse Layer (Analog Scope)

Rules inside `Analog { ... }`:
- No `where:`—you are addressing a wire, not a superposition predicate.
- Time is explicit (`ns`, `dt`). Visualize the Bloch vector moving over time.
- Manage frames directly: virtual Z (`ShiftPhase`), frequency hops (`SetFreq`).

Pulse verbs:
- **`Analog(target: reg[i]) { ... }`** — Enter pulse-time for that qubit/line.
- **`Rotate(axis, angle, duration, shape?)`** — Geometric motion on the Bloch sphere with a drive envelope (e.g., `Gaussian`, `Drag`, `Slepian`).
- **`Wait(duration)`** — Idle with explicit time.
- **`ShiftPhase(angle)`** — Virtual Z/frame shift.
- **`SetFreq(hz)`** — Drive frame update (e.g., accessing sidebands/levels).
- **`Play(waveform, channel)`** — Raw arbitrary waveform emit.
- **`Acquire(duration, kernel)`** — Readout capture with a processing kernel.

### Parallel Flow
Use `Align { ... }` with `branch <label> { ... }` to express simultaneous actions. Each branch runs until the longest completes; useful for echo sequences alongside logical idling.

```psi
Align {
    branch q[0] { Rotate(axis: Z, angle: PI, duration: 100ns); }
    branch q[1] {
        Rotate(axis: X, angle: PI, duration: 40ns);
        Wait(duration: 20ns);
        Rotate(axis: -X, angle: PI, duration: 40ns);
    }
}
```

---

## 5. Bridging: Custom Gates from Pulses

Define a pulse implementation for a logic verb, then call it with `where:` like any other gate:

```psi
def pulse SoftFlip(target: Qubit) {
    Analog(target: target) {
        Rotate(axis: X, angle: PI, duration: 24ns, shape: Slepian(window: 0.3));
    }
}

let reg = Register(3)
reg.apply(SoftFlip, where: reg[0] && !reg[1]) // compiler substitutes the pulse schedule
```

This “trapdoor” lets you optimize hardware behavior without losing the declarative logic flow.

---

## 6. Execution Order & Time

- **Quantum-time (logic):** `Superpose`, `Phase`, `Reflect`, `Flip` compose as before. Multiple `where` clauses overlap and interfere.
- **Pulse-time (analog):** Inside `Analog`, steps follow real durations; `Align` synchronizes branches by wall-clock time.
- **Measurement boundary:** After `Measure`, only `when:` applies. You can re-enter `Analog` on surviving qubits for calibrated readout or resets.

---

## 7. Hardware & Visualization Notes

- Topology and ancilla costs still matter for logic predicates; pulse blocks let you side-step gate explosion with tailored trajectories.
- Frame tracking is explicit (`ShiftPhase`, `SetFreq`); envelope choices (`shape:`) capture leakage/DRAG concerns.
- The viewer in `viewer-references/` focuses on interference visuals; it records pulse steps for context but does not simulate microwave physics.
