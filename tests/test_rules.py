"""Unit tests for rule-based flags, using a small synthetic vessel feature matrix."""

from __future__ import annotations

import pandas as pd

from iuu_radar.models.rules import apply_rules


def _vessel_features() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "vessel_id": "v1",
                "total_fishing_hours": 5.0,
                "events_inside": 1,
                "events_edge": 0,
                "events_outside": 0,
                "gap_event_count": 1,
                "encounter_count_inside": 0,
                "loitering_count_inside": 0,
                "dark_then_reappear_count": 1,
            },
            {
                "vessel_id": "v2",
                "total_fishing_hours": 1.0,
                "events_inside": 0,
                "events_edge": 0,
                "events_outside": 1,
                "gap_event_count": 0,
                "encounter_count_inside": 0,
                "loitering_count_inside": 0,
                "dark_then_reappear_count": 0,
            },
        ]
    )


def test_flag_dark_then_reappear():
    result = apply_rules(_vessel_features())
    v1 = result[result["vessel_id"] == "v1"].iloc[0]
    v2 = result[result["vessel_id"] == "v2"].iloc[0]

    assert "dark_then_reappear" in v1["flags"]
    assert "effort_inside_mpa" in v1["flags"]
    assert "gap_near_mpa" in v1["flags"]
    assert len(v1["reasons"]) == len(v1["flags"])
    assert v2["flags"] == []
    assert v2["reasons"] == []
