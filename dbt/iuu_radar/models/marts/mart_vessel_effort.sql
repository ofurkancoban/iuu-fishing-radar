-- Base per-vessel aggregation: fishing effort hours and event counts split by
-- proximity zone. This is the table features/build.py extends into the full
-- feature matrix (gap events, encounters, identity anomalies, etc.) in Phase 3.
--
-- mart_events_mpa is populated by Python (spatial/events_mpa_join.py) in
-- bounded batches before this model runs, not by a dbt SQL model, so it is
-- referenced here as a plain table rather than through dbt's ref macro.

with effort as (
    select
        region,
        vessel_id,
        sum(fishing_hours) as total_fishing_hours
    from {{ ref('stg_fishing_effort') }}
    group by 1, 2
),

events_by_zone as (
    select
        region,
        vessel_id,
        proximity_zone,
        event_type,
        count(*) as event_count
    from mart_events_mpa
    where vessel_id is not null
    group by 1, 2, 3, 4
),

zone_pivot as (
    select
        region,
        vessel_id,
        sum(case when proximity_zone = 'inside' then event_count else 0 end) as events_inside,
        sum(case when proximity_zone = 'edge' then event_count else 0 end) as events_edge,
        sum(case when proximity_zone = 'outside' then event_count else 0 end) as events_outside,
        sum(case when event_type = 'gap' then event_count else 0 end) as gap_event_count,
        sum(
            case when event_type = 'encounter' and proximity_zone = 'inside'
            then event_count else 0 end
        ) as encounter_count_inside,
        sum(
            case when event_type = 'loitering' and proximity_zone = 'inside'
            then event_count else 0 end
        ) as loitering_count_inside
    from events_by_zone
    group by 1, 2
)

select
    coalesce(e.region, z.region) as region,
    coalesce(e.vessel_id, z.vessel_id) as vessel_id,
    coalesce(e.total_fishing_hours, 0) as total_fishing_hours,
    coalesce(z.events_inside, 0) as events_inside,
    coalesce(z.events_edge, 0) as events_edge,
    coalesce(z.events_outside, 0) as events_outside,
    coalesce(z.gap_event_count, 0) as gap_event_count,
    coalesce(z.encounter_count_inside, 0) as encounter_count_inside,
    coalesce(z.loitering_count_inside, 0) as loitering_count_inside
from effort e
full outer join zone_pivot z
    on e.region = z.region and e.vessel_id = z.vessel_id
