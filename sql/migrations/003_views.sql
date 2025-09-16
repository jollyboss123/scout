DROP VIEW IF EXISTS gaz.poi_view;
CREATE VIEW gaz.poi_view AS
SELECT
    osm_id, name_local, name_en,
    name_local_norm, name_en_norm,
    amenity, shop, tourism, leisure, office,
    city, state, country, lat, lon, kind, importance
FROM gaz.pois;