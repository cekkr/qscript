"""
PsiScript interference viewer (v1.1 sculpting lens).

This script loads a `.psi` program, simulates its quantum operations,
and renders a 3D surface where height = probability density and color = phase.
Use the slider or buttons to step through the script and see how phase tags,
reflections, and measurements reshape the state vector.

Run locally (Python 3, numpy, matplotlib):
    python viewer-references/psi_interference_viewer.py psiscripts/teleport.psi --seed 1

Limitations: geared toward the PsiScript samples in this repo (single register,
Superpose/Phase/Flip/Reflect/Measure). Classical guards (`when:`) are applied
after sampling measurement outcomes.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm
from matplotlib.colors import Normalize
from matplotlib.widgets import Button, Slider

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from psi_lang import (
    PsiOperation,
    PsiScriptParser,
    StepSnapshot,
    build_classical_predicate,
    build_quantum_predicate,
)


class QuantumSimulator:
    """Minimal statevector simulator to track interference step by step."""

    def __init__(self, num_qubits: int, operations: List[PsiOperation], seed: Optional[int] = None):
        self.num_qubits = num_qubits
        self.operations = operations
        self.state = np.zeros(2**num_qubits, dtype=np.complex128)
        self.state[0] = 1.0
        self.classical_bits: Dict[str, int] = {}
        self.snapshots: List[StepSnapshot] = []
        self.rng = np.random.default_rng(seed)

    def run(self) -> List[StepSnapshot]:
        self._record("Init", "All amplitude in |0...0>.")
        for idx, op in enumerate(self.operations, start=1):
            measurement = getattr(self, f"_apply_{op.kind}")(op)
            self._record(
                f"{idx}. {op.kind}",
                op.raw or op.kind,
                measurement=measurement,
            )
        return self.snapshots

    def _record(self, label: str, detail: str, measurement: Optional[Dict[str, object]] = None):
        self.snapshots.append(
            StepSnapshot(
                label=label,
                detail=detail,
                amplitudes=self.state.copy(),
                measurement=measurement,
                classical_bits=dict(self.classical_bits),
            )
        )

    def _apply_superpose(self, op: PsiOperation):
        targets = range(self.num_qubits) if op.targets == ["ALL"] else op.targets
        for q in targets:
            self.state = self._apply_single_qubit_gate(self.state, q, self._hadamard())

    def _apply_phase(self, op: PsiOperation):
        predicate = build_quantum_predicate(op.predicate) if op.predicate else None
        when_fn = build_classical_predicate(op.when) if op.when else None
        if when_fn and not when_fn(self.classical_bits):
            return
        if not predicate:
            return
        for idx in range(len(self.state)):
            bits = self._index_to_bits(idx)
            if predicate(bits):
                self.state[idx] *= np.exp(1j * op.angle)

    def _apply_flip(self, op: PsiOperation):
        predicate = build_quantum_predicate(op.predicate) if op.predicate else None
        when_fn = build_classical_predicate(op.when) if op.when else None
        if when_fn and not when_fn(self.classical_bits):
            return
        target = op.targets[0]
        for idx in range(len(self.state)):
            bits = self._index_to_bits(idx)
            if predicate is None or predicate(bits):
                flipped_idx = idx ^ (1 << target)
                if flipped_idx > idx:
                    a, b = self.state[idx], self.state[flipped_idx]
                    self.state[idx], self.state[flipped_idx] = b, a

    def _apply_reflect(self, op: PsiOperation):
        if op.axis and "MEAN" in op.axis.upper():
            avg = np.mean(self.state)
            self.state = 2 * avg - self.state

    def _apply_measure(self, op: PsiOperation):
        if op.measure_all:
            distribution = self._probabilities()
            outcomes = list(distribution.keys())
            probs = np.array(list(distribution.values()))
            bitstring = self.rng.choice(outcomes, p=probs)
            collapsed_idx = int(bitstring, 2)
            collapsed_state = np.zeros_like(self.state)
            collapsed_state[collapsed_idx] = 1.0
            self.state = collapsed_state
            if op.classical_target:
                self.classical_bits[op.classical_target] = int(bitstring, 2)
            return {
                "type": "register",
                "bitstring": bitstring,
                "distribution": distribution,
            }

        target = op.targets[0]
        p0 = self._probability_for_bit(target, 0)
        result = int(self.rng.random() >= p0)
        for idx in range(len(self.state)):
            bit = (idx >> target) & 1
            if bit != result:
                self.state[idx] = 0
        prob_result = p0 if result == 0 else 1 - p0
        if prob_result > 0:
            self.state /= math.sqrt(prob_result)
        if op.classical_target:
            self.classical_bits[op.classical_target] = result
        return {"type": "qubit", "qubit": target, "result": result, "p0": p0, "p1": 1 - p0}

    # --- helpers ---

    def _probabilities(self) -> Dict[str, float]:
        probs = np.abs(self.state) ** 2
        distribution = {}
        for idx, p in enumerate(probs):
            if p > 1e-12:
                bitstring = format(idx, f"0{self.num_qubits}b")
                distribution[bitstring] = float(p)
        return distribution

    def _probability_for_bit(self, qubit: int, value: int) -> float:
        mask = 1 << qubit
        probs = np.abs(self.state) ** 2
        indices = np.arange(len(probs))
        selector = (indices & mask) == (value << qubit)
        return float(np.sum(probs[selector]))

    def _index_to_bits(self, idx: int) -> List[int]:
        return [(idx >> q) & 1 for q in range(self.num_qubits)]

    def _apply_single_qubit_gate(self, state: np.ndarray, qubit: int, gate: np.ndarray) -> np.ndarray:
        size = len(state)
        new_state = np.zeros_like(state)
        stride = 1 << qubit
        for idx in range(size):
            if (idx & stride) == 0:
                partner = idx | stride
                a0, a1 = state[idx], state[partner]
                new_state[idx] = gate[0, 0] * a0 + gate[0, 1] * a1
                new_state[partner] = gate[1, 0] * a0 + gate[1, 1] * a1
        return new_state

    def _hadamard(self) -> np.ndarray:
        return np.array([[1, 1], [1, -1]], dtype=np.complex128) / math.sqrt(2)


class InterferenceViewer:
    """Interactive matplotlib surface showing probability and phase per step."""

    def __init__(self, snapshots: List[StepSnapshot], num_qubits: int):
        self.snapshots = snapshots
        self.num_qubits = num_qubits
        self.row_bits = max(1, num_qubits // 2)
        self.col_bits = num_qubits - self.row_bits
        self.fig = plt.figure(figsize=(12, 8))
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.norm = Normalize(vmin=-np.pi, vmax=np.pi)
        self.colorbar = None
        self.slider = None
        self._render_static_controls()
        self._draw_snapshot(0)

    def _render_static_controls(self):
        plt.subplots_adjust(bottom=0.18)
        ax_slider = plt.axes([0.15, 0.05, 0.7, 0.03])
        self.slider = Slider(
            ax=ax_slider,
            label="Step",
            valmin=0,
            valmax=len(self.snapshots) - 1,
            valinit=0,
            valfmt="%0.0f",
            valstep=1,
        )
        self.slider.on_changed(lambda val: self._draw_snapshot(int(val)))

        ax_prev = plt.axes([0.02, 0.05, 0.08, 0.04])
        ax_next = plt.axes([0.9, 0.05, 0.08, 0.04])
        Button(ax_prev, "< Prev").on_clicked(lambda _: self._bump(-1))
        Button(ax_next, "Next >").on_clicked(lambda _: self._bump(1))

    def _bump(self, delta: int):
        current = int(self.slider.val)
        next_val = np.clip(current + delta, 0, len(self.snapshots) - 1)
        self.slider.set_val(next_val)

    def _draw_snapshot(self, idx: int):
        snap = self.snapshots[idx]
        self.ax.clear()
        prob_grid, phase_grid, X, Y = self._reshape_state(snap.amplitudes)
        colors = cm.hsv(self.norm(phase_grid))
        self.ax.plot_surface(X, Y, prob_grid, facecolors=colors, rstride=1, cstride=1, linewidth=0.2, antialiased=True)
        self.ax.set_xlabel("Low bits")
        self.ax.set_ylabel("High bits")
        self.ax.set_zlabel("|psi|^2")
        title = f"{snap.label} – {snap.detail}"
        if snap.measurement:
            title += f" | Measured: {snap.measurement}"
        elif snap.classical_bits:
            title += f" | Classical: {snap.classical_bits}"
        self.ax.set_title(title, fontsize=11)

        if not self.colorbar:
            mappable = cm.ScalarMappable(cmap=cm.hsv, norm=self.norm)
            mappable.set_array([])
            self.colorbar = self.fig.colorbar(mappable, ax=self.ax, shrink=0.5, aspect=15, pad=0.08)
            self.colorbar.set_label("Phase", rotation=270, labelpad=14)

        self.fig.canvas.draw_idle()

    def _reshape_state(self, amplitudes: np.ndarray):
        rows = 2 ** self.row_bits
        cols = 2 ** self.col_bits
        prob_grid = np.zeros((rows, cols))
        phase_grid = np.zeros((rows, cols))
        for idx, amp in enumerate(amplitudes):
            row = idx >> self.col_bits
            col = idx & ((1 << self.col_bits) - 1)
            prob_grid[row, col] = np.abs(amp) ** 2
            phase_grid[row, col] = np.angle(amp)
        X, Y = np.meshgrid(np.arange(cols), np.arange(rows))
        return prob_grid, phase_grid, X, Y

    def show(self):
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Visualize interference from a PsiScript program as a 3D surface."
    )
    parser.add_argument("script", help="Path to a .psi file (e.g., psiscripts/teleport.psi)")
    parser.add_argument(
        "--register",
        help="Register name to track (defaults to the first declared register).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for measurement sampling to make the walkthrough repeatable.",
    )
    args = parser.parse_args()

    ps_parser = PsiScriptParser(args.script)
    registers, operations = ps_parser.parse()

    target_register = args.register or next(iter(registers.keys()))
    if target_register not in registers:
        raise SystemExit(f"Register '{target_register}' not declared in script.")

    filtered_ops = [op for op in operations if op.register == target_register]
    if not filtered_ops:
        raise SystemExit(f"No operations found for register '{target_register}'.")

    simulator = QuantumSimulator(registers[target_register], filtered_ops, seed=args.seed)
    snapshots = simulator.run()
    viewer = InterferenceViewer(snapshots, simulator.num_qubits)
    viewer.show()


if __name__ == "__main__":
    main()
