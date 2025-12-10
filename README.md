# PsiScript / qscript

(Concept phase)

PsiScript is a high-level, geometry-oriented quantum description language. Instead of chaining hardware-level gates, you script **geometric transformations and constraints** on a state vector using four primitives—`Superpose`, `Phase`, `Reflect`, and `Flip`. The goal is to keep the abstraction close to how a circuit actually behaves (compute–phase–uncompute, ancilla management, interference), while letting you reason in terms of amplitude geometry rather than gate soup.

```psi
let work = Register(3)
work.Superpose(targets: ALL)
work.Phase(angle: PI, where: work[0] == work[1])
let c0 = Measure(work[0])
if (c0) { work.Flip(target: 2, when: true) }
```

- `Superpose` spreads amplitude (Hadamards under the hood).
- `Phase` encodes logic as phase kickback (oracles with automatic compute/uncompute).
- `Reflect` amplifies marked states (diffusion).
- `Flip` entangles and moves data (X/CNOT/Toffoli families).

The language makes quantum/classical boundaries explicit: `where:` is a quantum predicate evaluated in superposition; `when:` is a classical guard after measurement.

## How 4 Primitives Cover the Usual Gate Zoo
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

## Repository Map
- `PsiScript-Definition.md` – Technical reference and semantics for the language (v1.0).
- `psiscripts/` – Worked examples (teleportation, Grover SAT, QFT3, GHZ, BV, etc.) using the four primitives.
- `viewer-references/` – Python helpers to visualize interference patterns and build intuition for quantum circuits (`wave_viewer.py`, `psi_interference_viewer.py`).
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
`viewer-references/psi_interference_viewer.py` loads a `.psi` file, simulates each primitive, and shows a 3D surface where height = probability density and color = phase. Use the slider/buttons to watch interference evolve and see measurement collapses annotated in the title.

```bash
# Teleportation, deterministic measurements via seed
python viewer-references/psi_interference_viewer.py psiscripts/teleport.psi --seed 1

# Choose a specific register if your script declares multiple
python viewer-references/psi_interference_viewer.py psiscripts/qft_3.psi --register q
```

## Learning the Language
Start from `PsiScript-Definition.md` for syntax and synthesis rules. Then open `psiscripts/EXAMPLES.md` and the corresponding `.psi` files to see how common algorithms are expressed geometrically. As the compiler matures, the `compile/` area will house the OpenQASM transpilation pipeline so PsiScript can target real hardware backends.

## Compiling to OpenQASM (experimental)
`compiler/qasm_compiler.py` is a best-effort translator from PsiScript to OpenQASM 2.0 (qelib1). It lowers:
- `Superpose` → H on each target.
- `Flip` → X/CX/CCX with automatic helper X gates for `== 0` controls.
- `Phase` → U1/CU1 for simple conjunctive `where` predicates (up to two controls), TODO for larger cases.
- `Measure` → OpenQASM `measure` with optional `when:` guards emitted as `if`.
- `Reflect` is documented but currently emitted as a comment placeholder.

Example:
```bash
python compiler/qasm_compiler.py psiscripts/teleport.psi --out build/teleport.qasm
```

The emitted QASM includes TODO comments where predicates are too complex to lower; extend `parse_conjunctive_controls` and the emitters to broaden coverage.
