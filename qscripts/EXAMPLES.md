# qscript examples

All files use a single selected register. Register bitstrings are high-bit first,
with q0 least significant. Logic gates run in the ideal statevector simulator;
pulse steps are annotations there. See the [manual](../qscript-Definition.md) and
[gate reference](../explain/gate-reference.md) for syntax and matrix conventions.
For a line-by-line introduction to Bell states, phase interference and controls,
start with the [learning manual](../qscript-Definition.md#1-a-first-program-line-by-line).
Its [primitive recipes](../qscript-Definition.md#7-reading-primitive-recipes) explain
how the named gates in these examples reduce to Superpose, Phase and Flip.

| Script | Purpose and current boundary |
| --- | --- |
| [bell_pair.psi](bell_pair.psi) | Superpose q0, controlled Flip q1, then measure. Before collapse, amplitudes are (00+11)/sqrt(2); shots produce only 00/11. |
| [bell_unitary.psi](bell_unitary.psi) / [bell_primitives.psi](bell_primitives.psi) | Equivalent named-gate and primitive Bell transforms without measurement; compare complete matrices with `--unitary`. |
| [interactions.psi](interactions.psi) | RXX creates entanglement, followed by RZ, sqrt(SWAP), fSim, partial measurement and feed-forward. Step 1 shows zero local Bloch vectors and unit pair concurrence. |
| [exchange.psi](exchange.psi) | Prepare 01, then XY exchange and Givens rotation before measurement. XY rotates within 01/10 rather than creating 00/11 population. |
| [teleport.psi](teleport.psi) | Partial measurement and classical X/phase corrections on Bob's wire. The file starts with a zero payload; it is not a test of arbitrary-state teleportation. Everything remains local. |
| [ghost_filter.psi](ghost_filter.psi) | Aligned analog echo description with a 90 ns schedule. Ideal independent Bloch replay is available, but noise suppression is not modeled. |
| [grover_sat.psi](grover_sat.psi) | Two SAT oracle/mean-reflection cycles and measurement. Multiline calls now parse and simulate; its OR predicates are rejected by QASM. Comments are not success-probability guarantees. |
| [qft_3.psi](qft_3.psi) | Complete positive-sign three-qubit QFT, including endpoint SWAP. Tests compare the entire transform with `exp(2 PI i j k/8)/sqrt(8)` for every input basis state. |
| [ghz.psi](ghz.psi) | Prepare (000+111)/sqrt(2) before measurement. Its reduced pairs are classically correlated with zero pair concurrence. |
| [bernstein_vazirani.psi](bernstein_vazirani.psi) | Parity phase tagging and Hadamard decoding recover 101; the simulator regression checks this exact file. Multiline parsing works; QASM rejects its OR oracle. |
| [odder.psi](odder.psi) | Existing carry/sum sketch: no input preparation or measurement, and an unused fourth wire. Arithmetic correctness remains untested. |

## Run and compare

```sh
python3 -m pip install -r requirements-viewer.txt
python3 viewer-references/psi_interference_viewer.py qscripts/interactions.psi qscripts/exchange.psi --seed 1 --shots 500
python3 viewer-references/psi_interference_viewer.py qscripts/ghz.psi --qubits 0 2 --step 3
python3 viewer-references/psi_interference_viewer.py qscripts/qft_3.psi --initial 101

MPLBACKEND=Agg python3 viewer-references/psi_interference_viewer.py qscripts/bell_unitary.psi qscripts/bell_primitives.psi --unitary --report build/bell.json --save build/bell.png --no-show
python3 compiler/qasm_compiler.py qscripts/interactions.psi --out build/interactions.qasm
python3 compiler/qasm_compiler.py qscripts/ghost_filter.psi --pulse-table --simulate-bloch
```

Left/right steps through a circuit. Q changes the selected wire pair, C changes
circuits, W switches probability/real/imaginary amplitude, and M switches matrix
real/imaginary components. The matrix panels compare analytic gates with their
primitive expansion, retaining global phase in the simulator. `--report` exports
complex values and diagnostics. `--unitary` requires a circuit with no measurement,
guard or pulse annotation; `--shots` reruns all measurements and corrections.

## Small primitive core

- `Superpose`: Hadamards; repeated application can decode phase patterns.
- `Phase`: exp(i angle) on matching basis states, or a global phase without `where`.
- `Flip`: X on a target with quantum `where` or classical `when`; quantum conditions
  must be invariant under flipping the target.
- `Reflect`: full-register inversion about the mean.
- `Turn`, `Interact`, and named `Gate` calls expand into this core. They are logical
  unitaries, distinct from timed `Rotate` inside the analog layer.
- `Analog`, `Rotate`, `Wait`, frame operations, `Play`, `Acquire` and `Align` retain
  pulse-time intent. Acquisition events do not measure the logic simulator.

One-qubit mixedness or a nonzero correlation is not itself proof of pair
entanglement. The viewer supplies both concurrence and mutual information;
measurements retain their pre-collapse probabilities beside the collapsed state.

## Continuous wave lens

The circuit viewer defaults to `--view waves`: before/during/after continuous
3D surfaces with a gate-fraction slider and Play/pause. `--wave-mode real` or
`imaginary` shows signed wave amplitudes; density is the default. Use
`--view workbench` for the diagnostic panels described above.
The wave encoding uses Gaussian phi0 and first Hermite phi1 modes:
Psi(x,y) = sum_ab c_ab phi_a(x) phi_b(y), in selected operand order.
These orthonormal coordinates illustrate interference and entanglement; they
are not hardware position or microwave fields. Mixed reductions display the
density kernel diagonal instead of a fabricated pure wavefunction. Gate
interpolation uses principal eigenphases of the ideal unitary; measurements
jump at fraction 1 and pulse annotations remain unchanged.
See the README screenshots and `assets/generate_screenshots.py` for reproducible
XX, XY, phase and measurement examples; `qscripts/wave_interference.psi` gives
a phase-tag/decode circuit (H Z H = X) followed by exchange.
