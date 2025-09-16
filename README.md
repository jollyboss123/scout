<img src="images/duck-scout.png" alt="Scout logo — duck with binoculars" width="300">

# Scout
A lightweight, on-demand forward geocoder for OSM data—name in, lat/lon out—that can replace self-hosted Nominatim for many use cases and cut cold-start from ~30 min to ~1 min on typical regional datasets.

| Aspect                        | This project                            | Self-hosted Nominatim                                      | Paid SaaS (typical) |
|------------------------------|------------------------------------------|-------------------------------------------------------------|---------------------|
| Boot/Build time (example)    | ~**1 min** local (MSB PBF)               | ~**30 min** to pull image (MSB PBF), plus import/prepare    | Instant (external)  |
| Infra                        | **Ephemeral** / on-demand                | **24/7** server(s), stateful                                | Vendor-managed      |
| Storage                      | Small (DuckDB/Parquet)                   | Large Postgres DB + indices                                 | N/A (vendor)        |
| Ops                          | Simple container or process              | DB tuning, updates, backups                                 | Vendor-managed      |
| Use case fit                 | **Forward geocoding by name**            | Full geocoding stack (forward + reverse + addresses)        | Varies, $$$         |

