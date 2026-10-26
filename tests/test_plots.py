from collections import deque
from types import SimpleNamespace
import pytest
from nitrosense.widgets import HistoryPlot, DiagnosticPlot


def test_history_plot_fixed_duration():
    plot = HistoryPlot()
    assert plot.samples.maxlen >= 360
    for t in range(60):
        plot.samples.append((50 + t, 55 + t, 100.0 + t * 0.5))
    assert len(plot.samples) == 60


def test_diagnostic_plot_duration_stability():
    history = deque(maxlen=1600)
    plot = DiagnosticPlot(history, mode="temperature")
    plot.seconds = 30

    for i in range(80):
        ts = 100.0 + i * 0.5
        history.append((ts, SimpleNamespace(cpu_temp=50, gpu_temp=60,
                                           cpu_critical=100, gpu_critical=90)))

    assert plot.seconds == 30
    assert plot.history is history
