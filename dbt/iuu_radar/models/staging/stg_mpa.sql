-- Clean and rename raw WDPA polygons: keep only the identity, name, and geometry
-- needed downstream. Raw WDPA attribute columns vary by source export, so this
-- model is deliberately narrow.

select
    region,
    cast("WDPAID" as varchar) as mpa_id,
    "NAME" as mpa_name,
    "IUCN_CAT" as iucn_category,
    geom
from {{ source('raw', 'raw_mpas') }}
where "WDPAID" is not null
