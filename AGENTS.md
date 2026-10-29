# qscript — AI Agent Reference

qscript is a concept-phase quantum description language with an interference
sculpting logic layer and an explicit analog/pulse layer. It provides a shared
parser, an ideal single-register statevector simulator, a full named qubit-gate
catalog, experimental OpenQASM 2.0 export, pulse schedules and educational viewers.
It is not a complete interpreter, hardware toolchain or microwave simulator.
Internal Psi names and .psi extensions are qscript artifacts, not another product.

## Read order and sources of truth

1. [LICENSE](LICENSE) governs reuse. Preserve the MIT notice.
2. Tests specify only what they assert: [parser](tests/test_parser.py),
   [pulse](tests/test_pulse_compiler.py), [gate/QASM](tests/test_quantum_gates.py),
   [statevector](tests/test_quantum_simulator.py), [viewer](tests/test_viewer.py).
3. Inspect the implementation owner below before trusting prose.
4. [The manual](qscript-Definition.md) owns syntax;
   [gate reference](explain/gate-reference.md) owns gate conventions/math/sources;
   [README](README.md) owns public commands;
   [example guide](qscripts/EXAMPLES.md) owns algorithm intent.
5. [v1.2 rationale](definitions/v1.2-upgrade.md) and
   [v1.1 rationale](definitions/v1.1-upgrade.md) explain design, not feature status.
   This handbook owns conceptual anchors, known gaps and planned work.
6. [Interference teaching](explain/interference-basics.md) and
   [the notebook](explain/viewing-distribution.ipynb) are not hardware or complexity
   contracts. History is not a feature registry.

Distinguish intended semantics from executable behavior. Fix discrepancies in
scope and synchronize affected documentation; otherwise record the gap here.
There are no separate tracked security/privacy/product-principle documents.

## Collaboration and maintenance

- Read every applicable AGENTS.md completely at task start. This root owns all
  subsystems; no nested instruction files currently exist.
- Check branch and working tree before editing. Preserve unrelated work. The
  repository has no tracked submodules, workspace manifests or CI configuration.
- Keep this handbook, manual, README and example guide synchronized with durable
  changes in the same coherent edit batch. Update ownership when symbols move.
- Run focused checks and the full standard-library suite. Semantic fixes require
  meaningful regression coverage. Run optional numerical/rendering tests when
  their dependencies are available; disclose skipped checks.
- Python, .psi and documentation are source. build/, dist/, bytecode, environments
  and notebook checkpoints are derived/local; do not commit runtime artifacts, except deliberately maintained README screenshots in assets/.
- Keep future work in Planned below or a deliberately introduced authoritative
  design/backlog document. Label intent; do not invent hardware/optimization claims.
- No branch/commit/tag/release convention is defined. Follow explicit task instructions.
- Before committing, review the complete diff, changed facts, links and whitespace.
  Include this handbook with changes it describes, retain explicit gap labels and
  remove stale workarounds. Do not add a chronological commit diary.
- Handoff reports checks run, skipped checks and material limitations. No changed
  durable knowledge means no cosmetic handbook edit is required.

## Essential principles and contracts

### Preserve quantum, classical and pulse domains

The core remains Superpose (expansion/H), Phase (basis-state tagging), Reflect
(mean interference), and Flip (routing/X). Named Gate, logical Turn and Interact
expand through Superpose/Phase/Flip; no new irreducible primitive is required.
`where` is quantum selection; `when` is a classical guard. Analog addresses
explicit pulse time on wires. Pulse metadata is not a logical oracle.

The mental model expansion → phase tagging → interference → routing is conceptual,
not a mandatory order. Phase tagging alone does not remove probability. Measurement
produces classical outcomes; subsequent quantum operations act on the collapsed state.

- **Bit order:** register indices use q0 as the least significant bit; printed kets
  are high-bit first. Local named-gate matrices use the first target as their most
  significant bit. Preserve this distinction when embedding reversed/nonadjacent wires.
- **Exact phase:** unqualified Phase multiplies the entire state by exp(i angle).
  P and RZ differ by global phase. Simulation/reference comparisons retain it;
  OpenQASM 2 omits global phase with comments. Do not substitute U1 on q0.
- **Interactions:** RAA(theta)=exp(-i theta A⊗A/2). RXY(theta) means
  exp[-i theta (XX+YY)/4], not a tensor X⊗Y rotation. FSIM uses exp(-i phi)
  on 11, following Google; the reviewed Wikipedia row has the opposite sign.
  ECR operand order and Margolus/RCCX phases are specified in the gate reference.
- **Named gates:** ordered, distinct, in-range operands and finite parameters;
  intrinsic controls precede target wires. Every entry supports inverse and when.
  Extra where on named gates is rejected. Primitive Flip predicates must be
  invariant under target flips; do not execute a nonunitary pair permutation.
- **Dual parser representation:** parse() returns registers/flat operations and
  retains parser.statements. PulseScheduler reparses that tree for nesting/timing.
  Preserve scope/analog_context/default_register in both walks. Parse before scheduling.
- **Payload compatibility:** PsiOperation has gate/parameters/inverse plus the old
  logic/pulse fields. targets == ["ALL"] remains a sentinel. StepSnapshot adds
  operation/comparison and copies amplitudes/classical bits so collapse cannot
  mutate history. The viewer still exposes imported QuantumSimulator for callers.
- **Measurement:** project using P_m|psi>/sqrt(p_m), retain phase and normalization.
  The measurement panel shows pre-collapse probabilities beside post-collapse state.
  Shots rerun the entire circuit, including mid-circuit guards. Conditional exact
  probabilities from one trajectory can differ from aggregate shot frequencies.
- **QASM:** named gates lower through the shared primitive synthesis. Supported
  predicates are same-register conjunctions; unsupported predicates/guards raise.
  Classical guards require an existing measured register == an in-range integer.
  All basis changes/compute/uncompute gates must share the guard. Ancillas start
  clean and must be uncomputed. A local qelib evaluator tests equivalence; external
  QASM conformance and hardware behavior remain unverified.
- **Pulse time:** sequential durations add, Align branches share a start and advance
  by the longest branch. Register-filtered events still consume enclosing time.
  _parse_duration is permissive, with dt factor 1.0 rather than calibration.
- **Pulse lifecycle:** PulseSimulator calls on_start, sorted on_event, on_finish.
  Bloch replay initializes addressed wires at +Z, applies Rotate and ShiftPhase,
  and imports no preceding logic state. Logging reuse accumulates events and Bloch
  reuse retains keys; do not promise isolated reuse without fixing/testing resets.
- **Resources:** statevectors allocate 2**N amplitudes and snapshots copy them.
  Dense circuit matrices are limited to eight qubits. Plot truncation is explicitly
  labeled; JSON reports retain full data. No performance or speedup claims follow.

## Ownership and data flow

`.psi path` → QScriptParser → register map, flat PsiOperation list, structured tree.
Logic: flat operations → QuantumSimulator → StepSnapshot → InterferenceViewer.
QASM: selected register → OpenQasmCompiler → shared synthesis → QasmBuilder.
Pulse: structured tree → PulseScheduler → PulseSchedule → optional backend replay.
All run locally. There are no services, databases, workers or hardware adapters.

### [psi_lang.py](psi_lang.py)

Owns syntax, records and expressions; no NumPy/Matplotlib import. _gather_statements
tracks call/list depth, quotes, comments and braces, including multiline calls.
_walk flattens recognized operations; unknown blocks still traverse children once.
_parse_operation handles original primitives, Gate/direct names, Turn, Interact,
and pulse/Align/branch headers. It lazily imports the standard-library gate catalog
for arity/parameter validation. _parse_measurement handles Measure(reg[i]),
Measure(reg), reg.Measure(), and optional target/when arguments. parse validates
register ownership and indices, rejecting cross-register quantum predicates.
_split_args keeps nested commas intact. Predicates support != without corrupting
negation. eval_angle and predicate helpers use Python eval/compile, not a sandbox.
parse_conjunctive_controls fully matches simple terms and rejects repeated controls.

### [quantum_gates.py](quantum_gates.py)

Owns GATES/GateSpec, ALIASES/canonical_name/validate_gate, analytic gate_matrix,
and decompose_gate into only superpose/phase/flip records. Reference generation
and primitive expansion are separate paths; controlled arbitrary blocks use
_euler and _sqrt_unitary with Barenco recursion. Decomposition restores basis
changes/controls and preserves exact phases. No numerical or GUI dependency.
The complete catalog and explicit sign/operand conventions are maintained in
[explain/gate-reference.md](explain/gate-reference.md), including the reviewed source.

### [quantum_simulator.py](quantum_simulator.py)

Owns ideal NumPy logic evolution, moved out of the viewer. QuantumSimulator.run
resets its state/snapshots/RNG on reuse; accepts a normalized complex initial state
or a high-bit-first basis string. primitive_action executes the sculpting core;
reference_action uses theory and apply_matrix embeds ordered local matrices.
gate_comparison compares full local reference/primitive matrices. circuit_unitary
compares small complete circuits and rejects nonunitary/guarded/pulse operations.
reduced_density_matrix, bloch_vector, entropy and pair_diagnostics implement partial
traces, purity, entropy, connected correlations, Wootters concurrence and mutual
information. sample_shots reruns full causal circuits. Pulses are no-ops here.

### [compiler/qasm_compiler.py](compiler/qasm_compiler.py)

Owns OpenQASM, pulse scheduling, replay and compiler CLI. _emit_gate invokes shared
synthesis; _emit_phase/_emit_flip support conjunctions and clean ancilla networks.
_emit_with_when rejects unsupported guards and applies valid ones to whole networks.
QasmBuilder allocates declarations before use and rejects incompatible classical
register sizes. Reflect emits diffusion up to an explicitly omitted global -1.
Pulse emitters are comments. main selects one register and owns --out, --pulse-json,
--pulse-table, --simulate-pulses and --simulate-bloch; either simulation flag builds
a schedule. --pulse-json - also prints QASM unless redirected to --out.

PulseScheduler.build/_compile_block/_compile_align/_lower_pulse_op preserve
structured timing and filtering. PulseLayerCompiler is its compatibility alias.
PulseEvent/PulseSchedule own JSON/table export. PulseBackend defines callbacks;
LoggingPulseBackend counts records, BlochSimulatorBackend handles ideal independent
signed-axis rotations and frame phase. PulseSimulator does not evaluate guards.
Play/Acquire do not currently inherit a target index, though they retain a register.

### [viewer-references/psi_interference_viewer.py](viewer-references/psi_interference_viewer.py)

Owns Matplotlib UI and report/export CLI; imports/reexports QuantumSimulator.
InterferenceViewer links timeline, 3D basis bars, reduced Bloch vectors, selected
one/two-wire density, connected correlations, measurement/shot bars and Re/Im
matrix comparison (measurement steps show projector/post-collapse matrices). It
retains widget objects and updates slider limits per circuit.
Left/right steps, Q cycles pairs, C circuits, W wave mode, M matrix component.
CLI: multiple script paths, --register, --seed, --qubits, --initial, --shots,
--step (-1 final), --save, --report, --unitary, --no-show, --list-gates, --matrix,
--params. Reports are arrays of per-circuit dictionaries; complex arrays encode
separate real/imag lists. Keep measurement classical/quantum domains explicit.

### Continuous wave lens and screenshot assets

[viewer-references/wave_interaction_viewer.py](viewer-references/wave_interaction_viewer.py)
owns wave_field, gate_state and WaveInteractionViewer. The main circuit CLI now
defaults to --view waves; --view workbench preserves the diagnostic UI.
--wave-mode density/real/imaginary selects the initial surface. Wave controls
include step, fractional gate progress, timer playback, mode and circuit selection.
Gaussian/Hermite orthonormal modes encode the selected joint state; mixed
reductions show density only. Interpolation is an ideal principal-eigenphase
unitary path, not physical pulse time. Measurement jumps at the endpoint.
The one-wire view adds a vacuum spectator. tests/test_viewer.py covers mode
normalization, density consistency, nonseparability, mixed-state handling,
unitary interpolation, collapse jumps and controls.
assets/generate_screenshots.py regenerates four intentional tracked README PNGs;
run with optional viewer dependencies. qscripts/wave_interference.psi illustrates
phase tagging/decoding followed by exchange. Keep screenshot captions and math
representation limits synchronized with these owners.

### [viewer-references/wave_viewer.py](viewer-references/wave_viewer.py)

Independent QuantumScene spatial-grid teaching model: analytic plane waves,
Gaussian packets, Hermite oscillator modes, normalization and render_3d. It has
no parser caller, circuit CLI, gate equivalence or automated tests.

### Examples and human documentation

[qscripts/EXAMPLES.md](qscripts/EXAMPLES.md) owns the file-by-file guide.
Bell/GHZ prepare correlated states before measurement; teleport starts a zero
payload. interactions/exchange demonstrate entangling versus excitation-preserving
gates and feed-forward. bell_unitary/bell_primitives allow full-transform comparison.
qft_3 now implements the complete positive-sign QFT with an endpoint SWAP and
full DFT regression. Bernstein–Vazirani's multiline OR oracle parses and recovers
101 in the simulator; QASM rejects the OR. Grover also parses but has no success
probability regression and its OR clauses exceed QASM. odder remains a carry/sum
sketch with unused ancilla and no prepared inputs; preserve its existing filename.
ghost_filter emits a 90 ns pulse schedule, without modeling noise suppression.

[README](README.md) owns public setup/commands; [manual](qscript-Definition.md) owns
implemented syntax versus planned bridging. [Gate reference](explain/gate-reference.md)
owns the catalog, mathematical definitions, diagnostics and source conventions.
The manual also owns the beginner learning path and execution-order primitive
recipes: it defines amplitudes, phase, controls and bit order before giving
single-wire, interaction, swap and controlled-unitary constructions. Recipe
arrows run left to right; conventional matrix products run right to left.
Some hand-written recipes are shorter exact equivalents of the emitted Euler
sequences; quantum_gates.decompose_gate remains the executable source of truth.
When changing synthesis, validate the manual's paired runnable examples and
its phase/angle conventions against that owner, not just the recipe prose.
Upgrade/teaching prose still contains planned/unsupported constructs: def pulse,
.apply, repeat, whole-register predicates and physical/speedup metaphors must not
be read as implemented guarantees. The notebook builds independent four-qubit
arrays and writes quantum_visualization.png relative to its execution directory;
that generated path is not specifically ignored. [.gitignore](.gitignore) is a
broad Python template, not proof those frameworks are in use.

## Test ownership and commands

| Owner | Covered contracts | Remaining boundaries |
| --- | --- | --- |
| tests/test_parser.py | Analog targets; all named entries; multiline calls; aliases; measurements; malformed gates/operands; Boolean !=; examples parse | General grammar/unknown-block diagnostics; expression safety; deep nesting |
| tests/test_quantum_gates.py | Catalog coverage; reference unitarity; exact expansions/adjoints and angle edges; independent emitted-QASM equivalence with ancilla restoration; guard failure/basis changes | External parser/vendor validation; topology/cost; broad primitive predicate synthesis |
| tests/test_quantum_simulator.py | Arbitrary states/reversed/nonadjacent wires; Bell/GHZ reductions; endian/Y sign; global phase; collapse/snapshot isolation; seeded full-circuit shots/feed-forward; BV; full QFT/DFT and equivalent Bell transforms | Arbitrary-payload teleportation; Grover probability; large-register performance |
| tests/test_viewer.py | Agg export; gate/measurement/pulse steps; wave/matrix controls; qubit/circuit switching; single-qubit/initial-only view | Native GUI event loop/platforms; notebook/analytic viewer |
| tests/test_pulse_compiler.py | Sequential/parallel timing; event replay; X/frame-Z Bloch rotation | Complex nesting, filtered timing, unit edges, signed axes, reuse, CLI combinations |

Parser/pulse legacy temporary helpers leave files behind; new logic fixtures
register cleanup. Optional numerical/render tests skip when dependencies are absent.
Core tests remain standard-library-only. Do not hard-code suite counts here.

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s tests -p test_quantum_gates.py -v
python3 -m pip install -r requirements-viewer.txt
MPLBACKEND=Agg python3 -m unittest discover -s tests -v
python3 compiler/qasm_compiler.py qscripts/interactions.psi --out build/interactions.qasm
python3 compiler/qasm_compiler.py qscripts/ghost_filter.psi --pulse-table --simulate-bloch
MPLBACKEND=Agg python3 viewer-references/psi_interference_viewer.py qscripts/interactions.psi --step 1 --save build/interactions.png --report build/interactions.json --no-show
MPLBACKEND=Agg python3 viewer-references/psi_interference_viewer.py qscripts/bell_unitary.psi qscripts/bell_primitives.psi --unitary --report build/bell.json --no-show
git diff --check
```

Core tests are checked with Python 3.9; numerical/Agg rendering checks also use
Python 3.12 with NumPy/Matplotlib. requirements-viewer.txt lists optional minima,
not a lockfile or supported-version/platform matrix. Native GUI display is not
verified by Agg. There is no CI, package/release/deployment workflow or linter.
Explicit output options overwrite destinations; keep outputs in build/ or temp.

## Known gaps and planned work

### Current gaps

- Unknown statements can disappear; unknown block bodies execute once rather than
  implementing if/loops/function definitions. Custom def pulse/.apply is absent.
- One selected register only; no cross-register state/entanglement ownership.
- Primitive OR/non-conjunctive oracles simulate but do not lower to QASM. Named
  gates do not accept arbitrary additional quantum guards. No topology optimization.
- Pulse replay ignores guards, logic initialization and entanglement. Units/angles
  are permissive, dt uncalibrated, envelope/readout metadata nonphysical. Reuse
  reset behavior and filtered timing lack focused tests. Pulse-verb where keys
  are not consistently rejected even though they do not implement quantum control.
- Statevector/shot cost scales classically with the full register and program;
  GUI rendering truncates bars, not simulation. No noisy or mixed joint-state input.
- QASM tests use an independent local evaluator; no external conformance, hardware,
  calibration, noise-cancellation or compiler optimality guarantee.
- Teaching/upgrade documents still include intended syntax and metaphors beyond
  the implementation. Grover/teleport/arithmetic claims need focused algorithm tests.

### Planned

These are intent, not implemented capabilities or ordered commitments:

- Broaden quantum predicate synthesis beyond conjunctions; add formal grammar,
  diagnostics, expression trust boundaries and actual control-flow semantics.
- Extend pulse coverage for invalid units, filtered/nested time, repeated backend
  use and signed axes; consider CI and a supported dependency/platform matrix.
- Explore waveform libraries/hardware adapters. Existing schedules and backend
  hooks do not implement sampled waveform generation or physical execution.
- Implement the manual's custom pulse-gate bridge while preserving the
  quantum/classical/pulse distinction and PulseLayerCompiler compatibility alias.
- Extend algorithm regressions and external QASM conformance checks; investigate
  circuit synthesis cost and larger-state performance without implying speedups.

Do not invent priorities, dates or feature commitments. Move intent to implemented
status only after code and validation establish it. Keep the MIT license notice.
