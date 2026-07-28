-- Clean and type raw GFW events (fishing, encounter, loitering, port_visit, gap)
-- into one typed row per event, ready for the spatial join against MPAs.

select
    id as event_id,
    region,
    event_type,
    "type" as gfw_type,
    cast("start" as timestamp) as start_ts,
    cast("end" as timestamp) as end_ts,
    cast(position.lat as double) as lat,
    cast(position.lon as double) as lon,
    vessel.id as vessel_id,
    vessel.name as vessel_name,
    vessel.flag as vessel_flag,
    vessel.type as vessel_type
from {{ source('raw', 'raw_events') }}
where id is not null
