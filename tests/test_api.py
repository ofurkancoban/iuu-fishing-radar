"""API endpoint tests using an in-memory DuckDB and a fake event bus (Phase 6).

Must not require network access. Includes tests that out-of-range inputs
(bbox, limit, offset, region) are rejected with a 4xx.
"""

import pytest


@pytest.mark.skip(reason="Implement alongside iuu_radar.api in Phase 6")
def test_health_ok():
    pass


@pytest.mark.skip(reason="Implement alongside iuu_radar.api in Phase 6")
def test_vessels_rejects_out_of_range_limit():
    pass
