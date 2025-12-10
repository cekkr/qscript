# AI References — PsiScript v1.1

Quick anchors to the v1.1 “Interference Sculpting” model so follow-up prompts do not need to re-derive the mental model.

- **Core sources:** `PsiScript-Definition.md` (v1.1 semantics), `definitions/v1.1-upgrade.md` (narrative framing), `psiscripts/` (examples), `viewer-references/` (simulation/visual aids), `compiler/qasm_compiler.py` (lowering sketch).
- **Mental model:** Expand the $2^N$ space (`Superpose`), tag regions with phase in the imaginary plane (`Phase`), convert tags into probability shifts (`Reflect`), and pivot indices or apply classical corrections (`Flip`). `where:` is quantum-time tagging; `when:` is classical-time gating.
- **Primitive cheat sheet:**  
  - `Superpose(targets)` → expansion via Hadamards.  
  - `Phase(angle, where)` → chisel/logic tag; `PI` = delete tag, fractions = frequency tagging.  
  - `Reflect(axis: MEAN)` → interference trigger to carve away tagged regions.  
  - `Flip(target, where|when)` → pivot/route; entangling when guarded by `where`, classical when guarded by `when`.
- **Example pointers:**  
  - Grover sculpting loop: `psiscripts/grover_sat.psi` (tag → reflect → repeat).  
  - Frequency tagging: `psiscripts/qft_3.psi` (coarse/fine phase etches, then pivot order).  
  - Teleportation corrections: `psiscripts/teleport.psi` (classical `when:` guards).  
  - Phase oracle decoding: `psiscripts/bernstein_vazirani.psi`.
- **Python helpers:**  
  - Viewer: `viewer-references/psi_interference_viewer.py` simulates steps and visualizes phase/amplitude; `--register` and `--seed` options help with demos.  
  - Wave intuition: `viewer-references/wave_viewer.py` sketches interference patterns for teaching.  
  - Parsing utilities: `psi_lang.py` defines `PsiScriptParser`, predicate helpers, and angle eval.
- **Known gaps / TODOs:**  
  - `compiler/qasm_compiler.py`: `Reflect` is still a comment placeholder; extend emitter for diffusion or provide library macro.  
  - Phase/flip lowering only supports simple conjunctive predicates (see `parse_conjunctive_controls`); extend for broader `where` expressions.  
  - Add automated checks/examples to guard v1.1 semantics (unit tests for parser + viewer?) once CI strategy exists.  
  - Consider adding v1.1-focused walkthroughs (interference sculpting diagrams) under `viewer-references/` or README visuals.

