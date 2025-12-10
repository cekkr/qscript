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

## Repository Map
- `PsiScript-Definition.md` – Technical reference and semantics for the language (v1.0).
- `psiscripts/` – Worked examples (teleportation, Grover SAT, QFT3, GHZ, BV, etc.) using the four primitives.
- `viewer-references/` – Python helpers to visualize interference patterns and build intuition for quantum circuits.
- `compile/` (future) – Experimental Python-based compiler to transpile PsiScript into OpenQASM.

## Visualizing Interference (Python)
The `viewer-references/wave_viewer.py` script sketches a 2D quantum “scene” with plane waves, Gaussian packets, and harmonic oscillator modes, then renders probability density with phase coloring.

Run locally (Python 3, `numpy`, `matplotlib`):
```bash
python viewer-references/wave_viewer.py
```
Try toggling the Gaussian packet setup vs. the harmonic oscillator section to see how interference and phase coloring relate to circuit-level phase logic.

## Learning the Language
Start from `PsiScript-Definition.md` for syntax and synthesis rules. Then open `psiscripts/EXAMPLES.md` and the corresponding `.psi` files to see how common algorithms are expressed geometrically. As the compiler matures, the `compile/` area will house the OpenQASM transpilation pipeline so PsiScript can target real hardware backends.
