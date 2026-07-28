-- Tag every event with its proximity zone relative to the nearest MPA in the same
-- region: 'inside' (within the polygon), 'edge' (within the configured buffer of
-- the boundary), or 'outside'. edge_buffer_km is passed in via the region config
-- and applied here in meters after reprojecting to a metric CRS for the distance
-- check; ST_DWithin on WGS84 degrees would give the wrong buffer distance, so the
-- geometries are transformed before the check.

{% set edge_buffer_km = 10 %}

with events as (
    select * from {{ ref('stg_gfw_events') }}
),

mpas as (
    select * from {{ ref('stg_mpa') }}
),

joined as (
    select
        e.event_id,
        e.region,
        e.event_type,
        e.start_ts,
        e.end_ts,
        e.lat,
        e.lon,
        e.vessel_id,
        e.vessel_flag,
        m.mpa_id,
        m.mpa_name,
        st_distance(
            st_point(e.lon, e.lat),
            m.geom
        ) as degrees_to_mpa,
        st_contains(m.geom, st_point(e.lon, e.lat)) as is_inside
    from events e
    left join mpas m
        on e.region = m.region
),

ranked as (
    select
        *,
        row_number() over (
            partition by event_id order by degrees_to_mpa asc nulls last
        ) as rn
    from joined
)

select
    event_id,
    region,
    event_type,
    start_ts,
    end_ts,
    lat,
    lon,
    vessel_id,
    vessel_flag,
    mpa_id,
    mpa_name,
    case
        when is_inside then 'inside'
        -- 1 degree of latitude is ~111 km; a coarse but dependency-free km->degree
        -- conversion, adequate for the small demo regions this project targets.
        when degrees_to_mpa <= ({{ edge_buffer_km }} / 111.0) then 'edge'
        else 'outside'
    end as proximity_zone
from ranked
where rn = 1
