"""Unit tests for anomaly scoring, verifying a synthetic suspicious vessel ranks high."""

from __future__ import annotations

import pandas as pd

from iuu_radar.models.anomaly import fit_score, merge_scores
from iuu_radar.models.rules import apply_rules


def _vessel_features() -> pd.DataFrame:
    normal = [
        {
            "vessel_id": f"v{i}",
            "total_fishing_hours": 2.0,
            "events_inside": 0,
            "events_edge": 0,
            "events_outside": 1,
            "gap_event_count": 0,
            "encounter_count_inside": 0,
            "loitering_count_inside": 0,
            "dark_then_reappear_count": 0,
        }
        for i in range(10)
    ]
    suspicious = {
        "vessel_id": "suspicious",
        "total_fishing_hours": 50.0,
        "events_inside": 20,
        "events_edge": 5,
        "events_outside": 0,
        "gap_event_count": 8,
        "encounter_count_inside": 3,
        "loitering_count_inside": 2,
        "dark_then_reappear_count": 4,
    }
    return pd.DataFrame([*normal, suspicious])


def test_suspicious_vessel_ranks_highest():
    features = _vessel_features()
    scores = fit_score(features)
    with_rules = apply_rules(features)
    final = merge_scores(scores, with_rules)

    top_vessel = features.loc[final.idxmax(), "vessel_id"]
    assert top_vessel == "suspicious"
    assert final.max() <= 100.0


def test_fit_score_handles_single_vessel():
    features = _vessel_features().iloc[:1]
    scores = fit_score(features)
    assert (scores == 0.0).all()
