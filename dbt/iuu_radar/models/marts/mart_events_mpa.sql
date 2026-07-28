-- Tag every event with its proximity zone relative to the nearest MPA in the same
-- region: 'inside' (within the polygon), 'edge' (within the configured buffer of
-- the boundary), or 'outside'.
--
-- Joins against int_mpa_buffered (mpa geometry pre-buffered by the edge distance,
-- indexed with an R-tree) using ST_Intersects, not a plain cross join: DuckDB can
-- use the index to probe only the handful of MPAs near each event instead of
-- comparing every event against every MPA on earth. That distinction is what
-- keeps this join tractable once the region count (and therefore the worldwide
-- MPA count in scope) grows beyond a handful of small demo bboxes.

with events as (
    select *, st_point(lon, lat) as geom from {{ ref('stg_gfw_events') }}
),

mpas as (
    select * from {{ ref('int_mpa_buffered') }}
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
        st_contains(m.geom, e.geom) as is_inside
    from events e
    join mpas m
        on e.region = m.region
        and st_intersects(m.geom_buffered, e.geom)
),

ranked as (
    select
        *,
        row_number() over (
            partition by event_id order by is_inside desc
        ) as rn
    from joined
),

matched as (
    select
        event_id, region, event_type, start_ts, end_ts, lat, lon, vessel_id, vessel_flag,
        mpa_id, mpa_name,
        case when is_inside then 'inside' else 'edge' end as proximity_zone
    from ranked
    where rn = 1
),

unmatched as (
    -- Events with no MPA within the buffer distance anywhere in their region.
    select
        e.event_id, e.region, e.event_type, e.start_ts, e.end_ts, e.lat, e.lon,
        e.vessel_id, e.vessel_flag,
        cast(null as varchar) as mpa_id,
        cast(null as varchar) as mpa_name,
        'outside' as proximity_zone
    from events e
    left join matched mt on e.event_id = mt.event_id
    where mt.event_id is null
)

select * from matched
union all
select * from unmatched
