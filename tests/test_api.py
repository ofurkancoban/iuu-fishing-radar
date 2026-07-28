"""API endpoint tests using a temp DuckDB file and the real app. No network access.

Includes tests that out-of-range inputs (bbox, limit, offset, region) are
rejected with a 4xx.
"""

from __future__ import annotations

import json

import duckdb
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "test.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    conn.execute(
        "CREATE TABLE result_mpa_scores AS SELECT * FROM (VALUES "
        "('1', 'default', 80.0)) AS t(mpa_id, region, score)"
    )
    conn.execute(
        "CREATE TABLE result_vessels AS SELECT * FROM (VALUES "
        "('v1', 'default', 90.0, ?, ?, '2024-01-01')) "
        "AS t(vessel_id, region, score, flags, reasons, last_seen)",
        [json.dumps(["gap_near_mpa"]), json.dumps(["1 gap event near MPA."])],
    )
    conn.execute(
        "CREATE TABLE result_hotspots AS SELECT * FROM (VALUES "
        "('862830827ffffff', 'default', 5)) AS t(h3_cell, region, intensity)"
    )
    conn.execute(
        "CREATE TABLE result_anomalies AS SELECT * FROM (VALUES "
        "(1, 'default', 'v1', -90.5, -0.5, TIMESTAMP '2024-01-05', ?)) "
        "AS t(id, region, vessel_id, lon, lat, ts, reasons)",
        [json.dumps(["gap near mpa"])],
    )
    conn.close()

    import iuu_radar.api.deps as deps

    monkeypatch.setattr(deps, "DUCKDB_PATH", duckdb_path)

    from iuu_radar.api.main import app

    return TestClient(app)


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_mpas(client):
    response = client.get("/api/mpas", params={"region": "default"})
    assert response.status_code == 200
    body = response.json()
    assert body[0]["mpa_id"] == "1"
    assert body[0]["rank"] == 1


def test_get_mpa_not_found(client):
    response = client.get("/api/mpas/does-not-exist")
    assert response.status_code == 404


def test_list_vessels(client):
    response = client.get("/api/vessels", params={"region": "default"})
    assert response.status_code == 200
    body = response.json()
    assert body[0]["vessel_id"] == "v1"
    assert body[0]["flags"] == ["gap_near_mpa"]


def test_list_hotspots(client):
    response = client.get("/api/hotspots", params={"region": "default"})
    assert response.status_code == 200
    assert response.json()[0]["h3_cell"] == "862830827ffffff"


def test_latest_anomalies(client):
    response = client.get("/api/anomalies/latest", params={"region": "default"})
    assert response.status_code == 200
    assert response.json()[0]["vessel_id"] == "v1"


def test_vessels_rejects_out_of_range_limit(client):
    response = client.get("/api/vessels", params={"region": "default", "limit": 9999})
    assert response.status_code == 422


def test_vessels_rejects_negative_offset(client):
    response = client.get("/api/vessels", params={"region": "default", "offset": -1})
    assert response.status_code == 422


def test_rejects_unknown_region(client):
    response = client.get("/api/vessels", params={"region": "not-a-real-region"})
    assert response.status_code == 422


def test_hotspots_rejects_invalid_bbox(client):
    response = client.get(
        "/api/hotspots", params={"region": "default", "bbox": "not,a,valid,bbox"}
    )
    assert response.status_code == 422


def test_hotspots_rejects_oversized_bbox(client):
    response = client.get(
        "/api/hotspots", params={"region": "default", "bbox": "-180,-90,180,90"}
    )
    assert response.status_code == 422
