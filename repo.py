from typing import Optional
import duckdb


def like_clause_for_tokens(tokens: list[str], cols: list[str]) -> tuple[str, list[str]]:
    if not tokens:
        return "1=1", []
    conds, params = [], []
    for t in tokens:
        ors = " OR ".join(f"{c} LIKE ?" for c in cols)
        conds.append(f"({ors})")
        params.extend([f"%{t}%"] * len(cols))
    return " AND ".join(conds), params


def resolve_area_bbox(
    con: duckdb.DuckDBPyConnection, city_hint: Optional[str], country: Optional[str]
) -> Optional[tuple[float, float, float, float, float, float]]:
    def _norm_tokens(s: Optional[str]) -> list[str]:
        if not s:
            return []
        return [t for t in s.lower().split() if t]

    if city_hint:
        where, params = like_clause_for_tokens(
            _norm_tokens(city_hint), ["name_local_norm", "name_en_norm"]
        )
        q = f"""SELECT minx,miny,maxx,maxy,center_lat,center_lon
                FROM gaz.admin WHERE {where} AND admin_level >= 6
                ORDER BY (maxx-minx)*(maxy-miny) DESC LIMIT 1"""
        r = con.execute(q, params).fetchone()
        if r:
            return tuple(map(float, r))  # type: ignore

    if country:
        where, params = like_clause_for_tokens(
            _norm_tokens(country), ["name_local_norm", "name_en_norm"]
        )
        q = f"""SELECT minx,miny,maxx,maxy,center_lat,center_lon
                FROM gaz.admin WHERE {where} AND admin_level = 2
                ORDER BY (maxx-minx)*(maxy-miny) DESC LIMIT 1"""
        r = con.execute(q, params).fetchone()
        if r:
            return tuple(map(float, r))  # type: ignore
    return None


def fetch_candidates(
    con: duckdb.DuckDBPyConnection,
    name_tokens: list[str],
    bbox: Optional[tuple[float, float, float, float, float, float]],
    limit_scan: int = 10000,
) -> list[tuple]:
    where_name, params = like_clause_for_tokens(
        name_tokens, ["name_local_norm", "name_en_norm"]
    )
    bbox_sql = ""
    if bbox:
        minx, miny, maxx, maxy, _, _ = bbox
        bbox_sql = " AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ? "
        params += [miny, maxy, minx, maxx]
    sql = f"""
      SELECT osm_id,name_local,name_en,name_local_norm,name_en_norm,
             amenity,shop,tourism,leisure,office,
             city,state,country,lat,lon,kind,importance
      FROM gaz.poi_view
      WHERE {where_name}
      {bbox_sql}
      LIMIT {limit_scan}
    """
    return con.execute(sql, params).fetchall()
