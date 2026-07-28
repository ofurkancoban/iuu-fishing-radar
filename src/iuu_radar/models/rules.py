"""Deterministic, explainable red-flag rules with human-readable reason strings.

Each rule is a named boolean function so the UI can show WHY a vessel was flagged.
Output feeds into the final risk score alongside the unsupervised anomaly score.
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
    """Flag vessels with apparent fishing effort inside a no-take MPA."""
    raise NotImplementedError("Implement in Phase 4")


def flag_gap_near_mpa_boundary(vessel_row: pd.Series, boundary_km: float = 5.0) -> Flag | None:
    """Flag vessels whose AIS gap (disabling) event begins within boundary_km of an MPA."""
    raise NotImplementedError("Implement in Phase 4")


def flag_dark_then_reappear(vessel_row: pd.Series) -> Flag | None:
    """Flag vessels that go dark near an MPA and reappear near the same MPA."""
    raise NotImplementedError("Implement in Phase 4")


def apply_rules(vessel_features: pd.DataFrame) -> pd.DataFrame:
    """Run all rules over the vessel feature matrix, adding flags and reasons columns."""
    raise NotImplementedError("Implement in Phase 4")
