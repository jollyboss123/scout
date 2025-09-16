-- Uses dynamic macros: gaz.id_expr(), gaz.name_local(), gaz.name_en(), gaz.geom_expr()
DROP TABLE IF EXISTS gaz.pois;

CREATE TABLE gaz.pois AS
WITH src AS (
    SELECT
    {ID_EXPR}               AS osm_id,
    gaz.name_local({NAME_ARG}, tags) AS name_local,
    gaz.name_en(tags)       AS name_en,
    tags                    AS tags,
    {GEOM_EXPR}             AS geom
    FROM {RAW_TABLE}
    WHERE gaz.name_local({NAME_ARG}, tags) IS NOT NULL
    OR gaz.name_en(tags) IS NOT NULL
)
SELECT
    osm_id,
    name_local,
    name_en,
    gaz.canon(name_local) AS name_local_norm,
    gaz.canon(name_en)    AS name_en_norm,
    COALESCE(tags['amenity'], '')   AS amenity,
    COALESCE(tags['shop'], '')      AS shop,
    COALESCE(tags['tourism'], '')   AS tourism,
    COALESCE(tags['leisure'], '')   AS leisure,
    COALESCE(tags['office'], '')    AS office,
    NULLIF(tags['addr:city'], '')    AS city,
    NULLIF(tags['addr:state'], '')   AS state,
    NULLIF(tags['addr:country'], '') AS country,
    CASE WHEN ST_GeometryType(geom) = 'POINT' THEN ST_Y(geom) ELSE ST_Y(ST_Centroid(geom)) END AS lat,
    CASE WHEN ST_GeometryType(geom) = 'POINT' THEN ST_X(geom) ELSE ST_X(ST_Centroid(geom)) END AS lon,
    CASE
        WHEN COALESCE(tags['amenity'],'') <> '' THEN 'amenity:' || tags['amenity']
        WHEN COALESCE(tags['shop'],'')    <> '' THEN 'shop:'    || tags['shop']
        WHEN COALESCE(tags['tourism'],'') <> '' THEN 'tourism:' || tags['tourism']
        WHEN COALESCE(tags['leisure'],'') <> '' THEN 'leisure:' || tags['leisure']
        WHEN COALESCE(tags['office'],'')  <> '' THEN 'office:'  || tags['office']
        ELSE 'unknown'
        END AS kind,
    LEAST(1.0,
          (CASE WHEN tags['wikidata'] IS NOT NULL THEN 0.40 ELSE 0 END) +
          (CASE WHEN COALESCE(tags['tourism'],'') <> '' THEN 0.25 ELSE 0 END) +
          (CASE WHEN COALESCE(tags['amenity'],'') <> '' THEN 0.20 ELSE 0 END) +
          (CASE WHEN COALESCE(tags['shop'],'')    <> '' THEN 0.10 ELSE 0 END) +
          (CASE WHEN tags['website'] IS NOT NULL  THEN 0.05 ELSE 0 END)
    ) AS importance
FROM src
WHERE tags['amenity'] IS NOT NULL
   OR tags['shop']    IS NOT NULL
   OR tags['tourism'] IS NOT NULL
   OR tags['leisure'] IS NOT NULL
   OR tags['office']  IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_pois_name_local_norm ON gaz.pois(name_local_norm);
CREATE INDEX IF NOT EXISTS ix_pois_name_en_norm    ON gaz.pois(name_en_norm);