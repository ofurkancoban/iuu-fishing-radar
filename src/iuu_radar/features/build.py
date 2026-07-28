"""Build per-vessel and per-H3-cell feature matrices from staged/marted events."""

from __future__ import annotations

import pandas as pd


def build_vessel_features(events_with_zone: pd.DataFrame) -> pd.DataFrame:
    """Build the per-vessel feature matrix: effort by zone, gap events, encounters, etc.

    Expected output columns include (not exhaustive): vessel_id, effort_hours_inside,
    effort_hours_edge, effort_hours_outside, gap_event_count, gap_hours_near_mpa,
    dark_then_reappear_count, encounter_count_inside, loitering_count_inside.
    """
    raise NotImplementedError("Implement in Phase 3")


def build_cell_features(events_with_h3: pd.DataFrame) -> pd.DataFrame:
    """Build the per-H3-cell feature matrix used for hotspot intensity."""
    raise NotImplementedError("Implement in Phase 3")
