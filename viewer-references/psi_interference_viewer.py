"""Circuit workbench: joint wavefunctions, entanglement, collapse and matrices.

One or more .psi circuits; ideal logic simulation with pulse annotations.
Use --save/--report --no-show for headless use. Q0 is the low register bit.
"""

import argparse
import json
import sys
import textwrap
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm
from matplotlib.colors import Normalize
from matplotlib.patches import FancyBboxPatch
from matplotlib.widgets import Button, Slider

from psi_lang import QScriptParser
from quantum_gates import GATES, gate_matrix
from quantum_simulator import (QuantumSimulator, bloch_vector, circuit_unitary,
                               pair_diagnostics, reduced_density_matrix, sample_shots)


class InterferenceViewer:
    """Linked views of a snapshot, with circuit and qubit-pair selection."""

    def __init__(self, snapshots, num_qubits, qubits=None, shots=None, title="qscript", circuits=None):
        if not snapshots: raise ValueError("Viewer requires at least an initial snapshot")
        self.circuits = circuits or [{"name": title, "snapshots": snapshots, "num_qubits": num_qubits, "shots": shots}]
        self.circuit_index, self.index, self.mode, self.matrix_part = 0, 0, "Probability", "real"
        self.snapshots, self.num_qubits, self.shots = snapshots, num_qubits, shots
        self.requested_qubits = qubits
        self.qubits = self._select_qubits(num_qubits)
        self.fig = plt.figure(figsize=(18, 11), facecolor="#f4f6fb")
        self.fig.canvas.manager.set_window_title("qscript quantum circuit workbench")
        self.fig.suptitle(title, x=0.04, y=0.985, ha="left", fontsize=19, weight="bold", color="#182b49")
        self.timeline = self.fig.add_axes([0.055, 0.82, 0.90, 0.105])
        self.ax = self.fig.add_axes([0.035, 0.47, 0.335, 0.28], projection="3d")
        self.bloch_ax = self.fig.add_axes([0.395, 0.47, 0.24, 0.28], projection="3d")
        self.measure_ax = self.fig.add_axes([0.72, 0.47, 0.24, 0.245])
        self.density_ax = self.fig.add_axes([0.055, 0.145, 0.23, 0.21])
        self.correlation_ax = self.fig.add_axes([0.375, 0.145, 0.21, 0.21])
        self.matrix_ref_ax = self.fig.add_axes([0.68, 0.15, 0.12, 0.20])
        self.matrix_actual_ax = self.fig.add_axes([0.84, 0.15, 0.12, 0.20])
        self.status = self.fig.text(0.055, 0.395, "", fontsize=9, color="#263e5f")
        self.matrix_status = self.fig.text(0.68, 0.095, "", fontsize=8, color="#263e5f")
        self.detail = self.fig.text(0.055, 0.78, "", fontsize=10, color="#263e5f")
        self.norm = Normalize(-np.pi, np.pi)
        cax = self.fig.add_axes([0.81, 0.78, 0.15, 0.007])
        self.fig.colorbar(cm.ScalarMappable(norm=self.norm, cmap="twilight"), cax=cax, orientation="horizontal",
                          ticks=[-np.pi, 0, np.pi])
        cax.tick_params(labelsize=7, pad=1)
        cax.set_title("Amplitude phase (radians)", fontsize=8)
        self._render_static_controls()
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)
        self._draw_snapshot(0)

    def _select_qubits(self, n):
        qubits = list(self.requested_qubits) if self.requested_qubits is not None else list(range(min(2, n)))
        if len(qubits) not in (1, 2) or len(set(qubits)) != len(qubits) or any(q < 0 or q >= n for q in qubits):
            raise ValueError("Select one or two distinct qubits present in every selected circuit")
        return qubits

    def _render_static_controls(self):
        self.slider = Slider(self.fig.add_axes([0.15, 0.055, 0.46, 0.025]), "Step", 0,
                             max(1, len(self.snapshots)-1), valinit=0, valstep=1, valfmt="%0.0f")
        self.slider.on_changed(lambda value: self._draw_snapshot(min(int(value), len(self.snapshots)-1)))
        # Keep references so Matplotlib retains widget callbacks.
        self.prev_button = Button(self.fig.add_axes([0.055, 0.045, 0.065, 0.04]), "Previous")
        self.next_button = Button(self.fig.add_axes([0.63, 0.045, 0.055, 0.04]), "Next")
        self.pair_button = Button(self.fig.add_axes([0.695, 0.045, 0.065, 0.04]), "Qubit pair")
        self.circuit_button = Button(self.fig.add_axes([0.77, 0.045, 0.055, 0.04]), "Circuit")
        self.mode_button = Button(self.fig.add_axes([0.835, 0.045, 0.055, 0.04]), "Wave")
        self.matrix_button = Button(self.fig.add_axes([0.9, 0.045, 0.06, 0.04]), "Re / Im")
        self.prev_button.on_clicked(lambda _: self._bump(-1))
        self.next_button.on_clicked(lambda _: self._bump(1))
        self.pair_button.on_clicked(lambda _: self._cycle_pair())
        self.circuit_button.on_clicked(lambda _: self._cycle_circuit())
        self.mode_button.on_clicked(lambda _: self._cycle_mode())
        self.matrix_button.on_clicked(lambda _: self._cycle_matrix())
        self.fig.text(0.055, 0.013, "Left / right: step    Q: pair    C: circuit    W: wave    M: matrix Re / Im    |    q0 = low register bit; pulse steps are annotations",
                      fontsize=9, color="#526782")

    def _on_key(self, event):
        actions = {"left": lambda: self._bump(-1), "right": lambda: self._bump(1),
                   "q": self._cycle_pair, "c": self._cycle_circuit, "w": self._cycle_mode, "m": self._cycle_matrix}
        if event.key in actions: actions[event.key]()

    def _bump(self, delta):
        self.slider.set_val(int(np.clip(self.index + delta, 0, len(self.snapshots)-1)))

    def _cycle_pair(self):
        pairs = list(combinations(range(self.num_qubits), 2)) or [(0,)]
        current = tuple(sorted(self.qubits))
        self.qubits = list(pairs[(pairs.index(current)+1) % len(pairs)] if current in pairs else pairs[0])
        self._draw_snapshot(self.index)

    def _cycle_mode(self):
        modes = ["Probability", "Real amplitude", "Imaginary amplitude"]
        self.mode = modes[(modes.index(self.mode)+1) % len(modes)]
        self._draw_snapshot(self.index)

    def _cycle_matrix(self):
        self.matrix_part = "imag" if self.matrix_part == "real" else "real"
        self._draw_snapshot(self.index)

    def _cycle_circuit(self):
        self.circuit_index = (self.circuit_index + 1) % len(self.circuits)
        circuit = self.circuits[self.circuit_index]
        self.snapshots, self.num_qubits, self.shots = circuit["snapshots"], circuit["num_qubits"], circuit.get("shots")
        self.qubits = self._select_qubits(self.num_qubits)
        self.fig._suptitle.set_text(circuit["name"])
        self.slider.valmax = max(1, len(self.snapshots)-1)
        self.slider.ax.set_xlim(0, self.slider.valmax)
        self.slider.set_val(min(self.index, len(self.snapshots)-1))

    def _draw_snapshot(self, idx):
        self.index = idx
        snap = self.snapshots[idx]
        self.detail.set_text(textwrap.shorten(f"{snap.label}   {snap.detail}", width=140))
        self._draw_timeline()
        self._draw_wave(snap.amplitudes)
        self._draw_bloch(snap.amplitudes)
        diagnostics = pair_diagnostics(snap.amplitudes, self.qubits, self.num_qubits)
        self._heatmap(self.density_ax, diagnostics["density"], "Reduced density matrix (phase color)", phase=True)
        self._draw_correlations(diagnostics)
        self._draw_measurement(snap)
        self._draw_matrices(snap)
        info = f"Selected {self.qubits}  |  Tr(rho²)={diagnostics['purity']:.4f}  S(rho)={diagnostics['entropy']:.4f} bits"
        if "concurrence" in diagnostics:
            info += f"  |  concurrence={diagnostics['concurrence']:.4f}  mutual information={diagnostics['mutual_information']:.4f} bits"
        self.status.set_text(info + "\nClassical: " + (str(snap.classical_bits) if snap.classical_bits else "no measured bits"))
        self.fig.canvas.draw_idle()

    def _draw_wave(self, state):
        self.ax.clear()
        probabilities = np.abs(state)**2
        selected = np.arange(len(state)) if len(state) <= 128 else np.sort(np.argsort(probabilities)[-128:])
        cols = 2 ** ((self.num_qubits + 1)//2)
        x, y = selected % cols, selected // cols
        heights = {"Probability": probabilities, "Real amplitude": state.real, "Imaginary amplitude": state.imag}[self.mode][selected]
        colors = cm.twilight(self.norm(np.angle(state[selected])))
        colors[probabilities[selected] < 1e-12] = (0.8, 0.82, 0.85, 0.25)
        self.ax.bar3d(x, y, np.minimum(0, heights), 0.65, 0.65, np.abs(heights), color=colors, shade=True)
        self.ax.set_zlim((0, 1) if self.mode == "Probability" else (-1, 1))
        self.ax.set_xlabel("Low register bits")
        self.ax.set_ylabel("High register bits")
        self.ax.set_zlabel(self.mode)
        suffix = f" (top 128 / {len(state)} states)" if len(state) > 128 else ""
        self.ax.set_title("Joint wavefunction: " + self.mode + suffix, fontsize=11)
        if len(state) <= 16:
            for xi, yi, i, z in zip(x, y, selected, heights):
                self.ax.text(xi+0.3, yi+0.3, max(0, z)+0.025, f"|{i:0{self.num_qubits}b}>", fontsize=8, ha="center")
        self.ax.view_init(elev=27, azim=-55)

    def _draw_bloch(self, state):
        ax = self.bloch_ax
        ax.clear()
        u, v = np.mgrid[0:2*np.pi:25j, 0:np.pi:13j]
        ax.plot_wireframe(np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v), color="#b9c8de", alpha=0.3, linewidth=0.5)
        for q, color in zip(self.qubits, ["#4269ca", "#d16543"]):
            vec = bloch_vector(reduced_density_matrix(state, [q], self.num_qubits))
            ax.quiver(0, 0, 0, *vec, color=color, linewidth=2.5, arrow_length_ratio=0.12)
            ax.scatter(*vec, color=color, s=45, label=f"q{q}: |r|={np.linalg.norm(vec):.3f}")
        ax.set(xlim=(-1, 1), ylim=(-1, 1), zlim=(-1, 1), xlabel="X", ylabel="Y", zlabel="Z")
        ax.set_box_aspect((1, 1, 1))
        ax.set_title("Reduced Bloch vectors (mixed states shrink)", fontsize=11)
        ax.legend(loc="lower left", fontsize=8)

    def _heatmap(self, ax, matrix, title, phase=False):
        ax.clear()
        if phase:
            colors = cm.twilight(self.norm(np.angle(matrix)))
            colors[..., :3] = 1 - np.abs(matrix)[..., None] * (1-colors[..., :3])
            ax.imshow(colors, origin="upper")
        else:
            ax.imshow(np.real(matrix), cmap="RdBu_r", vmin=-1, vmax=1, origin="upper")
        n = len(matrix)
        labels = [format(i, f"0{int(np.log2(n))}b") for i in range(n)]
        ax.set_xticks(range(n), labels, fontsize=8)
        ax.set_yticks(range(n), labels, fontsize=8)
        ax.set_title(title, fontsize=10, pad=12)
        if n <= 4:
            for i in range(n):
                for j in range(n):
                    val = matrix[i, j]
                    label = f"{val.real:.2f}" if abs(val.imag) < 1e-9 else f"{val.real:.2f}\n{val.imag:+.2f}i"
                    ax.text(j, i, label, ha="center", va="center", fontsize=8)

    def _draw_correlations(self, diagnostics):
        ax = self.correlation_ax
        ax.clear()
        if "connected" not in diagnostics:
            ax.axis("off")
            ax.text(0, 0.5, "Select two qubits to inspect\nconnected Pauli correlations.\n\nConcurrence measures pair entanglement;\nmutual information includes\nclassical correlations.", fontsize=10)
            return
        ax.set_axis_on()
        matrix = diagnostics["connected"]
        ax.imshow(matrix, cmap="RdBu_r", vmin=-1, vmax=1)
        ax.set_xticks(range(3), list("XYZ"))
        ax.set_yticks(range(3), list("XYZ"))
        ax.set_xlabel(f"q{self.qubits[1]}")
        ax.set_ylabel(f"q{self.qubits[0]}")
        ax.set_title("Connected correlations: <AB> - <A><B>", fontsize=10, pad=12)
        for i in range(3):
            for j in range(3): ax.text(j, i, f"{matrix[i,j]:+.2f}", ha="center", va="center", fontsize=10)

    def _draw_measurement(self, snap):
        ax = self.measure_ax
        ax.clear()
        measurement = snap.measurement
        if measurement:
            if measurement["type"] == "qubit":
                theory = {"0": measurement["p0"], "1": measurement["p1"]}
                outcome = str(measurement["result"])
                title = f"Measure q{measurement['qubit']}: sampled {outcome}"
            else:
                theory, outcome = measurement["distribution"], measurement["bitstring"]
                title = f"Register collapse: sampled {outcome}"
            histogram = (self.shots or {}).get("measurements", {}).get(self.index, {})
        else:
            theory = {format(i, f"0{self.num_qubits}b"): float(abs(a)**2) for i, a in enumerate(snap.amplitudes)}
            histogram = (self.shots or {}).get("final", {}) if self.index == len(self.snapshots)-1 else {}
            outcome, title = None, "Born probabilities at this step"
        labels = [key for key in theory if theory[key] > 1e-10 or histogram.get(key, 0)]
        labels = sorted(labels) if len(labels) <= 16 else sorted(labels, key=lambda k: theory[k], reverse=True)[:16]
        x = np.arange(len(labels))
        ax.bar(x-0.18, [theory[k] for k in labels], 0.34, label="Before collapse" if measurement else "Exact", color="#4269ca")
        if histogram:
            total = sum(histogram.values())
            ax.bar(x+0.18, [histogram.get(k, 0)/total for k in labels], 0.34, label=f"{total} circuit shots", color="#d16543")
        if outcome in labels:
            ax.scatter(labels.index(outcome), 1.03, marker="v", color="#233857", label="This trajectory")
        ax.set_xticks(x, labels, rotation=40 if len(labels)>6 else 0, fontsize=8)
        ax.set_ylim(0, 1.12)
        ax.set_ylabel("Probability")
        ax.set_title(title + (" (top 16)" if len(theory)>16 else ""), fontsize=11, pad=12)
        ax.legend(fontsize=8, loc="upper right")
        ax.spines[["top", "right"]].set_visible(False)

    def _draw_matrices(self, snap):
        comparison = snap.comparison or {}
        if snap.measurement:
            measurement = snap.measurement
            if measurement["type"] == "qubit":
                result, size = measurement["result"], 2
                density = reduced_density_matrix(snap.amplitudes, [measurement["qubit"]], self.num_qubits)
            else:
                result, size = int(measurement["bitstring"], 2), 2**self.num_qubits
                density = np.outer(snap.amplitudes, snap.amplitudes.conj()) if size <= 8 else None
            if density is not None:
                projector = np.zeros((size, size))
                projector[result, result] = 1
                for ax in (self.matrix_ref_ax, self.matrix_actual_ax): ax.set_axis_on()
                self._heatmap(self.matrix_ref_ax, projector, f"Projector P_{result}")
                self._heatmap(self.matrix_actual_ax, density, "Post-collapse rho")
                self.matrix_status.set_text("P_m|psi> / sqrt(p_m); p_m = <psi|P_m|psi>\nProjectors describe collapse; they are not unitary gates.")
                return
        if "reference" not in comparison:
            for ax in (self.matrix_ref_ax, self.matrix_actual_ax): ax.clear(); ax.axis("off")
            text = "Select a named gate to compare its matrix\nwith the primitive decomposition."
            if snap.measurement: text = "Measurement: P_m|psi> / sqrt(p_m)\np_m = <psi|P_m|psi>; no unitary matrix."
            elif snap.operation and snap.operation.kind in {"rotate", "wait", "analog", "shiftphase", "setfreq", "play", "acquire", "align", "branch"}:
                text = "Pulse annotation: no statevector evolution."
            if "state_error" in comparison: text += f"\nTheory state error = {comparison['state_error']:.2e}"
            self.matrix_status.set_text(text)
            return
        part = "Re" if self.matrix_part == "real" else "Im"
        for ax, key, title in [(self.matrix_ref_ax, "reference", f"Theory {part}(U)"), (self.matrix_actual_ax, "actual", f"Primitives {part}(U)")]:
            ax.set_axis_on()
            self._heatmap(ax, getattr(comparison[key], self.matrix_part), title)
        self.matrix_status.set_text(f"{comparison['basis']} ({comparison['primitive_count']} primitives)\n"
                                  f"max |U_theory - U_primitive| = {comparison['operator_error']:.2e}\n"
                                  f"max |psi_theory - psi_sim| = {comparison['state_error']:.2e}"
                                  + (" (guard skipped)" if not comparison["applied"] else ""))

    def _draw_timeline(self):
        import re
        ax = self.timeline
        ax.clear()
        start, stop = max(0, self.index-7), min(len(self.snapshots), max(16, self.index+9))
        for q in range(self.num_qubits): ax.plot([start-0.5, stop-0.5], [q, q], color="#afbdd1", linewidth=1)
        for i in range(start, stop):
            op = self.snapshots[i].operation
            if op is None: continue
            targets = list(range(self.num_qubits)) if op.measure_all or op.targets == ["ALL"] or not op.targets else op.targets
            if op.predicate: targets = sorted(set(targets) | {int(q) for q in re.findall(r"\[(\d+)\]", op.predicate)})
            ax.plot([i, i], [min(targets), max(targets)], color="#4269ca", linewidth=1.5)
            for q in targets:
                ax.add_patch(FancyBboxPatch((i-0.36, q-0.23), 0.72, 0.46, boxstyle="round,pad=0.03", linewidth=1,
                             facecolor="#4269ca" if i == self.index else "#e8edf6", edgecolor="#4269ca"))
                label = op.gate or {"superpose": "H", "phase": "P", "flip": "X", "measure": "M", "reflect": "D"}.get(op.kind, "pulse")
                ax.text(i, q, label, ha="center", va="center", fontsize=7, color="white" if i == self.index else "#263e5f")
        ax.set(xlim=(start-0.7, stop-0.3), ylim=(self.num_qubits-0.5, -0.5))
        ax.set_yticks(range(self.num_qubits), [f"q{q}" for q in range(self.num_qubits)], fontsize=8)
        ax.set_xticks(range(start, stop), range(start, stop), fontsize=8)
        ax.set_title("Circuit timeline: multiwire boxes share one operation; source detail gives predicates and guards", fontsize=10, loc="left")
        for spine in ax.spines.values(): spine.set_visible(False)

    def show(self):
        plt.show()


def _complex_json(matrix):
    return {"real": np.real(matrix).tolist(), "imag": np.imag(matrix).tolist()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", nargs="*", help="One or more .psi circuits")
    parser.add_argument("--register", help="Register to track (first declaration by default)")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--view", choices=["waves", "workbench"], default="waves", help="Continuous wave lens (default) or diagnostic workbench")
    parser.add_argument("--wave-mode", choices=["density", "real", "imaginary"], default="density")
    parser.add_argument("--qubits", nargs="+", type=int, help="One or two qubits for reduced-state inspection")
    parser.add_argument("--initial", help="Initial basis bitstring, high bit first")
    parser.add_argument("--shots", type=int, default=0, help="Independent full-circuit repetitions")
    parser.add_argument("--step", type=int, default=-1, help="Initially selected step; -1 selects the final step")
    parser.add_argument("--save", type=Path, help="Save the selected view as PNG/PDF/SVG")
    parser.add_argument("--report", type=Path, help="Write probabilities, shots, measurements and matrix diagnostics as JSON")
    parser.add_argument("--unitary", action="store_true", help="Include a circuit reference in the report (at most 8 qubits, unitary operations only)")
    parser.add_argument("--no-show", action="store_true", help="Run without opening a GUI")
    parser.add_argument("--list-gates", action="store_true")
    parser.add_argument("--matrix", help="Print the analytic local matrix for a gate")
    parser.add_argument("--params", nargs="*", default=[], help="Matrix parameters, e.g. PI/2")
    args = parser.parse_args()
    if args.no_show:
        plt.switch_backend("Agg")
    if args.shots < 0: parser.error("--shots must be nonnegative")
    if args.list_gates:
        for name, spec in GATES.items(): print(f"{name:14} {spec.qubits} qubits  {', '.join(spec.parameters)}")
    if args.matrix:
        from psi_lang import eval_angle
        print(np.asarray(gate_matrix(args.matrix, *[eval_angle(v) for v in args.params])))
    if not args.script:
        if args.list_gates or args.matrix: return
        parser.error("Provide a circuit, --list-gates, or --matrix")
    circuits, reports, reference_circuits = [], [], []
    for path in args.script:
        registers, operations = QScriptParser(path).parse()
        reg = args.register or next(iter(registers))
        if reg not in registers: parser.error(f"Register {reg} not declared in {path}")
        ops = [op for op in operations if op.register == reg]
        simulator = QuantumSimulator(registers[reg], ops, args.seed, args.initial)
        snapshots = simulator.run()
        histogram = sample_shots(registers[reg], ops, args.shots, args.seed, args.initial) if args.shots else None
        name = f"{Path(path).name} / {reg} / {registers[reg]} qubits"
        circuits.append({"name": name, "snapshots": snapshots, "num_qubits": registers[reg], "shots": histogram})
        measurements = [{"step": i, **s.measurement} for i, s in enumerate(snapshots) if s.measurement]
        gates = [{"step": i, "name": s.operation.gate, **{k: (_complex_json(v) if k in {"reference", "actual"} else v) for k, v in s.comparison.items()}}
                 for i, s in enumerate(snapshots) if s.operation and s.operation.kind == "gate"]
        report = {"script": str(path), "register": reg, "qubits": registers[reg], "basis_order": "q[n-1] ... q[0]",
                  "final_state": _complex_json(simulator.state), "probabilities": simulator._probabilities(),
                  "classical_bits": simulator.classical_bits, "measurements": measurements, "gates": gates, "shots": histogram}
        selected = args.qubits if args.qubits is not None else list(range(min(2, registers[reg])))
        report["selected_qubits"] = selected
        report["reductions"] = [{"step": i, **{k: (_complex_json(v) if isinstance(v, np.ndarray) else v)
                                    for k, v in pair_diagnostics(s.amplitudes, selected, registers[reg]).items()}}
                                for i, s in enumerate(snapshots)]
        if args.unitary:
            reference = circuit_unitary(registers[reg], ops)
            actual = circuit_unitary(registers[reg], ops, primitives=True)
            report["circuit_unitary"] = _complex_json(reference)
            report["primitive_unitary"] = _complex_json(actual)
            report["circuit_operator_error"] = float(np.max(abs(reference-actual)))
            report["comparisons"] = []
            for other_path, other in reference_circuits:
                if other.shape != reference.shape: continue
                overlap = np.vdot(other, reference)
                phase = overlap / abs(overlap) if abs(overlap) > 1e-12 else 1
                report["comparisons"].append({"script": other_path,
                    "max_error": float(np.max(abs(reference-other))),
                    "max_error_up_to_global_phase": float(np.max(abs(reference-phase*other)))})
            reference_circuits.append((str(path), reference))
        reports.append(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    first = circuits[0]
    viewer_class = InterferenceViewer
    if args.view == "waves":
        from wave_interaction_viewer import WaveInteractionViewer
        viewer_class = WaveInteractionViewer
    viewer = viewer_class(first["snapshots"], first["num_qubits"], args.qubits, first["shots"], first["name"], circuits)
    if args.view == "waves":
        viewer.mode = args.wave_mode.title()
    for circuit in circuits: viewer._select_qubits(circuit["num_qubits"])
    step = len(viewer.snapshots)-1 if args.step == -1 else args.step
    if not 0 <= step < len(viewer.snapshots): parser.error("--step is outside the circuit")
    viewer.slider.set_val(step)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        viewer.fig.savefig(args.save, dpi=150, facecolor=viewer.fig.get_facecolor())
    if not args.no_show: viewer.show()
    else: plt.close(viewer.fig)


if __name__ == "__main__":
    main()
