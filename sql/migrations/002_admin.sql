DROP TABLE IF EXISTS gaz.admin;

CREATE TABLE gaz.admin AS
SELECT
    {ID_EXPR}                               AS osm_id,
    gaz.name_local({NAME_ARG}, tags)        AS name_local,
    gaz.name_en(tags)                       AS name_en,
    gaz.canon(gaz.name_local({NAME_ARG}, tags)) AS name_local_norm,
    gaz.canon(gaz.name_en(tags))            AS name_en_norm,
    TRY_CAST(NULLIF(tags['admin_level'],'') AS INTEGER) AS admin_level,
    NULLIF(tags['admin_level'],'') AS admin_level_raw,
    COALESCE(tags['ISO3166-1'], '') AS iso1,
    COALESCE(tags['ISO3166-2'], '') AS iso2,
    {GEOM_EXPR}                             AS geom,
    ST_XMin({GEOM_EXPR})                    AS minx,
    ST_YMin({GEOM_EXPR})                    AS miny,
    ST_XMax({GEOM_EXPR})                    AS maxx,
    ST_YMax({GEOM_EXPR})                    AS maxy,
    ST_Y(ST_Centroid({GEOM_EXPR}))          AS center_lat,
    ST_X(ST_Centroid({GEOM_EXPR}))          AS center_lon
FROM {RAW_TABLE}
WHERE COALESCE(tags['boundary'],'') = 'administrative'
AND {GEOM_EXPR} IS NOT NULL
AND (gaz.name_local({NAME_ARG}, tags) IS NOT NULL OR gaz.name_en(tags) IS NOT NULL);

CREATE INDEX IF NOT EXISTS ix_admin_name_local_norm ON gaz.admin(name_local_norm);
CREATE INDEX IF NOT EXISTS ix_admin_name_en_norm    ON gaz.admin(name_en_norm);
CREATE INDEX IF NOT EXISTS ix_admin_level           ON gaz.admin(admin_level);