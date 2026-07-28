-- Clean and rename raw WDPA/WD-OECM polygons: keep only the identity, name, and
-- geometry needed downstream. The current combined WDPA/WD-OECM bulk export keys
-- each site by SITE_ID (formerly WDPAID in older single-source WDPA exports).

select
    region,
    cast("SITE_ID" as varchar) as mpa_id,
    "NAME" as mpa_name,
    "IUCN_CAT" as iucn_category,
    geom
from {{ source('raw', 'raw_mpas') }}
where "SITE_ID" is not null
