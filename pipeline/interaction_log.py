"""Metrics of each conversation turn, for Grafana and the health view.

Decision A8 / F1 (14.11.2026): conversation text is never stored. Only
timings, trigger type and error codes are written, into metrics.db (separate
from the senior's data, see metrics.py).
"""

from metrics import log_interaction  # noqa: F401  (kept as the public entry point)
