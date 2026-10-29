"""Continuous configuration-space wave lens for exact qubit states.

The orthonormal oscillator modes encode |0>, |1>; they are a chosen coordinate
representation, not the position of a hardware qubit or a microwave field.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import Normalize
from matplotlib.widgets import Button, Slider
from quantum_gates import gate_matrix
from quantum_simulator import apply_matrix, circuit_unitary, pair_diagnostics, reduced_density_matrix
from psi_lang import build_classical_predicate


def wave_field(state, qubits, num_qubits, coordinates):
    """Return an exact mode expansion (pure) or diagonal density kernel (mixed)."""
    x, y = np.meshgrid(coordinates, coordinates)
    g = lambda z: np.pi**(-0.25) * np.exp(-z*z/2)
    modes = np.array([g(x)*g(y), g(x)*np.sqrt(2)*y*g(y),
                      np.sqrt(2)*x*g(x)*g(y), 2*x*y*g(x)*g(y)])
    rho = reduced_density_matrix(state, qubits, num_qubits)
    if len(qubits) == 1:
        # A vacuum spectator supplies the second display coordinate.
        rho = np.kron(rho, np.diag([1, 0]))
    density = np.einsum('iyx,ij,jyx->yx', modes, rho, modes.conj()).real.clip(0)
    pure = np.isclose(np.trace(rho @ rho).real, 1, rtol=0, atol=1e-9)
    wave = None
    if pure:
        axes = [num_qubits-1-q for q in qubits]
        axes += [a for a in range(num_qubits) if a not in axes]
        columns = np.asarray(state).reshape((2,)*num_qubits).transpose(axes).reshape(2**len(qubits),-1)
        coefficients = columns[:, np.argmax(np.linalg.norm(columns,axis=0))].copy()
        coefficients /= np.linalg.norm(coefficients)
        if len(qubits) == 1:
            coefficients = np.kron(coefficients, [1,0])
        wave = np.einsum('i,iyx->yx', coefficients, modes)
    return x, y, wave, density


def gate_state(before, after, op, num_qubits, fraction, classical):
    """Principal-eigenphase unitary path; measurement jumps only at its endpoint."""
    if fraction <= 0 or op is None:
        return before.copy()
    if fraction >= 1:
        return after.copy()
    if op.when and not build_classical_predicate(op.when)(classical):
        return before.copy()
    if op.kind == 'gate':
        matrix = np.asarray(gate_matrix(op.gate, *op.parameters, inverse=op.inverse))
        targets = op.targets
    elif op.kind in {'superpose', 'phase', 'flip', 'reflect'} and num_qubits <= 8:
        from dataclasses import replace
        matrix = circuit_unitary(num_qubits, [replace(op, when=None)])
        targets = list(reversed(range(num_qubits)))
    else:
        return before.copy()
    values, vectors = np.linalg.eig(matrix)
    partial = (vectors * np.exp(1j*fraction*np.angle(values))) @ np.linalg.inv(vectors)
    return apply_matrix(before, partial, targets, num_qubits)


class WaveInteractionViewer:
    """Before / during / after surfaces with gate scrubbing and animation."""
    def __init__(self, snapshots, num_qubits, qubits=None, shots=None, title='qscript', circuits=None):
        self.circuits = circuits or [dict(name=title, snapshots=snapshots, num_qubits=num_qubits)]
        self.snapshots, self.num_qubits = snapshots, num_qubits
        self.requested_qubits = qubits
        self.qubits = self._select_qubits(num_qubits)
        self.index, self.circuit_index, self.mode = 0, 0, 'Density'
        self.coordinates = np.linspace(-3.8, 3.8, 85)
        self.fig = plt.figure(figsize=(17, 9), facecolor='#0c1525')
        self.fig.suptitle(title, x=.045, y=.965, ha='left', color='white', fontsize=20, weight='bold')
        self.subtitle = self.fig.text(.045, .885, '', color='#c4d4ee', fontsize=11)
        self.axes = [self.fig.add_axes([.02+i*.325, .30, .31, .53], projection='3d', facecolor='#0c1525') for i in range(3)]
        self.metrics = self.fig.text(.045, .245, '', color='#b8cdea', fontsize=12)
        self.fig.text(.045, .19, 'Wave encoding: |0> = Gaussian; |1> = signed two-lobe mode.  Joint wave = sum of basis-mode products.', color='#b8cdea', fontsize=10)
        self.fig.text(.045, .16, 'Coordinates describe the selected qubits together; correlated ridges and phase cancellation reveal their joint state.', color='#b8cdea', fontsize=10)
        self.fig.text(.045, .025, 'Educational configuration-space representation; not hardware position or microwave physics.  Gate path is mathematical, not calibrated time.', color='#9aaeca', fontsize=9)
        self.slider = Slider(self.fig.add_axes([.13,.105,.38,.025]), 'Circuit step', 0, max(1,len(snapshots)-1), valstep=1, valinit=0)
        self.progress = Slider(self.fig.add_axes([.64,.105,.29,.025]), 'Gate fraction', 0, 1, valinit=.5)
        for control in (self.slider, self.progress):
            control.label.set_color('#b8cdea')
            control.valtext.set_color('#b8cdea')
        self.slider.on_changed(lambda v: self._draw_snapshot(min(int(v), len(self.snapshots)-1)))
        self.progress.on_changed(lambda v: self._draw_snapshot(self.index))
        self.buttons = []
        actions = [('Previous', lambda: self.slider.set_val(max(0,self.index-1))),
                   ('Next', lambda: self.slider.set_val(min(len(self.snapshots)-1,self.index+1))),
                   ('Play / pause', self._play), ('Density / Re / Im', self._mode), ('Circuit', self._circuit)]
        for i,(label,action) in enumerate(actions):
            button = Button(self.fig.add_axes([.13+i*.168,.055,.155,.032]), label)
            button.on_clicked(lambda event, fn=action: fn())
            self.buttons.append(button)
        self.timer = self.fig.canvas.new_timer(interval=80)
        self.timer.add_callback(self._tick)
        self.playing = False
        self.fig.canvas.mpl_connect('close_event', lambda event: self.timer.stop())
        cax = self.fig.add_axes([.72,.905,.22,.008])
        self.fig.colorbar(cm.ScalarMappable(norm=Normalize(-np.pi,np.pi), cmap='hsv'), cax=cax, orientation='horizontal', ticks=[-np.pi,0,np.pi])
        cax.tick_params(colors='white', labelsize=8)
        cax.set_title('Complex amplitude phase (pure states)', color='white', fontsize=9)
        self._draw_snapshot(0)

    def _select_qubits(self, n):
        qs = list(self.requested_qubits) if self.requested_qubits is not None else list(range(min(2,n)))
        if not qs or len(qs)>2 or len(set(qs))!=len(qs) or any(q<0 or q>=n for q in qs):
            raise ValueError('Wave lens needs one or two distinct valid selected qubits')
        return qs

    def _mode(self):
        modes = ['Density','Real','Imaginary']
        self.mode = modes[(modes.index(self.mode)+1)%3]
        self._draw_snapshot(self.index)

    def _play(self):
        self.playing = not self.playing
        if self.playing:
            if self.progress.val >= 1: self.progress.set_val(0)
            self.timer.start()
        else: self.timer.stop()

    def _tick(self):
        if self.progress.val >= 1:
            self.playing = False
            self.timer.stop()
        else: self.progress.set_val(min(1,self.progress.val+.04))

    def _circuit(self):
        self.circuit_index = (self.circuit_index+1)%len(self.circuits)
        circuit = self.circuits[self.circuit_index]
        self.snapshots, self.num_qubits = circuit['snapshots'], circuit['num_qubits']
        self.qubits = self._select_qubits(self.num_qubits)
        self.fig._suptitle.set_text(circuit['name'])
        self.slider.valmax = max(1,len(self.snapshots)-1)
        self.slider.ax.set_xlim(0,self.slider.valmax)
        self.slider.set_val(min(self.index,len(self.snapshots)-1))

    def _draw_snapshot(self, index):
        self.index = index
        snap = self.snapshots[index]
        previous = self.snapshots[max(0,index-1)]
        during = gate_state(previous.amplitudes, snap.amplitudes, snap.operation, self.num_qubits, self.progress.val, previous.classical_bits)
        states = [previous.amplitudes, during, snap.amplitudes]
        fields = [wave_field(s,self.qubits,self.num_qubits,self.coordinates) for s in states]
        bound = max(float(np.max(f[3] if self.mode=='Density' or f[2] is None else np.abs(f[2]))) for f in fields)*1.08
        for ax, field, label in zip(self.axes, fields, ['Before gate',f'During gate: {self.progress.val:.0%}','After gate']):
            ax.clear()
            x,y,wave,density = field
            z = density if self.mode=='Density' or wave is None else (wave.real if self.mode=='Real' else wave.imag)
            colors = cm.hsv((np.angle(wave)+np.pi)/(2*np.pi)) if wave is not None else cm.viridis(density/max(density.max(),1e-12))
            ax.plot_surface(x,y,z, facecolors=colors, rstride=1,cstride=1, linewidth=0, antialiased=True, shade=True)
            ax.contour(x,y,z, zdir='z', offset=0 if self.mode=='Density' else -bound, levels=9, colors='#809cc6', alpha=.35, linewidths=.6)
            ax.set_zlim((0,bound) if self.mode=='Density' or wave is None else (-bound,bound))
            ax.set_xlabel(f'q{self.qubits[0]} mode coordinate',color='#b8cdea',labelpad=8)
            ax.set_ylabel(f'q{self.qubits[1]} mode coordinate' if len(self.qubits)==2 else 'Vacuum spectator',color='#b8cdea',labelpad=8)
            ax.set_zlabel('Joint density' if wave is None or self.mode=='Density' else self.mode+' amplitude',color='#b8cdea')
            ax.set_title(label+(' / mixed-state density' if wave is None else ''),color='white',fontsize=13,pad=12)
            ax.tick_params(colors='#9aaeca',labelsize=7)
            for axis in [ax.xaxis,ax.yaxis,ax.zaxis]:
                axis.set_pane_color((.055,.095,.16,1))
                axis._axinfo['grid']['color'] = (.3,.4,.55,.2)
            ax.view_init(32,-52)
        kind = snap.operation.kind if snap.operation else 'init'
        path = 'Measurement jumps at 100%; no interpolated collapse.' if kind=='measure' else 'Principal-eigenphase unitary path; endpoints are circuit states.'
        if kind in {'analog','rotate','wait','shiftphase','setfreq','play','acquire','align','branch'}:
            path = 'Pulse annotation; no logical state evolution.'
        self.subtitle.set_text(f'{snap.label}   {snap.detail[:110]}\n{path}')
        diagnostics = [pair_diagnostics(s,self.qubits,self.num_qubits) for s in states]
        self.metrics.set_text('     |     '.join(f'{label}: concurrence {d["concurrence"]:.3f}' if 'concurrence' in d else f'{label}: purity {d["purity"]:.3f}' for label,d in zip(['Before','During','After'],diagnostics)))
        self.fig.canvas.draw_idle()

    def show(self):
        plt.show()
