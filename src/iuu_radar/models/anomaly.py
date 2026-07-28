"""Unsupervised anomaly scoring over the per-vessel feature matrix (PyOD Isolation Forest).

No reliable ground-truth label set exists for IUU fishing, hence unsupervised.
The raw decision score is normalized to 0-100 per region so scores are
comparable across vessels within a single pipeline run.
"""

from __future__ import annotations

import pandas as pd
from pyod.models.iforest import IForest

FEATURE_COLUMNS = [
    "total_fishing_hours",
    "events_inside",
    "events_edge",
    "events_outside",
    "gap_event_count",
    "encounter_count_inside",
    "loitering_count_inside",
    "dark_then_reappear_count",
]

RULE_HIT_BONUS = 10.0


def fit_score(vessel_features: pd.DataFrame, random_state: int = 42) -> pd.Series:
    """Fit an Isolation Forest on the vessel feature matrix and return a 0-100 score.

    Returns an all-zero score for fewer than 2 vessels, since a meaningful
    anomaly comparison needs at least a small population to contrast against.
    """
    if len(vessel_features) < 2:
        return pd.Series([0.0] * len(vessel_features), index=vessel_features.index)

    x = vessel_features[FEATURE_COLUMNS].fillna(0)
    model = IForest(random_state=random_state)
    model.fit(x)
    raw_scores = model.decision_scores_

    min_score, max_score = raw_scores.min(), raw_scores.max()
    if max_score == min_score:
        normalized = [0.0] * len(raw_scores)
    else:
        normalized = [
            100.0 * (s - min_score) / (max_score - min_score) for s in raw_scores
        ]
    return pd.Series(normalized, index=vessel_features.index)


def merge_scores(anomaly_score: pd.Series, rule_flags: pd.DataFrame) -> pd.Series:
    """Combine the normalized anomaly score with rule-based flags into the final risk score.

    Each rule hit adds a fixed bonus so a vessel with clear, explainable red
    flags outranks a vessel that is merely statistically unusual, then the
    result is clipped back to 0-100 so it stays interpretable.
    """
    bonus = rule_flags["flags"].apply(len) * RULE_HIT_BONUS
    combined = anomaly_score + bonus
    return combined.clip(upper=100.0)
