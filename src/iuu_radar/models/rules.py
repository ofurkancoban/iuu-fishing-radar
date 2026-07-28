"""Deterministic, explainable red-flag rules with human-readable reason strings.

Each rule inspects one row of the per-vessel feature matrix produced by
features/build.py and returns a Flag or None. Rule hits feed into the final
risk score alongside the unsupervised anomaly score (models/anomaly.py).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Flag:
    """A single rule hit: a machine-readable name and a human-readable reason."""

    name: str
    reason: str


def flag_effort_inside_notake_mpa(vessel_row: pd.Series) -> Flag | None:
    """Flag vessels with apparent fishing activity inside an MPA."""
    if vessel_row.get("events_inside", 0) > 0:
        return Flag(
            name="effort_inside_mpa",
            reason=(
                f"{int(vessel_row['events_inside'])} event(s) recorded inside a "
                "Marine Protected Area."
            ),
        )
    return None


def flag_gap_near_mpa_boundary(vessel_row: pd.Series) -> Flag | None:
    """Flag vessels with an AIS gap (disabling) event near an MPA."""
    if vessel_row.get("gap_event_count", 0) > 0:
        return Flag(
            name="gap_near_mpa",
            reason=(
                f"{int(vessel_row['gap_event_count'])} AIS disabling (gap) event(s) "
                "recorded near a Marine Protected Area."
            ),
        )
    return None


def flag_dark_then_reappear(vessel_row: pd.Series) -> Flag | None:
    """Flag vessels that go dark near an MPA and reappear near the same MPA."""
    if vessel_row.get("dark_then_reappear_count", 0) > 0:
        return Flag(
            name="dark_then_reappear",
            reason=(
                f"Went dark near a Marine Protected Area and reappeared nearby "
                f"{int(vessel_row['dark_then_reappear_count'])} time(s)."
            ),
        )
    return None


def flag_encounter_inside_mpa(vessel_row: pd.Series) -> Flag | None:
    """Flag vessels with an encounter (potential transshipment) inside an MPA."""
    if vessel_row.get("encounter_count_inside", 0) > 0:
        return Flag(
            name="encounter_inside_mpa",
            reason=(
                f"{int(vessel_row['encounter_count_inside'])} encounter event(s) "
                "(potential transshipment) recorded inside a Marine Protected Area."
            ),
        )
    return None


def flag_loitering_inside_mpa(vessel_row: pd.Series) -> Flag | None:
    """Flag vessels loitering inside an MPA."""
    if vessel_row.get("loitering_count_inside", 0) > 0:
        return Flag(
            name="loitering_inside_mpa",
            reason=(
                f"{int(vessel_row['loitering_count_inside'])} loitering event(s) "
                "recorded inside a Marine Protected Area."
            ),
        )
    return None


ALL_RULES = (
    flag_effort_inside_notake_mpa,
    flag_gap_near_mpa_boundary,
    flag_dark_then_reappear,
    flag_encounter_inside_mpa,
    flag_loitering_inside_mpa,
)


def apply_rules(vessel_features: pd.DataFrame) -> pd.DataFrame:
    """Run all rules over the vessel feature matrix, adding flags and reasons columns.

    Adds two columns: 'flags' (list of rule names hit) and 'reasons' (list of
    human-readable reason strings, one per hit), so the UI can explain WHY a
    vessel was flagged.
    """
    flags_col: list[list[str]] = []
    reasons_col: list[list[str]] = []

    for _, row in vessel_features.iterrows():
        hits = [rule(row) for rule in ALL_RULES]
        hits = [h for h in hits if h is not None]
        flags_col.append([h.name for h in hits])
        reasons_col.append([h.reason for h in hits])

    out = vessel_features.copy()
    out["flags"] = flags_col
    out["reasons"] = reasons_col
    return out
