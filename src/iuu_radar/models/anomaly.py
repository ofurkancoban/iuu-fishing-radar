"""Unsupervised anomaly scoring over the per-vessel feature matrix (PyOD / scikit-learn)."""

from __future__ import annotations

import pandas as pd


def fit_score(vessel_features: pd.DataFrame) -> pd.Series:
    """Fit an Isolation Forest (optionally ensembled with ECOD/LOF) and return a 0-100 score.

    No reliable ground-truth labels exist, hence unsupervised. Score is normalized
    per region so scores are comparable across MPAs within a run.
    """
    raise NotImplementedError("Implement in Phase 4")


def merge_scores(anomaly_score: pd.Series, rule_flags: pd.DataFrame) -> pd.Series:
    """Combine the normalized anomaly score with rule-based flags into the final risk score."""
    raise NotImplementedError("Implement in Phase 4")
