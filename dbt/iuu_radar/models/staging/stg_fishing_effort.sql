-- Clean and type raw 4Wings fishing effort rows, one row per vessel per report bucket.

select
    region,
    "vessel_id" as vessel_id,
    cast("hours" as double) as fishing_hours
from {{ source('raw', 'raw_fishing_effort') }}
where vessel_id is not null
