from __future__ import annotations

import pandas as pd
import pytest

from bpic17_analyzer.event_log import normalize_event_log


@pytest.fixture

def sample_log() -> pd.DataFrame:
    """Synthetic event log covering all important assignment edge cases."""
    rows = [
        # C1: accepted; cancellation followed later by accepted; three complete
        # fraud assessments (two by Alice, one by Bob).
        ("C1", "O_Submitted", "2026-01-01T08:00:00Z", "complete", "Clerk"),
        ("C1", "O_Cancelled", "2026-01-01T09:00:00Z", "complete", "Clerk"),
        ("C1", "O_Review", "2026-01-01T09:30:00Z", "complete", "Clerk"),
        ("C1", "W_Assess Potential Fraud", "2026-01-01T12:00:00Z", "start", "Alice"),
        ("C1", "O_Accepted", "2026-01-01T10:00:00Z", "complete", "Manager"),
        ("C1", "W_Assess Potential Fraud", "2026-01-01T13:00:00Z", "complete", "Alice"),
        ("C1", "W_Assess Potential Fraud", "2026-01-01T14:00:00Z", "complete", "Alice"),
        ("C1", "W_Assess Potential Fraud", "2026-01-01T15:00:00Z", "complete", "Bob"),
        # C2: refused and accepted (overlap is permitted), ends with cancelled;
        # two fraud completes but performed by different resources.
        ("C2", "O_Refused", "2026-01-02T08:00:00Z", "complete", "Manager"),
        ("C2", "W_Assess Potential Fraud", "2026-01-02T09:00:00Z", "complete", "Alice"),
        ("C2", "W_Assess Potential Fraud", "2026-01-02T10:00:00Z", "complete", "Bob"),
        ("C2", "O_Accepted", "2026-01-02T11:00:00Z", "complete", "Manager"),
        ("C2", "O_Cancelled", "2026-01-02T12:00:00Z", "complete", "Manager"),
        # C3: accepted and refused, but only one fraud complete. One-day cycle.
        ("C3", "O_Accepted", "2026-01-03T08:00:00Z", "complete", "Manager"),
        ("C3", "O_Refused", "2026-01-04T08:00:00Z", "complete", "Manager"),
        ("C3", "W_Assess Potential Fraud", "2026-01-03T09:00:00Z", "complete", "Alice"),
        # C4: cancellation is followed by another activity, so it is not 11.7E;
        # no later accepted event, so it is not 11.22.
        ("C4", "O_Cancelled", "2026-01-05T08:00:00Z", "complete", "Manager"),
        ("C4", "O_Review", "2026-01-05T09:00:00Z", "complete", "Manager"),
    ]
    # Deliberately shuffle rows to confirm the normalizer sorts by timestamp,
    # retaining source order as a stable tie-breaker.
    data = pd.DataFrame(rows, columns=[
        "case:concept:name", "concept:name", "time:timestamp",
        "lifecycle:transition", "org:resource",
    ])
    order = [7, 4, 1, 0, 3, 2, 6, 5, 12, 10, 8, 11, 9, 15, 13, 14, 17, 16]
    return normalize_event_log(data.iloc[order].reset_index(drop=True))
