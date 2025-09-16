import math
import os
import time
from contextlib import asynccontextmanager
from typing import Optional, List, Tuple

import duckdb
from fastapi import Depends, Request, FastAPI
from pydantic import BaseModel
from rapidfuzz import fuzz

DB_PATH = os.path.abspath(os.getenv("GAZETTEER_DB_PATH", "data/gazetteer.duckdb"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1) open DuckDB (read-only for serving)
    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
    except Exception:
        pass
    app.state.db = con

    try:
        yield
    finally:
        try:
            con.close()
        except Exception:
            pass

app = FastAPI(title="scout", version="1.0.0", lifespan=lifespan)

class ForwardCandidate(BaseModel):
    text: str

class ForwardReq(BaseModel):
    candidates: List[ForwardCandidate]
    country: Optional[str] = None
    city_hint: Optional[str] = None
    limit: int = 5

class Hit(BaseModel):
    name: str
    lat: float
    lon: float
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    osm_id: int
    kind: Optional[str] = None
    score: float

class ForwardResp(BaseModel):
    hits: List[Hit]

# DI helper to fetch the lifespan-managed DuckDB connection
def get_db(request: Request) -> duckdb.DuckDBPyConnection:
    return request.app.state.db  # type: ignore[return-value]

def _norm(s: str) -> str:
    return " ".join(
        s.lower().replace("#", " ").replace("@", " ")
        .translate({ord(c): " " for c in r"""!"$%&'()*+,./:;<=>?@[\]^_`{|}~"""})
        .split()
    )

def _tokens(name: str) -> list[str]:
    n = _norm(name)
    return [t for t in n.split() if t]  # keep short ones too; RapidFuzz is robust

def _like_clause_for_tokens(tokens: list[str], cols: list[str]) -> tuple[str, list[str]]:
    """
    Build: (col1 LIKE ? OR col2 LIKE ?) AND ... per token
    """
    if not tokens:
        return "1=1", []
    conds, params = [], []
    for t in tokens:
        ors = " OR ".join(f"{c} LIKE ?" for c in cols)
        conds.append(f"({ors})")
        params.extend([f"%{t}%"] * len(cols))
    return " AND ".join(conds), params

def _resolve_area_bbox(con: duckdb.DuckDBPyConnection,
                       city_hint: Optional[str],
                       country: Optional[str]) -> Optional[tuple[float,float,float,float,float,float]]:
    if city_hint:
        toks = _tokens(city_hint)
        where, params = _like_clause_for_tokens(toks, ["name_local_norm", "name_en_norm"])
        q = f"""
          SELECT minx, miny, maxx, maxy, center_lat, center_lon, admin_level
          FROM gaz.admin
          WHERE {where} AND admin_level >= 6
          ORDER BY (maxx-minx)*(maxy-miny) DESC
          LIMIT 1
        """
        rows = con.execute(q, params).fetchall()
        if rows:
            (minx, miny, maxx, maxy, clat, clon, _) = rows[0]
            return float(minx), float(miny), float(maxx), float(maxy), float(clat), float(clon)

    if country:
        toks = _tokens(country)
        where, params = _like_clause_for_tokens(toks, ["name_local_norm", "name_en_norm"])
        q = f"""
          SELECT minx, miny, maxx, maxy, center_lat, center_lon, admin_level
          FROM gaz.admin
          WHERE {where} AND admin_level = 2
          ORDER BY (maxx-minx)*(maxy-miny) DESC
          LIMIT 1
        """
        rows = con.execute(q, params).fetchall()
        if rows:
            (minx, miny, maxx, maxy, clat, clon, _) = rows[0]
            return float(minx), float(miny), float(maxx), float(maxy), float(clat), float(clon)

    return None

def _fetch_candidates(con: duckdb.DuckDBPyConnection,
                      name_tokens: list[str],
                      bbox: Optional[tuple[float,float,float,float,float,float]],
                      limit_scan: int = 10000) -> list[tuple]:
    where_name, params = _like_clause_for_tokens(name_tokens, ["name_local_norm", "name_en_norm"])
    bbox_sql = ""
    if bbox:
        minx, miny, maxx, maxy, _, _ = bbox
        bbox_sql = " AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ? "
        params += [miny, maxy, minx, maxx]

    sql = f"""
      SELECT
        osm_id,
        name_local,
        name_en,
        name_local_norm,
        name_en_norm,
        amenity, shop, tourism, leisure, office,
        city, state, country, lat, lon, kind, importance
      FROM gaz.poi_view
      WHERE {where_name}
      {bbox_sql}
      LIMIT {limit_scan}
    """
    return con.execute(sql, params).fetchall()

def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    # standard haversine
    R = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def kind_of(row: Tuple) -> str:
    amenity, shop, tourism, leisure, office = row[3], row[4], row[5], row[6], row[7]
    for k, v in [("amenity", amenity), ("shop", shop), ("tourism", tourism), ("leisure", leisure), ("office", office)]:
        if v: return f"{k}:{v}"
    return "unknown"

def rank(cands: List[ForwardCandidate],
         rows: List[tuple],
         limit: int,
         bbox: Optional[tuple[float,float,float,float,float,float]]) -> List[Hit]:
    def type_boost(k: str) -> float:
        if k.startswith("tourism:"):           return 0.8
        if k.startswith("amenity:"):           return 0.7
        if k.startswith("shop:"):              return 0.6
        return 0.4

    scored = []
    ctr_lat = ctr_lon = None
    if bbox:
        _, _, _, _, ctr_lat, ctr_lon = bbox

    for r in rows:
        (osm_id, name_local, name_en, local_norm, en_norm,
         amenity, shop, tourism, leisure, office,
         city, state, country, lat, lon, kind, importance) = r

        best_sim, best_src_conf = 0.0, 0.0
        for c in cands:
            q = _norm(c.text or "")
            if not q:
                continue
            # compare against BOTH norms; fallback to raw names if norms are NULL
            target_local = (local_norm or _norm(name_local or ""))
            target_en    = (en_norm    or _norm(name_en    or ""))

            sim_local = fuzz.WRatio(q, target_local) if target_local else 0
            sim_en    = fuzz.WRatio(q, target_en)    if target_en    else 0
            sim = max(sim_local, sim_en)
            best_sim = max(best_sim, sim / 100.0)

        s = (0.60 * best_sim) + (0.25 * type_boost(kind)) + (0.15 * float(importance or 0.0))
        if best_src_conf:
            s = 0.85 * s + 0.15 * best_src_conf

        if ctr_lat is not None and ctr_lon is not None and lat is not None and lon is not None:
            d = _haversine_km(float(lat), float(lon), float(ctr_lat), float(ctr_lon))
            prox = max(0.0, 1.0 - min(d / 25.0, 1.0))
            s += 0.15 * prox

        label = name_local or name_en or ""
        scored.append((s, Hit(
            name=label,
            lat=float(lat),
            lon=float(lon),
            country=country,
            state=state,
            city=city,
            osm_id=int(osm_id),
            kind=kind,
            score=s,
        )))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in scored[:limit]]

@app.post("/v1/geocode/forward", response_model=ForwardResp)
def forward(req: ForwardReq, con: duckdb.DuckDBPyConnection = Depends(get_db)):
    t0 = time.time()

    # 1) Build name tokens from all candidates
    toks: list[str] = []
    for c in (req.candidates or []):
        toks.extend(_tokens(c.text or ""))
    # de-dup while preserving order
    seen = set()
    toks = [t for t in toks if not (t in seen or seen.add(t))]

    if not toks:
        return ForwardResp(hits=[])

    # 2) Resolve bbox from admin areas (city first, else country)
    bbox = _resolve_area_bbox(con, req.city_hint, req.country)

    # 3) Fetch candidates by name (and bbox if available)
    rows = _fetch_candidates(con, toks, bbox, limit_scan=10000)

    # 4) Rank
    hits = rank(req.candidates or [], rows, req.limit, bbox)
    return ForwardResp(hits=hits)