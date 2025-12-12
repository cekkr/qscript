# AI References — PsiScript v1.2

Quick anchors to the v1.2 **Hybrid (Logic ↔ Pulse)** model so follow-up prompts do not need to re-derive the mental model.

- **Core sources:** `PsiScript-Definition.md` (v1.2 hybrid manual), `definitions/v1.2-upgrade.md` (Zoom philosophy), `psiscripts/` (logic + analog examples), `viewer-references/` (interference visuals), `compiler/qasm_compiler.py` + `psi_lang.py` (parsing/lowering stubs).
- **Mental model:** Start at the logic layer to sculpt the $2^N$ space (`Superpose` → `Phase` → `Reflect` → `Flip`). When you need hardware detail, drop into `Analog { ... }` to specify **geometric pulse trajectories** with durations and waveforms. `where:` is quantum-time tagging; `when:` is classical-time gating; `Analog` suspends `where` and switches to explicit time.
- **Primitive cheat sheet (logic):**  
  - `Superpose(targets)` → expansion via Hadamards.  
  - `Phase(angle, where)` → chisel/logic tag; `PI` = delete tag, fractions = frequency tagging.  
  - `Reflect(axis: MEAN)` → interference trigger to carve away tagged regions.  
  - `Flip(target, where|when)` → pivot/route; entangling when guarded by `where`, classical when guarded by `when`.
- **Primitive cheat sheet (pulse):**  
  - `Analog(target)` → enter pulse-time for that wire.  
  - `Rotate(axis, angle, duration, shape?)`, `Wait(duration)`, `ShiftPhase(angle)`, `SetFreq(hz)` → geometric moves + frame tracking.  
  - `Play(waveform, channel)`, `Acquire(duration, kernel)` → raw emit/readout.  
  - `Align { branch ... }` → parallel branches that end together.
- **Example pointers:**  
  - Logic sculpting: `psiscripts/grover_sat.psi` (tag → reflect → repeat), `psiscripts/qft_3.psi` (frequency etches), `psiscripts/teleport.psi` (classical `when:` guards).  
  - Pulse flow: `psiscripts/ghost_filter.psi` (echo-style analog block inside an Align).  
  - Frequency tagging: `psiscripts/bernstein_vazirani.psi`; GHZ/Bell for entanglement scaffolding.
- **Python helpers:**  
  - Viewer: `viewer-references/psi_interference_viewer.py` visualizes logic-layer interference; pulse ops are recorded as timeline notes (no microwave simulation).  
  - Wave intuition: `viewer-references/wave_viewer.py` sketches interference patterns for teaching.  
  - Parser/lowering: `psi_lang.py` understands `Analog/Rotate/Align/...`; `compiler/qasm_compiler.py` emits QASM for logic ops and comments for pulse ops.
- **Known gaps / TODOs:**  
  - Pulse-level physics is not simulated; use `compiler/qasm_compiler.py --pulse-*` to get a timestamped schedule and replay it through the simulator abstraction while QASM still carries comments for analog sections.  
  - `where` lowering still limited to simple conjunctions (extend `parse_conjunctive_controls`).  
  - Add tests around the new parser branches/analog handling once CI exists; consider waveform libraries or hardware back-ends for pulse export.
