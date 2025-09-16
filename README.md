<img src="images/duck-scout.png" alt="Scout logo — duck with binoculars" width="300">

# Scout 
[![CI](https://github.com/jollyboss123/scout/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jollyboss123/scout/actions/workflows/ci.yml)

A lightweight, on-demand forward geocoder for OSM data—name in, lat/lon out—that can replace self-hosted Nominatim for many use cases and cut cold-start from ~30 min to ~1 min on typical regional datasets. (Numbers are from my machine—YMMV.)

| Aspect                        | This project                            | Self-hosted Nominatim                                      | Paid SaaS (typical) |
|------------------------------|------------------------------------------|-------------------------------------------------------------|---------------------|
| Boot/Build time (example)    | ~**1 min** local (MSB PBF)               | ~**30 min** to pull image (MSB PBF), plus import/prepare    | Instant (external)  |
| Infra                        | **Ephemeral** / on-demand                | **24/7** server(s), stateful                                | Vendor-managed      |
| Storage                      | Small (DuckDB/Parquet)                   | Large Postgres DB + indices                                 | N/A (vendor)        |
| Ops                          | Simple container or process              | DB tuning, updates, backups                                 | Vendor-managed      |
| Use case fit                 | **Forward geocoding by name**            | Full geocoding stack (forward + reverse + addresses)        | Varies, $$$         |

## Run it locally (via Makefile)

Prereq: uv installed.
```bash
# 1) Create the virtualenv and install deps from pyproject.toml
make install

# 2) Build the gazetteer DuckDB from the PBF in config.toml
make build-gaz

# 3) Start the API (dev, auto-reload)
make run
```
* API base URL: http://localhost:8000
* Swagger UI: http://localhost:8000/docs
* OpenAPI JSON: http://localhost:8000/openapi.json

## Attribution
The free [OpenStreetMap](https://www.openstreetmap.org/) data, which is used for the development of Scout, is licensed under the [Open Data Commons Open Database License](https://opendatacommons.org/licenses/odbl/) (ODbL) by the [OpenStreetMap Foundation](https://osmfoundation.org/) (OSMF).