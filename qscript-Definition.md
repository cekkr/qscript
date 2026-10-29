# qscript v1.2 — Hybrid Reference Manual

qscript separates quantum logic, classical measurement outcomes, and explicit
analog pulse timing. This document distinguishes executable syntax from design
intent. It is a prototype, not a complete interpreter or hardware toolchain.

## Registers, operands and expressions

`let reg = Register(N)` declares a positive literal number of qubits. The tools
select one register at a time (the first by default, or `--register name`).
Cross-register controls are rejected; declarations do not create a joint circuit.

q0 is the least significant register bit. Bitstring `101` means q2=1, q1=0,
q0=1. Ordered gate targets use the first operand as the most significant local
matrix bit. Thus `targets: [0,2]` uses basis `|q0 q2>` for its local matrix,
which is embedded in the full register `|q2 q1 q0>`.

Calls can span physical lines and end with an optional semicolon. `//` starts a
comment outside strings. Parameters accept arithmetic with `PI`, `pi`, and `tau`.
Input is trusted local source: expression evaluation is not a secure sandbox.

`where:` describes a quantum predicate on basis states in this register.
`when:` describes a classical condition; it does not create quantum control.
Quantum logic may continue after a measurement, acting on the collapsed state.
The ideal simulator evaluates Boolean predicates including `&&`, `||`, `!`,
`==`, and `!=`. OpenQASM lowering accepts conjunctions of `reg[i] == 0/1` or
truthy `reg[i]`, and classical `measured_register == nonnegative_integer` only.
Unsupported QASM predicates or guards fail explicitly.

## Logic primitives

| Primitive | Implemented behavior |
| --- | --- |
| `reg.Superpose(targets: ALL \| i \| [i,...], when: condition?)` | Hadamard on each selected wire. |
| `reg.Phase(angle: a, where: predicate?, when: condition?)` | Multiply matching amplitudes by exp(ia). Without `where`, multiply the entire state (global phase). |
| `reg.Flip(target: i, where: predicate?, when: condition?)` | Conditional X. The predicate must be invariant when the target flips. |
| `reg.Reflect(axis: Axis.MEAN, when: condition?)` | `2 mean(amplitudes) - amplitudes`, the full-register mean reflection. |

Phase tagging alone preserves basis probabilities. Interference through subsequent
operations converts relative phase into probability changes. `Phase` with
`where: reg[i]` is P(a)=diag(1,exp(ia)), which differs from RZ(a) by a global
phase. Unconditional Phase is an exact global phase in the simulator; OpenQASM
2 omits it with a comment, instead of applying a spurious U1 to q0.

## Named gates, rotations and interaction

These forms expand into the existing sculpting primitives:

```psi
let q = Register(3);
q.Gate(name: U, target: 0, theta: PI/2, phi: 0, lambda: PI/4);
q.Turn(axis: Y, target: 2, angle: PI/3);
q.Interact(axes: XX, targets: [0, 2], angle: PI/2);
q.Gate(name: CAN, targets: [2, 1], params: [PI/8, PI/9, PI/10]);
q.Gate(name: CCX, targets: [0, 1, 2], inverse: true);
```

- `Gate(name, targets/target, parameters..., inverse?, when?)` names an entry in
  the [complete catalog](explain/gate-reference.md). Named parameters or a
  `params: [...]` list supply the documented parameter order. Single-parameter
  gates accept `angle:` as an alias. Parameters must be finite.
- `Turn(axis: X|Y|Z, target, angle, inverse?, when?)` is a logical Pauli rotation,
  exp(-i angle Pauli/2). It has no duration or pulse envelope.
- `Interact(axes: XX|YY|ZZ|XY|ZX, targets: [a,b], angle, inverse?, when?)` is
  a two-wire logical interaction. XX/YY/ZZ/ZX use exp(-i angle A⊗B/2).
  XY means exp[-i angle (XX+YY)/4], an excitation-preserving exchange.
- Direct methods such as `q.RXX(targets: [0,2], angle: PI/2)` are equivalent to
  `Gate(name: RXX, ...)`. Original primitive method names keep their semantics.
- Targets are ordered, distinct and in range. Intrinsic controls are the leading
  targets. Named gates reject additional `where:`; use their controlled entries
  or primitive predicates. `inverse: true` takes the adjoint of any named gate.
- All of these are logic operations and are rejected inside Analog scopes.

The catalog implements the listed one-, two- and three-qubit unitary gates,
including interactions, swaps, fractional swaps, canonical entanglers and
controlled rotations. Reference matrices, sign conventions (especially fSim),
relative-phase Toffoli conventions, and source links live in the
[gate/matrix reference](explain/gate-reference.md).

## Measurement and classical correction

```psi
let pair = Register(2);
pair.Superpose(targets: 0);
pair.Flip(target: 1, where: pair[0] == 1);
let alice = Measure(pair[0]);
pair.Flip(target: 1, when: alice == 1);
let output = pair.Measure();
```

`Measure(reg[i])` samples and projects one wire, retaining entanglement/correlation
with the rest. `reg.Measure()` and `Measure(reg)` sample the whole register.
An assigned result is a classical integer; whole-register results use the same
high-bit-first numeric order. `reg.Measure(target: i, when: condition)` and
`Measure(reg[i], when: condition)` optionally guard measurement. A skipped
measurement neither collapses the state nor writes its destination.

The probability is `p_m = <psi|P_m|psi>` and the resulting state is
`P_m|psi>/sqrt(p_m)`. Snapshots copy amplitudes and classical bits, preserving
pre-measurement history. A seed gives repeatable trajectories. Full-circuit
shots rerun intermediate measurements and corrections, not merely the final
probability distribution.

## Analog pulse layer

```psi
let memory = Register(2);
Align {
    branch memory[0] {
        Rotate(axis: X, angle: PI, duration: 40ns);
        Wait(duration: 20ns);
        Rotate(axis: -X, angle: PI, duration: 40ns);
    }
    branch memory[1] { Wait(duration: 100ns); }
}
Analog(target: memory[0]) { ShiftPhase(angle: PI/8); }
```

`Analog(target: reg[i]) { ... }` enters explicit pulse time for a wire. Branch
headers can supply the same inherited wire. Sequential durations add; Align
branches share a start and advance enclosing time by their longest duration.

| Pulse verb | Current behavior |
| --- | --- |
| `Rotate(axis, angle, duration, shape?)` | Schedule ideal signed-X/Y/Z rotation and shape metadata. |
| `Wait(duration)` | Advance time. |
| `ShiftPhase(angle)` | Record frame phase; the ideal pulse Bloch backend applies a Z rotation. |
| `SetFreq(hz)` | Record a frequency/frame update. |
| `Play(waveform, channel)` | Record waveform-output intent. |
| `Acquire(duration, kernel)` | Record acquisition intent; it does not collapse a state. |

Pulse units convert approximately into nanoseconds: `dt` is not calibrated.
Malformed or unknown units are permissive and must not be treated as validated
hardware timing. Envelopes are metadata, not sampled signals. The pulse backend
starts independent qubits at +Z and does not import prior logic states. It models
neither entanglement nor noise, readout, calibration or physical emission.
Logic gates and quantum `where:` belong outside Analog. Pulse operations are
annotations in the logic simulator and comments in OpenQASM.

## Viewer, matrices and exports

Install [requirements-viewer.txt](requirements-viewer.txt), then run:

```sh
python3 viewer-references/psi_interference_viewer.py qscripts/interactions.psi qscripts/exchange.psi --qubits 0 1 --seed 1 --shots 500
MPLBACKEND=Agg python3 viewer-references/psi_interference_viewer.py qscripts/bell_unitary.psi qscripts/bell_primitives.psi --unitary --report build/bell.json --save build/bell.png --no-show
```

The workbench links timeline, probability/phase or signed-amplitude 3D bars,
reduced Bloch vectors, density matrices, connected Pauli correlations, concurrence,
mutual information, measurement probabilities and matrix comparison. Left/right
steps; Q chooses another pair; C switches circuits; W switches wave view; M
switches matrix real/imaginary parts. `--initial 101` prepares a basis input.
`--step` selects a view, with -1 (the default) meaning final. `--save` exports it.

`--report` writes an array of per-circuit reports: complex final state, all basis
probabilities, classical results, measurements, shots, selected reductions for
each step and analytic-versus-primitive gate matrices/errors. Complex values
are `{real: [...], imag: [...]}`. `--unitary` adds full circuit matrices and
comparisons to equal-sized supplied circuits; it requires unitary operations
without guards/pulses/measurements and limits dense matrices to eight qubits.

Reduced states use a partial trace and can be mixed even though the joint state
is pure. Nonzero correlations alone do not prove pair entanglement. A GHZ pair
illustrates classical correlations with zero pair concurrence. The reference
explains the diagnostic equations and numerical limits.

Storage is exponential in qubits and snapshots. Plots cap bars at 128 basis
states and histograms at 16 outcomes, with truncation labels; reports retain full
data. The independent `wave_viewer.py` draws analytic spatial fields and does
not simulate circuits.

## Planned syntax and remaining boundaries

Custom `def pulse SoftFlip(...) { ... }` and `reg.apply(SoftFlip, ...)` are design
intent, not implemented features. General `if`, `repeat`, and function blocks
are not interpreted: unknown block bodies are currently visited once. Use
explicit operations and operation-level `when:` for working programs.

The compiler supports complete catalog expansions and conjunctive primitive
controls; complex logical oracles still require additional synthesis. Pulse
scheduling is event metadata. Neither backend provides calibrated hardware
execution, and there is no joint-register simulator, noise model, topology
optimizer or external QASM conformance guarantee.

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
