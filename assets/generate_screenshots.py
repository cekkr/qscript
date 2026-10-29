"""Regenerate README screenshots with the actual viewer (requires viewer deps)."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
env = dict(os.environ, MPLBACKEND='Agg')
for filename, script, step, view, mode in [
    ('waves-xx.png', 'interactions.psi', 1, 'waves', 'density'),
    ('waves-exchange.png', 'exchange.psi', 2, 'waves', 'real'),
    ('waves-phase.png', 'wave_interference.psi', 2, 'waves', 'real'),
    ('measurement-workbench.png', 'interactions.psi', 5, 'workbench', 'density'),
]:
    subprocess.run([sys.executable, str(ROOT/'viewer-references/psi_interference_viewer.py'),
                    str(ROOT/'qscripts'/script), '--view', view, '--step', str(step),
                    '--wave-mode', mode, '--seed', '1', '--shots', '200', '--save', str(ROOT/'assets'/filename), '--no-show'],
                   env=env, check=True)
