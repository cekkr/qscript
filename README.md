# PsiScript / qscript (v1.2)

(Concept phase)

PsiScript now blends two layers:
- **Logic Layer (Interference Sculpting):** Expand a $2^N$ space, tag regions with complex phase, trigger interference, and pivot/route indices with four primitives (`Superpose`, `Phase`, `Reflect`, `Flip`).
- **Pulse Layer (Geometric Trajectories):** Drop into `Analog { ... }` to describe the actual rotations, waits, and frame updates that drive a qubit.

```psi
let work = Register(3)
work.Superpose(targets: ALL)                           // Logic: expansion
work.Phase(angle: PI, where: work[0] == work[1])       // Logic: tag

Analog(target: work[0]) {                              // Pulse: zoom in
  Rotate(axis: X, angle: PI/2, duration: 20ns, shape: Gaussian(sigma: 4ns));
  Wait(duration: 10ns);
  Rotate(axis: -X, angle: PI/2, duration: 20ns, shape: Drag(beta: 0.5));
  ShiftPhase(angle: PI/8);                              // Frame tweak
}

work.Reflect(axis: Axis.MEAN)                          // Logic: interference trigger
let c0 = Measure(work[0])                              // Collapse boundary
if (c0) { work.Flip(target: 2, when: true) }           // Classical correction (post-measure)
```

Logic primitives:
- `Superpose` inflates the search space.
- `Phase` is the logical chisel: tag states with imaginary phase (negative amplitude for deletes; fractional angles for frequency).
- `Reflect` converts tags into probability shifts via destructive/constructive interference.
- `Flip` pivots indices to entangle or reorder data; guarded by quantum `where` or classical `when`.

Quantum/classical boundaries stay explicit: `where:` is a quantum predicate across the full superposition; `when:` is classical after measurement.

Pulse primitives:
- `Analog(target)` enters physical time for that wire (no `where:` inside).
- `Rotate(axis, angle, duration, shape?)` sets the trajectory; `Wait(duration)` adds buffers.
- `ShiftPhase(angle)`, `SetFreq(hz)` keep frame tracking explicit.
- `Play(waveform, channel)` / `Acquire(duration, kernel)` expose raw emit/readout.
- `Align { branch ... }` expresses parallel branches that end together.

## How 4 Logic Primitives Cover the Usual Gate Zoo
PsiScript keeps the surface small and lets the compiler choose gates. A few common patterns:

- `Superpose(targets: i)` → Hadamard on qubit *i*.
- `Phase(angle: θ, where: reg[i])` → Z-rotation on *i*; add one control for CZ, two controls for CCZ, etc.
- `Flip(target: t)` → X on *t*; add controls in `where` for CX / Toffoli / multi-controlled X (with automatic helper X for `== 0` guards).
- `Reflect(axis: Axis.MEAN)` → Grover diffusion (H on all → X on all → multi-controlled Z → X on all → H on all).

Gate sketches in PsiScript:

```psi
// CNOT (control 0, target 1)
reg.Flip(target: 1, where: reg[0] == 1);

// Toffoli (controls 0 & 1, target 2)
reg.Flip(target: 2, where: reg[0] == 1 && reg[1] == 1);

// Controlled-Z (controls 0 & 1)
reg.Phase(angle: PI, where: reg[0] == 1 && reg[1] == 1); // CCZ with a single predicate

// SWAP(0,2) using three CNOT-equivalents
reg.Flip(target: 2, where: reg[0] == 1);
reg.Flip(target: 0, where: reg[2] == 1);
reg.Flip(target: 2, where: reg[0] == 1);
```

Everything stays at the “constraint” level; synthesis decides whether to emit qelib1 gates, ancilla ladders, or topology-aware swaps.

## Hybrid Pulse Layer (v1.2)
When you need hardware detail, drop into `Analog { ... }` to describe Bloch-sphere motion with explicit durations and envelopes. Use `Align` to show simultaneous branches (e.g., echo while a partner idles), and frame tools (`ShiftPhase`, `SetFreq`) to keep virtual Z tracking explicit. Pulse blocks compile into a Python-side pulse schedule via `compiler/qasm_compiler.py --pulse-*`; the QASM emitter still uses comments for pulse regions. The schedule can be replayed through a pluggable simulator backend (no physics yet).

## Repository Map
- `PsiScript-Definition.md` – v1.2 hybrid manual (logic sculpting + analog layer).
- `definitions/v1.2-upgrade.md` – Zoom philosophy/narrative for the hybrid model.
- `psiscripts/` – Worked examples (teleportation, Grover sculpting loop, QFT3 tagging, GHZ, BV, and pulse-level `ghost_filter` echo).
- `viewer-references/` – Python helpers to visualize interference patterns and build intuition for phase tagging and collapse (`wave_viewer.py`, `psi_interference_viewer.py`).
- `compiler/` – Experimental Python-based compiler that lowers PsiScript to OpenQASM (`qasm_compiler.py`).
- `psi_lang.py` – Shared parser/predicate utilities used by the viewer and compiler.

## Visualizing Interference (Python)

### Quick intuition (analytic waves)
`viewer-references/wave_viewer.py` sketches a 2D quantum “scene” with plane waves, Gaussian packets, and harmonic oscillator modes, then renders probability density with phase coloring.

Run locally (Python 3, `numpy`, `matplotlib`):
```bash
python viewer-references/wave_viewer.py
```
Try toggling the Gaussian packet setup vs. the harmonic oscillator section to see how interference and phase coloring relate to circuit-level phase logic.

### Step-by-step PsiScript playback
`viewer-references/psi_interference_viewer.py` loads a `.psi` file, simulates each primitive, and shows a 3D surface where height = probability density and color = phase. Use the slider/buttons to watch the sculpting process (phase tags → reflect → collapse) and see measurement events annotated in the title. Pulse-layer steps are logged as timeline context (no microwave simulation yet).

```bash
# Teleportation, deterministic measurements via seed
python viewer-references/psi_interference_viewer.py psiscripts/teleport.psi --seed 1

# Choose a specific register if your script declares multiple
python viewer-references/psi_interference_viewer.py psiscripts/qft_3.psi --register q
```

## Learning the Language
Start from `PsiScript-Definition.md` for syntax and the v1.2 hybrid semantics. Then open `psiscripts/EXAMPLES.md` and the `.psi` files to see how algorithms are expressed as “expand → tag → interfere → pivot → measure,” with optional `Analog` blocks for hardware-specific trajectories. As the compiler matures, the `compiler/` area will house the OpenQASM transpilation pipeline so PsiScript can target real hardware backends.

## Compiling to OpenQASM (experimental)
`compiler/qasm_compiler.py` is a best-effort translator from PsiScript to OpenQASM 2.0 (qelib1). It lowers:
- `Superpose` → H on each target.
- `Flip` → X/CX/CCX with automatic helper X gates for `== 0` controls.
- `Phase` → U1/CU1 for simple conjunctive `where` predicates (up to two controls), TODO for larger cases.
- `Measure` → OpenQASM `measure` with optional `when:` guards emitted as `if`.
- `Reflect` → Grover-style diffusion (H → X → multi-controlled Z → X → H) with an ancilla chain for 3+ qubits.

Pulse-layer ops (`Analog`, `Rotate`, `Wait`, `ShiftPhase`, `SetFreq`, `Play`, `Acquire`, `Align`) now lower into a timestamped Python schedule for synthesis; the OpenQASM output still records them as comments.

Example:
```bash
python compiler/qasm_compiler.py psiscripts/teleport.psi --out build/teleport.qasm
```

Pulse timelines (Analog/Rotate/Wait/ShiftPhase/SetFreq/Play/Acquire) can be inspected or simulated directly from Python:
```bash
# Text table
python compiler/qasm_compiler.py psiscripts/ghost_filter.psi --pulse-table

# JSON + lightweight simulator (console backend)
python compiler/qasm_compiler.py psiscripts/ghost_filter.psi --pulse-json build/ghost_filter.json --simulate-pulses
```

The emitted QASM includes TODO comments where predicates are too complex to lower; extend `parse_conjunctive_controls` and the emitters to broaden coverage.
