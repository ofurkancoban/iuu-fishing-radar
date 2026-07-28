-- Precompute each MPA's buffered geometry once (rather than per event) and index
-- it with an R-tree so mart_events_mpa's spatial join can use an index probe per
-- event instead of a full cross join against every MPA on earth. This is what
-- makes the join feasible at global scale (tens of thousands of MPAs worldwide).

{{
  config(
    materialized='table',
    post_hook="CREATE INDEX IF NOT EXISTS idx_mpa_buffered_geom ON {{ this }} USING RTREE (geom_buffered)"
  )
}}

{% set edge_buffer_km = 10 %}

select
    mpa_id,
    region,
    mpa_name,
    geom,
    -- 1 degree of latitude is ~111 km; a coarse but dependency-free km->degree
    -- conversion, adequate for the small demo regions this project targets.
    st_buffer(geom, {{ edge_buffer_km }} / 111.0) as geom_buffered
from {{ ref('stg_mpa') }}
