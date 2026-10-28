# qscript — AI Agent Reference

This is the operational reference for agents working on qscript, a concept-phase quantum description language with an interference-sculpting logic layer and an explicit analog/pulse layer. The repository contains a shared Python parser, an experimental OpenQASM 2.0 compiler and pulse scheduler, educational viewers, and `.psi` examples. The v1.2 language vision is broader than the implemented subset: this is not a production hardware toolchain, a complete language interpreter, or a microwave physics simulator. Internal `Psi*` names and the `.psi` extension refer to qscript artifacts, not a separate product.

## Read Order and Sources of Truth

1. [LICENSE](LICENSE) governs reuse and redistribution. Preserve its MIT notice. There are no separate tracked security, privacy, or product-principle documents; the principles and boundaries below guide changes.
2. [Parser tests](tests/test_parser.py) and [pulse tests](tests/test_pulse_compiler.py) specify only the behavior they assert. They do not establish complete language support or compiler correctness.
3. [psi_lang.py](psi_lang.py), [compiler/qasm_compiler.py](compiler/qasm_compiler.py), and the [viewers](viewer-references/) establish current executable behavior. Inspect the owner before relying on a handbook claim.
4. [qscript-Definition.md](qscript-Definition.md) describes intended v1.2 syntax and semantics. Preserve its quantum/classical/pulse distinction, but check implementation coverage: pulse definitions, application, and general control flow are not implemented.
5. [README.md](README.md) owns the public overview and usage examples; [qscripts/EXAMPLES.md](qscripts/EXAMPLES.md) explains algorithm intent. Examples and prose are not proof of executable support.
6. [definitions/v1.2-upgrade.md](definitions/v1.2-upgrade.md) explains the hybrid design; [definitions/v1.1-upgrade.md](definitions/v1.1-upgrade.md) supplies older sculpting rationale. Neither proves planned features exist. This handbook owns the agent quick reference and [planned-work snapshot](#planned).
7. [explain/interference-basics.md](explain/interference-basics.md) and [the distribution notebook](explain/viewing-distribution.ipynb) are teaching material, not hardware or complexity contracts. Git history is historical context, not a feature registry.

When these disagree, distinguish intended semantics from actual behavior and report the mismatch. Do not silently turn an implementation defect into a language rule. Fix code/documentation discrepancies within task scope and synchronize affected documents in the same change; otherwise record the unresolved gap here. Ask for direction when a conflict cannot be resolved safely.

## Collaboration and Maintenance Rules

- Read all applicable `AGENTS.md` files completely at task start, from the repository root to the target directory. This root file currently owns all subsystems; no nested instruction files exist.
- Check the working tree and branch before editing; preserve unrelated changes. The project is a single repository with no tracked submodules, workspace manifests, or CI configuration.
- Keep this file synchronized with durable changes: update file subsections and symbols when ownership moves; update contracts, feature status, interfaces, commands, tests, and gaps when their facts change. Do this in the same coherent edit batch, not a later cleanup.
- Update [the manual](qscript-Definition.md), [README](README.md), and [example guide](qscripts/EXAMPLES.md) when their governed facts change. Keep agent conceptual anchors and TODOs in this handbook. Avoid duplicating the two upgrade narratives as competing implementation specifications.
- Run focused tests for the affected parser/scheduler/backend behavior and the full standard-library suite before handoff. Semantic fixes require meaningful regression coverage; document current missing coverage rather than implying tests exist.
- Treat `.psi` files and Python modules as source. `build/`, `dist/`, bytecode, virtual environments, and notebook checkpoints are derived/local paths ignored by [.gitignore](.gitignore). Do not edit generated QASM/JSON as the implementation or commit runtime output by accident.
- Record future work and research in this handbook's [Planned section](#planned), or in a deliberately introduced authoritative design/backlog document. Label intent as planned; do not call an optimization or hardware capability implemented without code and validation.
- No repository-specific branch, commit-message, version-tag, or release convention is defined. Follow explicit task instructions; do not invent a release process.
- Before each commit, review the complete diff and changed durable facts, remove stale paths/workarounds, synchronize docs, validate links and whitespace, and include the handbook with the change it describes. Partial implementations must retain explicit scaffold/gap labels. Do not add a chronological commit diary here.
- Report checks run, checks not run, and remaining limitations. Tasks with no changed durable knowledge do not require cosmetic handbook edits.

## Essential Project Principles

### Preserve the three execution domains

The logic vocabulary remains `Superpose`, `Phase`, `Reflect`, and `Flip`. `where:` describes a quantum predicate on basis states; `when:` describes a classical guard using measurement results. `Analog` addresses a physical wire with durations and frame operations. Do not reinterpret a classical outcome as a quantum control or claim that pulse metadata implements a logical oracle. The manual forbids `where:` inside analog scope; the parser does not currently enforce that boundary.

### Hybrid model quick reference

The v1.2 mental model is to sculpt a `2**N` state space through expansion → phase tagging → interference → routing, with measurement producing classical outcomes. Zoom into `Analog` for explicit pulse trajectories, timing, and waveform metadata. These are conceptual stages, not a mandatory operation order or proof of complete backend support.

| Primitive | Conceptual role and current boundary |
| --- | --- |
| `Superpose(targets)` | Expansion via Hadamards; another application also decodes phase patterns. |
| `Phase(angle, where)` | Tags matching amplitudes: `PI` changes their sign; fractional angles encode relative phase. Tagging alone does not delete probability or collapse the state. |
| `Reflect(axis: Axis.MEAN)` | Mean reflection converts relative phase tags into probability changes through interference. |
| `Flip(target, where?, when?)` | Pivots basis indices; quantum controls can entangle, while classical guards drive post-measurement corrections. |
| `Analog(target: reg[i])` | Enters explicit pulse-time for a wire; `where:` does not belong in this scope. |
| `Rotate(axis, angle, duration, shape?)` / `Wait(duration)` | Describes geometric motion and idle time. Shapes are retained metadata, not synthesized envelopes. |
| `ShiftPhase(angle)` / `SetFreq(hz)` | Makes frame changes explicit; the ideal Bloch backend applies only the phase shift as a Z rotation. |
| `Play(waveform, channel)` / `Acquire(duration, kernel)` | Describes raw waveform output/readout intent; current schedules retain events without physical emission or acquisition. |
| `Align { branch ... }` | Starts branches together and advances enclosing time by the longest duration. |

For conceptual examples, use [Grover](qscripts/grover_sat.psi) for tag/reflect cycles, [QFT](qscripts/qft_3.psi) for fractional phase tagging, [teleportation](qscripts/teleport.psi) for classical guards, [ghost filter](qscripts/ghost_filter.psi) for an aligned analog echo, [Bernstein–Vazirani](qscripts/bernstein_vazirani.psi) for parity phase tagging, and [Bell](qscripts/bell_pair.psi)/[GHZ](qscripts/ghz.psi) for entanglement scaffolding. Read their file subsections and known gaps before running them: Grover/Bernstein–Vazirani currently fail multiline parsing, and QFT remains a sketch.

### Share parsing; keep execution responsibilities separate

[psi_lang.py](psi_lang.py) owns syntax, operation records, and predicates without importing NumPy or Matplotlib. Compiler and viewer consume it. Keep statevector simulation in [the interference viewer](viewer-references/psi_interference_viewer.py), scheduling and OpenQASM emission in [the compiler](compiler/qasm_compiler.py), and visual intuition in [the wave viewer](viewer-references/wave_viewer.py). A syntax change must account for both flat-operation consumers and the scheduler's structured walk.

### State physical and algorithmic limits honestly

Pulse schedules describe events; they do not synthesize sampled waveforms or validate hardware calibration. The Bloch backend models independent ideal vectors, while the interference viewer treats analog operations as no-ops. Do not infer noise cancellation, entangling pulse physics, real hardware execution, or quantum speedups from illustrative prose. The statevector simulator explicitly allocates `2**num_qubits` amplitudes and copies them into snapshots.

## Critical Implementation Contracts

- **Dual parse representation:** `QScriptParser.parse()` returns `(registers, operations)` and also populates `parser.statements`. `_walk` flattens operations for compiler/viewer; `PulseScheduler._compile_block` reparses the statement tree to retain nesting and parallel timing. Call `parse()` before scheduling. Preserve context updates (`scope`, `analog_context`, `default_register`) in both paths. [Parser tests](tests/test_parser.py) cover inherited targets; [pulse tests](tests/test_pulse_compiler.py) cover basic scheduling.
- **Operation payload compatibility:** `PsiOperation` carries logic and pulse metadata; `targets == ["ALL"]` is a real sentinel despite the `List[int]` annotation. Do not replace it with an empty target list. `StepSnapshot` stores independent state/classical copies through `QuantumSimulator._record`; later measurement must not mutate earlier snapshots. Snapshot behavior has no automated coverage.
- **Time composition:** `PulseScheduler._compile_block` advances sequential durations; `_compile_align` gives branches the same start and advances by the longest branch. Frame operations normally have zero duration. Register filtering suppresses events but still contributes their durations to enclosing timing. Preserve this distinction; filtered timing and post-align continuation lack focused tests. See `test_simple_pulse_schedule` and `test_align_branches_share_start` in [pulse tests](tests/test_pulse_compiler.py).
- **Units are approximate:** `_parse_duration` converts recognized time units into nanoseconds; `dt` currently uses factor `1.0`, not a calibrated hardware tick. Missing/malformed durations become zero and unknown units fall back to factor `1.0`. Do not advertise this permissive parser as validation or calibration; unit edge cases have no tests.
- **QASM is incomplete output:** `OpenQasmCompiler` emits only a subset of logic gates and comments for all pulse operations. Complex predicates and larger controlled Phase/Flip cases produce TODO comments. `_emit_with_when` currently emits unconditional gates after an unsupported guard TODO; this is an active semantic defect, not an acceptable guard policy. Never use successful text generation as evidence that a complete, correct circuit was compiled. No QASM correctness tests exist.
- **Measurement and indexing:** `QuantumSimulator._index_to_bits` uses qubit 0 as the least significant bit; printed bitstrings place high bits on the left. `_apply_measure` samples/collapses and renormalizes a selected qubit, or replaces the whole state on register measurement. Preserve the distinction between amplitudes and squared probabilities. Measurement, endian ordering, and classical correction need tests.
- **Backend lifecycle:** `PulseSimulator.run` calls `on_start`, ordered `on_event`, then `on_finish`, returning the finish summary. `BlochSimulatorBackend` begins addressed qubits at `(0, 0, 1)` and does not import preceding logic gates. `LoggingPulseBackend` accumulates events across reuse; the Bloch backend retains keys across starts. Do not promise isolated repeated runs without fixing and testing reset behavior. Basic replay and X/frame-Z rotations are covered in [pulse tests](tests/test_pulse_compiler.py); signed-axis coverage is missing.

## Architecture and Data/Control Flow

`CLI script path` → `QScriptParser.parse()` → registers, flat `PsiOperation` list, and structured `_Statement` tree.

- **OpenQASM:** compiler `main` selects one register (the first declaration by default) → filters flat operations → `OpenQasmCompiler._emit_*` → `QasmBuilder.render()` → stdout or `--out` file. Other registers do not form a joint circuit in this path.
- **Pulse schedule:** parsed statement tree → `PulseScheduler.build()` / `_compile_block` / `_compile_align` → timestamped `PulseEvent` records → `PulseSchedule` JSON/table and optional `PulseSimulator` backend replay. Logic gates and measurement are not simulated by this scheduler.
- **Interference playback:** viewer `main` selects one register → `QuantumSimulator.run()` → `StepSnapshot` copies → `InterferenceViewer` slider/buttons and probability/phase surface. Pulse steps are annotations only.
- **Analytic teaching:** `QuantumScene` builds a separate two-dimensional wave grid → adds analytic waves → normalizes → Matplotlib rendering. It does not load `.psi` or emit gates.

All paths run locally in a single Python process. There are no external services, database, workers, plugin loader, deployment targets, or hardware adapters in the tracked tree. Filesystem reads, explicit output writes, expression evaluation, and GUI rendering are the present boundaries.

## Linked Source Tree and File Reference

### [psi_lang.py](psi_lang.py)

Owns shared parsing and expressions, not execution or drawing. Both entry-point scripts insert the repository root into `sys.path` to import it.

- `_Statement.text` / `.children` retain block structure; `PsiOperation` is the shared operation payload; `StepSnapshot` carries viewer state, measurement metadata, and classical bits without a NumPy dependency.
- `QScriptParser.parse` reads a script, collects registers, walks operations, and retains the tree. `_collect_registers` recursively finds literal `Register(N)` declarations; the first register is the default.
- `_gather_statements` strips `//` comments and splits on newlines, braces, and semicolons. It is not a token-aware grammar and does not join multiline calls. `_walk` recursively visits children even when a block header is unrecognized.
- `_parse_operation` dispatches logic calls, measurements, analog/align/branch headers, and pulse verbs; its context dictionary supplies inherited wire/scope information. Unknown statements return no operation without a diagnostic. `_parse_measurement` recognizes `Measure(reg[i])` and `reg.Measure()`, not `Measure(reg)`.
- `_split_call` / `_extract_args` extract call text; `_parse_key_values` uses `_split_args` to avoid splitting commas inside nested parentheses/brackets. `_parse_targets` recognizes `ALL`, lists, and scalar indices; `_parse_target_ref` resolves a register/index pair or bare name.
- `eval_angle` evaluates with `PI`, `pi`, and `tau`; `_safe_eval_angle` catches errors and returns `0.0` for pulse angles. Logic angles raise instead. `build_quantum_predicate` rewrites indexed names to bit-list access; `build_classical_predicate` resolves names from classical bits, defaulting missing names to zero.
- `parse_conjunctive_controls` extracts same-register `(index, value)` pairs for compiler controls. It accepts simple truthy bit references and conjunctions, rejects OR, and uses permissive regex matching; it is not a full predicate validator.
- **Consumers/tests:** [compiler](compiler/qasm_compiler.py), [interference viewer](viewer-references/psi_interference_viewer.py), [parser tests](tests/test_parser.py), and [pulse tests](tests/test_pulse_compiler.py). Update both parser consumers when changing the private `_parse_operation` interface.
- **Common mistakes:** treating unknown blocks as implemented control flow, rewriting all register names into one simulated bit array, assuming `!` replacement supports `!=`, or trusting eval-based expressions as sandboxed input. See known gaps before broadening syntax claims.

### [compiler/qasm_compiler.py](compiler/qasm_compiler.py)

Owns experimental gate emission, pulse scheduling, backend replay, and compiler CLI dispatch. It does not implement a full interpreter, waveform synthesis, or hardware execution.

- `PULSE_KINDS` is the scheduler's pulse registry. `PulseEvent` stores wire, start/duration, branch, guard, raw text, and waveform/frame metadata. `PulseSchedule.duration_ns` derives the last event end; `to_json` emits an array of dataclass dictionaries and `to_table` orders events for inspection.
- `PulseScheduler.build` walks `parser.statements` and sorts events. `_compile_block` manages sequential cursors and nested analog scopes; `_compile_align` computes parallel branch duration; `_lower_pulse_op` creates/filter events while retaining elapsed time. `_parse_duration` and `_split_number_unit` own permissive unit parsing. `PulseLayerCompiler` is a backwards-compatibility alias of `PulseScheduler`; preserve it unless deliberately changing compatibility.
- `PulseBackend` defines lifecycle hooks. `LoggingPulseBackend` records callbacks and returns count/duration. `PulseSimulator.run` sorts by `(start_ns, register, target or -1)` and dispatches lifecycle hooks; it does not evaluate guards or overlap physics.
- `BlochSimulatorBackend.on_start` initializes addressed vectors, `on_event` applies only `rotate` and `shiftphase`, `_rotate` implements signed X/Y/Z rotations, and `on_finish` returns coordinates by wire label. Envelopes, durations, frequency, acquisition, and logic initialization do not affect its physics.
- `QasmBuilder` owns operation lines and register declarations: `ensure_creg`, `tmp_creg`, and `ensure_qreg` allocate/reuse declarations; `render` puts the OpenQASM header/declarations before gates. Keep auxiliary declarations ahead of use.
- `OpenQasmCompiler.compile` dispatches by operation kind. `_emit_superpose` emits H; `_emit_phase` handles U1/CU1; `_emit_flip` handles X/CX/CCX, with temporary X gates around zero-valued controls. Restore those controls after the operation.
- `_emit_reflect` expands mean diffusion through `_emit_multi_control_z` / `_emit_multi_control_x`. The latter computes and uncomputes an ancilla chain for more than two controls; do not leave work qubits entangled. `_emit_measure` allocates classical destinations. The `_emit_analog`, `_emit_align`, `_emit_branch`, and pulse `_emit_*` methods emit comments only.
- `_emit_with_when` and `_lower_when_condition` own classical QASM conditions. Only simple `name == 0/1` forms are recognized; the regex is not a complete grammar. Do not extend gate emitters while leaving unsafe guard fallbacks unnoticed.
- `main` owns argparse flags, selected-register filtering, output-directory creation, schedule construction, and backend choice. `wants_pulses` omits `--simulate-bloch`, so that flag alone currently replays an empty schedule.
- **Tests:** [test_pulse_compiler.py](tests/test_pulse_compiler.py) exercises scheduling and backends; gate emitters, output validity, CLI dispatch, guard failure, ancilla restoration, and JSON compatibility lack tests.

### [viewer-references/psi_interference_viewer.py](viewer-references/psi_interference_viewer.py)

Owns the logic statevector simulator and interactive script viewer; imports shared parser records/predicates and NumPy/Matplotlib. It does not simulate analog physics.

- `QuantumSimulator.__init__` creates the all-zero basis state and seeded random generator. `run` dispatches `_apply_*` and records every step; `_record` copies amplitudes and classical data into `StepSnapshot`.
- `_apply_superpose` applies Hadamards via `_apply_single_qubit_gate` / `_hadamard`. `_apply_phase` conditionally multiplies amplitudes, `_apply_flip` swaps basis-index pairs, and `_apply_reflect` implements `2*mean - state` for mean axes.
- `_apply_measure` handles whole-register and indexed collapse; `_probabilities`, `_probability_for_bit`, and `_index_to_bits` own distribution and endian logic. `_apply_noop` and analog/pulse handlers retain timeline annotations without changing state.
- `InterferenceViewer._render_static_controls` installs the slider/buttons; `_bump` changes steps; `_reshape_state` maps amplitudes to a high/low-bit grid; `_draw_snapshot` draws probability height and phase color plus measurement/classical context. `show` enters Matplotlib display.
- `main` defines script / `--register` / `--seed`, rejects undeclared or empty selected registers, runs the simulator, and opens the viewer.
- **Tests/gaps:** no automated simulator or GUI tests. Preserve normalization, snapshot isolation, seeded sampling, and bit order when adding coverage. A guard involving the flip target can violate the pair-swap assumptions; cross-register entanglement is not represented.

### [viewer-references/wave_viewer.py](viewer-references/wave_viewer.py)

Owns standalone analytic-wave intuition; no parser/compiler callers or automated tests.

- `QuantumScene.__init__` builds the spatial grid and complex field. `add_plane_wave`, `add_gaussian_packet`, and `add_harmonic_oscillator` accumulate analytic contributions; oscillator modes use NumPy Hermite polynomials.
- `normalize` scales the discrete sum of squared magnitudes; `render_3d` renders density/phase. The main block adds two Gaussian packets and opens a plot; the alternative oscillator scene is commented out.
- Do not mistake the spatial grid for a register statevector or use this teaching model to validate gate/pulse equivalence.

### [tests/test_parser.py](tests/test_parser.py)

Standard-library `unittest` coverage for analog parsing, importing only `QScriptParser`. `_write_tmp_script` writes temporary `.psi` fixtures rather than reading algorithm examples.

- `TestAnalogParsing.test_analog_targets_propagate` checks operation order and inherited analog targets/registers.
- `test_align_and_branch_targets` checks branch labels and inherited wire indices.
- The helper uses `NamedTemporaryFile(delete=False)` without unlinking; do not assume fixture cleanup is automatic. Add logic grammar/error/measurement coverage here when changing parsing, rather than relying on these pulse-only assertions.

### [tests/test_pulse_compiler.py](tests/test_pulse_compiler.py)

Owns scheduler/backend regression tests using temporary scripts and standard-library assertions; it does not test OpenQASM gates or the GUI. `_write_tmp_script` has the same persistent-temp-file limitation as the parser test helper.

- `TestPulseCompiler.test_simple_pulse_schedule` checks sequential starts, zero-time frame change, acquisition duration, and total duration.
- `test_align_branches_share_start` checks parallel starts, labels, durations, and longest-branch schedule length.
- `test_simulator_replays_events` checks logging replay count and duration.
- `test_bloch_backend_rotates_vectors` checks Rx then frame-Z rotation, final coordinates, and unit magnitude.
- Fixtures must call `QScriptParser.parse()` before constructing `PulseScheduler`; a fresh unparsed instance has no statements to schedule.

### [qscripts/bell_pair.psi](qscripts/bell_pair.psi)

Executable single-register entanglement example: `pair` expands qubit 0, conditionally flips qubit 1, then assigns `pair.Measure()` to `output`. Consumed by the shared parser and either CLI; no dedicated algorithm test. Keep least-significant-bit ordering distinct from illustrative ket comments.

### [qscripts/ghz.psi](qscripts/ghz.psi)

Executable Greenberger–Horne–Zeilinger (GHZ) example: `ghz` superposes qubit 0 and uses it to control flips on qubits 1 and 2 before `outcome` measurement. The parser accepts it; no automated correlation test exists. Changing the controls changes the intended two-peak distribution.

### [qscripts/teleport.psi](qscripts/teleport.psi)

Compiler/viewer example for partial measurement and feed-forward: `system` maps payload/Alice/Bob to 0/1/2, records `c1`/`c2`, and applies `when: c2 == 1` X and `when: c1 == 1` phase corrections. No communication service exists; all state is local. It starts the payload at zero, so it is not a test of arbitrary-state teleportation. CLI emission is a useful smoke check, not semantic proof.

### [qscripts/ghost_filter.psi](qscripts/ghost_filter.psi)

Pulse scheduling example: `memory` has an `Align` branch containing `Analog(memory[0])`, signed-Y rotations, wait, and frame shift. It produces a 90 ns schedule in the current implementation. This is an echo description; neither backend models noise suppression. The viewer logs its pulses as no-ops. Scheduler tests use separate fixtures, not this file.

### [qscripts/odder.psi](qscripts/odder.psi)

Reversible carry/sum sketch under its existing filename: `reg` uses a two-control flip into qubit 2 and a controlled flip into qubit 1. It declares an unused fourth ancilla and does not initialize nonzero inputs or measure results. Parser/compiler accept the calls; arithmetic correctness has no test. Do not silently rename the file while changing unrelated examples.

### [qscripts/qft_3.psi](qscripts/qft_3.psi)

Quantum Fourier transform (QFT) sketch for register `q`: staged superpositions and `PI/2` / `PI/4` conditional phases followed by two endpoint flips. The shared parser accepts it. Its final pair of controlled flips is not a complete three-CNOT swap; treat bit-reversal/full-QFT claims as unverified. No focused transform test exists.

### [qscripts/bernstein_vazirani.psi](qscripts/bernstein_vazirani.psi)

Intended hidden-string recovery for `bv`, with parity oracle, repeated Hadamards, and `hidden` measurement. **Known gap:** the multiline `Phase` call raises `ValueError: substring not found` in `_split_call`; after syntax repair, its OR predicate still exceeds QASM lowering support. The guide's deterministic output claim has no automated algorithm test.

### [qscripts/grover_sat.psi](qscripts/grover_sat.psi)

Intended satisfiability (SAT) sculpting example for `logic_space`: two oracle/reflection pairs and `solution` measurement. **Known gap:** multiline `Phase` calls fail during parsing; OR/negated clauses also exceed QASM lowering. Do not use this as a passing compiler smoke test or infer success probability from its comments. No algorithm regression test exists.

### [qscripts/EXAMPLES.md](qscripts/EXAMPLES.md)

Human guide to Bell, teleportation, pulse echo, Grover, QFT, GHZ, and Bernstein–Vazirani intent, plus a primitive table. It is not an executable suite and does not cover the carry/sum filename above. Keep algorithm goals separate from the parser/compiler gaps documented here; update the guide when repairing examples or changing primitives.

### [qscript-Definition.md](qscript-Definition.md)

Primary intended v1.2 manual: Zoom layers, registers/guards, logic primitives, analog verbs, parallel flow, pulse-defined gates, timing, and visualization limits. Syntax/semantic changes belong here along with their implementation and tests. The `def pulse` / `.apply` bridge and general control-flow implications are design intent, not working parser features.

### [definitions/v1.1-upgrade.md](definitions/v1.1-upgrade.md)

Older interference-sculpting rationale: expansion, phase tagging, mean reflection, collapse, and scaling intuition. Read for why the logic vocabulary exists; the v1.2 manual owns current intended hybrid syntax. Do not restore a logic-only product scope from this older narrative.

### [definitions/v1.2-upgrade.md](definitions/v1.2-upgrade.md)

Hybrid Zoom design rationale: macro/micro views, directional rotations, parallel `Align`, frame tools, pulse gate definitions, and echo example. It overlaps the manual but is not the implementation registry. Its custom pulse application and `Measure(memory)` examples are not supported as written.

### [README.md](README.md)

Public concept-phase overview, primitive explanations, repository map, viewer commands, and experimental compiler/schedule usage. Commands are examples backed by CLI source, not packaging metadata. Its blanket “no physics yet” scheduler description omits the ideal independent Bloch backend; read the actual backend limitations before extending it.

### [AGENTS.md](AGENTS.md)

Owns the agent operational map, hybrid-model quick reference, example pointers, implementation boundaries, and planned-work snapshot. Maintain conceptual anchors and TODOs here alongside verified source/test ownership. Parser/scheduler/backend tests already exist; planned coverage work extends them rather than starting from an untested analog layer.

### [explain/interference-basics.md](explain/interference-basics.md)

Teaching narratives around phase tags, diffusion, resonance analogies, and the target-13 search example. It uses unsupported constructs such as whole-register predicates, `def pulse`, `.apply`, `repeat`, and `Measure(reg)`. Do not turn its physical metaphors, constant-time oracle claims, or probability claims into implementation guarantees.

### [explain/viewing-distribution.ipynb](explain/viewing-distribution.ipynb)

Standalone NumPy/Matplotlib notebook for a four-qubit target-13 amplitude illustration. The code cell builds uniform/tagged/reflected arrays and `plot_quantum_state` draws signed amplitudes; `plt.savefig` writes `quantum_visualization.png` relative to the execution directory. The markdown explains the landscape; no parser/pulse simulation is invoked. Generated PNG output is not tracked or specifically ignored; do not commit it accidentally. No notebook execution test exists.

### [.gitignore](.gitignore)

Owns Python build/cache/environment exclusions, notebook checkpoints, and local/editor artifacts. It is a broad Python template, not evidence that every named framework is used. Check an actual generator before expanding ignore rules; generated output outside `build/` may remain visible to Git.

### [LICENSE](LICENSE)

MIT redistribution terms. Preserve the copyright/permission notice; this file does not define language semantics, supported platforms, or release steps.

## Features and Recurring Development Pitfalls

### Logic parsing and QASM translation — Experimental/scaffold

- **Behavior/path:** `.psi` declarations and recognized calls → `QScriptParser` → selected-register operations → `OpenQasmCompiler` / `QasmBuilder`. Supports H, simple conditional phase/flip, mean diffusion, and measurement emission.
- **Constraints:** compiler controls are simple same-register conjunctions; Phase handles up to two predicate bits, Flip up to two controls, while diffusion uses an ancilla decomposition for larger registers. Unsupported cases can produce comments instead of gates. Parsing multiple registers does not imply joint-register simulation/compilation.
- **Tests/gaps:** parser tests cover analog branches only. There is no external QASM validation or equivalence test. Use [teleport.psi](qscripts/teleport.psi) for a CLI smoke check and inspect TODOs, declarations, and guards.

### Pulse timelines and independent Bloch replay — Experimental/scaffold

- **Behavior/path:** `Analog` / `Align` / `branch` → parser tree → `PulseScheduler` → `PulseSchedule` JSON/table → `PulseSimulator` and logging or Bloch backend. [ghost_filter.psi](qscripts/ghost_filter.psi) is the public working example.
- **Constraints:** explicit timeline metadata, no waveform sampling or calibrated `dt`, no entanglement/noise/readout physics, no logic-state transfer, and no guard evaluation during replay. `Acquire` is an event, not classical collapse in the pulse backend.
- **Tests/gaps:** [pulse tests](tests/test_pulse_compiler.py) cover sequential/parallel timing, replay, and rotations. Complex nesting, filtered schedules, backend reuse, invalid units, and CLI flag combinations need coverage.

### Interference playback and analytic visualization — Experimental/scaffold

- **Behavior/path:** selected-register operations → `QuantumSimulator` → snapshots → `InterferenceViewer`. Separately, `QuantumScene` and [the notebook](explain/viewing-distribution.ipynb) provide analytic illustrations.
- **Constraints:** NumPy/Matplotlib required; interactive commands need a working GUI backend. Pulses do not alter the logic statevector; storage scales exponentially in qubits and grows with snapshots.
- **Tests/gaps:** no viewer, statevector, or notebook tests. Bell/GHZ/teleport scripts parse, but algorithmic behavior is not certified by the existing suite.

### Multiline calls and apparent language support

- **Symptom/cause:** Grover and Bernstein–Vazirani examples fail with `ValueError` because `_gather_statements` emits each physical line separately and `_split_call` expects the closing parenthesis in that statement. Unknown blocks are traversed once: `repeat(3)` does not repeat, `if (c0)` does not gate children, and pulse definitions do not register callable functions.
- **Safe pattern:** use recognized single-line calls and explicit operation-level `when: name == 0/1` for the working subset. A grammar fix must preserve nested argument splitting and both tree/flat representations; add focused tests to [test_parser.py](tests/test_parser.py) and consumer coverage. Never execute function-definition children as a substitute for `.apply` semantics.
- **Status:** active known bugs/missing grammar, not supported control flow. Reproduce with `QScriptParser.parse()` on [the affected examples](qscripts/grover_sat.psi).

### TODO comments can hide incorrect circuits

- **Symptom/cause:** valid-looking QASM is incomplete or changes behavior. `_emit_with_when` falls back to unconditional gates on unsupported guards. `_emit_phase` without controls emits U1 on qubit 0 as a “global phase marker,” while the viewer does nothing without a predicate; that U1 is not a true global phase. Measurement emission does not implement a `when` guard.
- **Safe pattern:** inspect the actual emitted gates and TODO comments; constrain demonstrations to covered forms. Changes here require gate/guard/equivalence tests and synchronized docs, not only a successful CLI exit. [teleport.psi](qscripts/teleport.psi) uses the currently recognized classical equality forms.
- **Status:** active semantic gaps in [OpenQasmCompiler](compiler/qasm_compiler.py); no automated regression checks yet.

### Bloch simulation can silently replay nothing

- **Symptom/cause:** `--simulate-bloch` alone reports `{}` because compiler `main.wants_pulses` excludes that flag.
- **Safe pattern/check:** pair it with `--pulse-table`, `--pulse-json`, or `--simulate-pulses` until CLI scheduling is fixed and regression-tested. `python3 compiler/qasm_compiler.py qscripts/ghost_filter.psi --pulse-table --simulate-bloch` exercises actual events.
- **Status:** active CLI bug; the backend unit test does not cover CLI dispatch.

### Textbook intent is not an algorithm regression test

- **Symptom/cause:** guide output claims appear more complete than the scripts. [qft_3.psi](qscripts/qft_3.psi) has only two endpoint CNOTs; [teleport.psi](qscripts/teleport.psi) starts with a zero payload; [odder.psi](qscripts/odder.psi) does not prepare inputs. Teaching prose also conflates phase tagging, amplification, and collapse.
- **Safe pattern/check:** add statevector/distribution or transform equivalence tests for the exact behavior being claimed; preserve bit ordering and use seeded measurements. Existing `unittest` success does not validate these algorithms.
- **Status:** deliberate sketches with unverified claims; the QFT bit-reversal discrepancy is a known gap.

## Interface Ownership Map

| Surface | Authoritative owner and boundary |
| --- | --- |
| `.psi` registers, logic verbs, measurement, analog/branch/pulse syntax | [QScriptParser._parse_operation and _parse_measurement](psi_lang.py); intended syntax in [the manual](qscript-Definition.md). No formal grammar or separate registry. |
| Shared Python records and predicates | [PsiOperation, StepSnapshot, QScriptParser, predicate helpers](psi_lang.py). There is no packaged/versioned public Python API. |
| Compiler positional `script`; `--register`, `--out` | [compiler main argparse declarations](compiler/qasm_compiler.py); first declared register by default, QASM to stdout unless `--out`. |
| `--pulse-json`, `--pulse-table`, `--simulate-pulses`, `--simulate-bloch` | [compiler main, PulseSchedule, PulseSimulator](compiler/qasm_compiler.py); `--pulse-json -` also prints QASM unless redirected to `--out`, so stdout is not pure JSON. |
| Pulse backend hooks | [PulseBackend.on_start/on_event/on_finish](compiler/qasm_compiler.py); replay extension points, not a dynamic plugin loader or hardware adapter. |
| Viewer positional `script`; `--register`, `--seed`; step slider/buttons | [viewer main and InterferenceViewer](viewer-references/psi_interference_viewer.py). |
| Standalone analytic plot | [QuantumScene and its main block](viewer-references/wave_viewer.py); no CLI flags. |

No HTTP routes, network protocols, persistent service schemas, or deployment interfaces exist.

## Build, Run, Test, Debug, and Release

Run from the repository root. [README.md](README.md) uses `python`; the locally available interpreter is `python3`, so the equivalent verified commands below use that spelling. Parser/compiler/tests pass with Python 3.9.6 in this environment; no supported-version matrix or dependency lockfile exists. Viewer prerequisites are Python 3, NumPy, and Matplotlib per the README/imports; exact dependency versions and supported GUI platforms are **Unknown — verify before changing viewer setup**.

There is no dependency/bootstrap manifest, package build, linter, formatter, type checker, benchmark, security scan, CI workflow, or automated release/deployment command. Core commands use the standard library; do not invent an install or release procedure. Viewer execution remains unverified locally because NumPy and Matplotlib are absent.

```sh
# Full suite; -s tests is necessary for this repository layout.
python3 -m unittest discover -s tests -v

# Focused suites.
python3 -m unittest discover -s tests -p test_parser.py -v
python3 -m unittest discover -s tests -p test_pulse_compiler.py -v

# Inspect actual CLI flags; emit QASM locally.
python3 compiler/qasm_compiler.py --help
python3 compiler/qasm_compiler.py qscripts/teleport.psi --out build/teleport.qasm

# Inspect/export/replay a populated pulse schedule.
python3 compiler/qasm_compiler.py qscripts/ghost_filter.psi --pulse-table
python3 compiler/qasm_compiler.py qscripts/ghost_filter.psi --pulse-json build/ghost_filter.json --simulate-bloch
python3 compiler/qasm_compiler.py qscripts/ghost_filter.psi --simulate-pulses

# Documentation/diff hygiene.
git diff --check
git status --short
```

These are locally verified invocations of the checked-in unittest entry points and compiler flags, not package-manager scripts. Compiler output-file variants were exercised in a temporary directory; output paths above follow README usage. `--out` and `--pulse-json` create parent directories and overwrite destination files. Tests create temporary files and currently leave them behind. None of these commands requires credentials, hardware, or network access.

Interactive commands from [README.md](README.md), inspected but **not run** because optional dependencies are absent:

```sh
python3 viewer-references/wave_viewer.py
python3 viewer-references/psi_interference_viewer.py qscripts/teleport.psi --seed 1
python3 viewer-references/psi_interference_viewer.py qscripts/qft_3.psi --register q
```

For debugging, inspect `registers`, `operations`, and `parser.statements` after `parse()`; inspect `PulseSchedule.to_table()` / `.to_json()` and emitted QASM TODOs. There is no dedicated debugger wrapper. The notebook writes a PNG in its working directory; no fixture seed command or data migration exists. Release, packaging, and hardware export are **Unknown — verify before changing distribution or targeting hardware**.

## Test Ownership Map

| Contract/subsystem | Focused owner | Uncovered boundary |
| --- | --- | --- |
| Analog context inheritance | [TestAnalogParsing.test_analog_targets_propagate](tests/test_parser.py) | Invalid targets, out-of-scope pulses, analog `where` rejection. |
| Align/branch wire inheritance | [TestAnalogParsing.test_align_and_branch_targets](tests/test_parser.py) | Multiple registers, malformed branches, deep nesting. |
| Sequential pulse timing/frame duration | [TestPulseCompiler.test_simple_pulse_schedule](tests/test_pulse_compiler.py) | Unit validation, negative durations, filtered events. |
| Parallel starts/longest branch | [TestPulseCompiler.test_align_branches_share_start](tests/test_pulse_compiler.py) | Operations after alignment, nested alignment/filter timing. |
| Replay and logging | [TestPulseCompiler.test_simulator_replays_events](tests/test_pulse_compiler.py) | Hook ordering assertions, repeated-run isolation, guard handling. |
| Ideal rotations/frame shift | [TestPulseCompiler.test_bloch_backend_rotates_vectors](tests/test_pulse_compiler.py) | All signed axes, backend reuse, CLI dispatch, pulse/logic state integration. |

Both test files define their own `_write_tmp_script`; there is no shared fixture package. No tests currently own OpenQASM semantics/ancillas, expression trust, logic parsing failures, statevector measurement/normalization, example algorithms, JSON schema stability, notebook output, or interactive controls. Add coverage at the actual owner when fixing these areas. Do not hard-code suite counts in maintained documentation.

## Data, Security, Privacy, and Compatibility Boundaries

- Canonical input is tracked Python, `.psi`, and documentation/notebook source. QASM, pulse JSON, plots, caches, and state snapshots are derived. There is no database, replication, retention policy, backup/restore tool, or schema migration mechanism.
- Only run trusted local `.psi` input. `eval_angle` and predicate builders use Python `eval`/`compile`; removing builtins is not a secure sandbox. There is no hostile-input grammar validation, resource cap, register-size limit, or file-access sandbox. Do not expose parsing/simulation as an untrusted-input service without addressing these boundaries.
- Predicate rewriting discards register names in quantum expressions, so cross-register predicates cannot establish joint state ownership. CLI register selection filters operations rather than simulating an entangled multi-register system.
- Preserve the v1.1 logic vocabulary when extending v1.2 pulse syntax and preserve `PulseLayerCompiler` unless an intentional compatibility change is documented. There is no declared semantic-version/deprecation policy, formal QASM equivalence guarantee, or versioned pulse-JSON schema. Update consumers/tests/docs when changing operation/event fields.
- Generated schedules and JSON include raw source text and metadata; do not put secrets or private data in examples, outputs, or this handbook. No credentials or external-service configuration are required by existing workflows.
- File-output options overwrite their explicit destinations. Keep outputs in ignored `build/` or a temporary location. Viewer state memory is exponential and snapshots add per-step copies; teaching statements about quantum parallelism are not classical resource guarantees.

## Current Status, Known Gaps, and Roadmap Snapshot

### Shipped

Present and verified within the prototype: shared single-line parsing; analog/branch target propagation; sequential and parallel pulse scheduling; JSON/table export; backend replay and ideal independent Bloch rotations. Existing tests pass. Bell, GHZ, teleportation, carry/sum, QFT sketch, and ghost-filter scripts parse; teleport QASM emission and ghost-filter schedule/replay smoke commands work. These facts do not certify algorithm correctness or production readiness.

### Experimental/scaffold

OpenQASM lowering, Python helper APIs, the statevector viewer, analytic illustrations, pulse-envelope metadata, and simulator extension hooks remain experimental. The Bloch backend has ideal per-qubit motion but no microwave/noise/readout model; the statevector viewer ignores pulse effects. No hardware backend is implemented.

### Known Gaps

- Multiline calls break [Grover](qscripts/grover_sat.psi) and [Bernstein–Vazirani](qscripts/bernstein_vazirani.psi). Unknown statements are silently ignored; unknown block bodies run once rather than implementing `if`, loops, or pulse definitions/application.
- Unsupported `when` guards can emit unconditional QASM. Guardless Phase differs between viewer/compiler; measurement guard claims in README exceed implementation. Controls and condition regexes accept prefixes rather than fully validating expressions.
- `--simulate-bloch` alone builds no schedule. Pulse replay ignores guards; malformed/unknown durations and angles are permissive. `Play`/`Acquire` records do not inherit a target index, although they retain the register; backend reuse does not fully clear state.
- The manual's no-`where` analog boundary is not enforced. Bare `Measure(reg)`, custom `def pulse`, `.apply`, general control flow, and joint-register semantics are absent. Predicate rewriting also does not robustly support `!=` or validate register identities.
- The QFT sketch's advertised endpoint reversal is incomplete. Algorithm/distribution, QASM correctness, expression safety, and GUI coverage are absent; see the test map.
- No dependency manifest, supported-platform matrix, CI, packaging, or release workflow exists. Viewer checks were not run locally because NumPy/Matplotlib are absent.
- Public docs mix intended/implemented behavior: README understates ideal Bloch support, and teaching/upgrade documents show unsupported syntax. This handbook records the discrepancies; broad documentation/code repair is separate work.

### Planned

This section owns the current agent TODO snapshot. These items are design intent, not implemented capabilities or an ordered roadmap:

- Broaden `where:` lowering beyond simple conjunctions through `parse_conjunctive_controls` and the gate emitters in [the compiler](compiler/qasm_compiler.py).
- Extend parser/analog handling tests in [parser tests](tests/test_parser.py) and [pulse tests](tests/test_pulse_compiler.py), including the gaps in the test ownership map; introduce CI. Existing tests already cover basic analog parsing, scheduling, replay, and ideal rotations.
- Explore waveform libraries and hardware backends for pulse export. Current pulse JSON/table output and replay hooks are scaffolding; QASM carries analog sections as comments, and ideal Bloch rotations do not model microwave physics.
- Implement the custom pulse-gate bridge described in [the manual](qscript-Definition.md); `def pulse` / `.apply` dispatch is currently absent.

Do not invent priorities, dates, or feature commitments. Record newly agreed future work and research here or in an explicitly introduced authoritative roadmap, and move items to implemented status only after code and validation establish support.

## Task Start and Handoff Checklist

1. Read applicable instructions completely; inspect branch/status and preserve unrelated edits.
2. Locate the owner and focused tests above; read the relevant manual/principle and compare its claims with the code, feature path, and known pitfalls.
3. Identify the quantum/classical/pulse, register, expression-trust, timing, generated-data, and compatibility boundaries the edit touches.
4. Implement at the canonical owner; add meaningful regression coverage for changed behavior. Update file/symbol ownership, contracts, interfaces, features, gaps, and human docs in the same edit batch.
5. Run focused/full tests as appropriate; inspect actual emitted output. Verify local Markdown targets and `git diff --check`; disclose optional checks that could not run.
6. Review the complete diff before handoff/commit. Keep implemented/scaffold/planned labels accurate, remove stale guidance, and report validation and remaining gaps without claiming unsupported capability.
