import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

import duckdb

DEFAULT_PBF   = "https://download.geofabrik.de/asia/malaysia-singapore-brunei-latest.osm.pbf"
DEFAULT_OUT   = "data/gazetteer.duckdb"
DEFAULT_TABLE = "raw_osm"
SCHEMA_VERSION = "1.0.0"  # bump on breaking schema changes

def ensure_meta_table(con: duckdb.DuckDBPyConnection):
    con.execute("""
                CREATE TABLE IF NOT EXISTS gaz_meta(
                                                       key   TEXT PRIMARY KEY,
                                                       value TEXT NOT NULL
                );
                """)

def render_sql_with_placeholders(sql_text: str, raw_cols: list[str], raw_table: str) -> str:
    has_name = any(c.lower() == "name" for c in raw_cols)
    id_col   = next((c for c in raw_cols if c.lower() in ("id","osm_id")), None)
    geom_col = next((c for c in raw_cols if c.lower() in ("geometry","geom","wkb_geometry","wkt")), None)
    if not geom_col:
        raise RuntimeError("No geometry column found.")

    NAME_ARG  = "name" if has_name else "CAST(NULL AS VARCHAR)"
    ID_EXPR   = f"CAST({id_col} AS BIGINT)" if id_col else "ROW_NUMBER() OVER ()::BIGINT"
    GEOM_EXPR = f"ST_GeomFromText({geom_col})" if geom_col.lower() == "wkt" else geom_col

    # Do the replacements
    sql = (sql_text
           .replace("{RAW_TABLE}", f'"{raw_table}"')
           .replace("{NAME_ARG}", NAME_ARG)
           .replace("{ID_EXPR}", ID_EXPR)
           .replace("{GEOM_EXPR}", GEOM_EXPR))
    return sql

def apply_migrations(con: duckdb.DuckDBPyConnection, dir_path: str, raw_table: str):
    """Run ALL .sql files in lexical order every build."""
    raw_cols = [r[1] for r in con.execute(f"PRAGMA table_info('{raw_table}')").fetchall()]
    for f in sorted(Path(dir_path).glob("*.sql")):
        sql_text = f.read_text(encoding="utf-8")
        sql = render_sql_with_placeholders(sql_text, raw_cols, raw_table)
        con.execute("BEGIN")
        try:
            con.execute(sql)
            con.execute("COMMIT")
            print(f"[migrate] applied {f.name}")
        except Exception as e:
            con.execute("ROLLBACK")
            raise RuntimeError(f"Migration {f.name} failed: {e}") from e

def record_build_meta(
        con: duckdb.DuckDBPyConnection,
        pbf: str,
        quack_cmd: list[str],
        schema_version: str,
        artifact_path: str
):
    ensure_meta_table(con)
    con.execute("BEGIN")
    try:
        con.execute("""
                    DELETE FROM gaz_meta
                    WHERE key IN ('pbf','duckdb_version','quackosm_args','schema_version','built_at','artifact_path')
                    """)
        # version(), CURRENT_TIMESTAMP come from DuckDB
        con.execute("""
                    INSERT INTO gaz_meta(key,value)
                    SELECT 'duckdb_version', version()
                    UNION ALL SELECT 'pbf', ?
                    UNION ALL SELECT 'quackosm_args', ?
                    UNION ALL SELECT 'schema_version', ?
                    UNION ALL SELECT 'built_at', CAST(CURRENT_TIMESTAMP AS TEXT)
                    UNION ALL SELECT 'artifact_path', ?
                    """, [pbf, " ".join(shlex.quote(x) for x in quack_cmd), schema_version, artifact_path])
        con.execute("COMMIT")
    except:
        con.execute("ROLLBACK"); raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pbf", default=DEFAULT_PBF, help="PBF URL or local path")
    ap.add_argument("--out", default=DEFAULT_OUT, help="DuckDB file to write")
    ap.add_argument("--table", default=DEFAULT_TABLE, help="Raw table name in DuckDB")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--filter-file", help="Optional JSON tags filter for QuackOSM (see docs)")
    ap.add_argument("--bbox", help="Optional bbox filter: minx,miny,maxx,maxy")
    ap.add_argument("--geocode", help='Optional geometry filter via text, e.g. "Kuala Lumpur, Malaysia"')
    ap.add_argument("--explode-tags", action="store_true", help="Explode tags to columns (instead of MAP)")
    ap.add_argument("--migrations-dir", default="sql/migrations", help="Path to migrations dir")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    if os.path.exists(args.out) and not args.overwrite:
        print(f"[build] {args.out} already exists. Use --overwrite to rebuild.", file=sys.stderr)
        sys.exit(0)

    # 1) quackosm → DuckDB raw table
    cmd = ["quackosm", args.pbf, "--duckdb", "--output", args.out,
           "--duckdb-table-name", args.table, "--no-sort"]
    if args.filter_file:
        cmd += ["--osm-tags-filter-file", args.filter_file]
        cmd += ["--explode-tags"] if args.explode_tags else ["--compact-tags"]
    else:
        cmd += ["--compact-tags"]
    if args.bbox:
        cmd += ["--geom-filter-bbox", args.bbox]
    if args.geocode:
        cmd += ["--geom-filter-geocode", args.geocode]

    print("[build] running:", " ".join(shlex.quote(x) for x in cmd))
    subprocess.run(cmd, check=True)

    # 2) open DB, run migrations using dynamic macros
    print("[build] materializing gazetteer")
    con = duckdb.connect(args.out)

    # Make base schema & canon macro available first
    init_sql = Path(args.migrations_dir, "000_init.sql").read_text(encoding="utf-8")
    con.execute(init_sql)

    # Apply all remaining migrations transactionally
    apply_migrations(con, args.migrations_dir, args.table)

    # 3) metadata
    record_build_meta(con, args.pbf, cmd, SCHEMA_VERSION, args.out)

    con.close()
    print("[build] done:", args.out)

if __name__ == "__main__":
    main()