import os, time, duckdb
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from pydantic import BaseModel
from typing import Optional, List

from settings import load_settings, Settings
from repo import resolve_area_bbox, fetch_candidates
from ranking import tokens, score_rows

class ForwardCandidate(BaseModel): text: str
class ForwardReq(BaseModel):
    candidates: List[ForwardCandidate]
    country: Optional[str] = None
    city_hint: Optional[str] = None
    limit: int = 5

class Hit(BaseModel):
    name: str; lat: float; lon: float
    country: Optional[str] = None; state: Optional[str] = None; city: Optional[str] = None
    osm_id: int; kind: Optional[str] = None; score: float

class ForwardResp(BaseModel): hits: List[Hit]

def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        con = duckdb.connect(settings.db_path, read_only=True)
        try:
            con.execute("INSTALL spatial; LOAD spatial;")
        except Exception: pass
        app.state.db = con
        app.state.settings = settings
        try:
            yield
        finally:
            try: con.close()
            except Exception: pass

    app = FastAPI(title="scout", version="1.0.0", lifespan=lifespan)

    def get_db(request: Request) -> duckdb.DuckDBPyConnection:
        return request.app.state.db

    @app.post("/v1/geocode/forward", response_model=ForwardResp)
    def forward(req: ForwardReq, con: duckdb.DuckDBPyConnection = Depends(get_db)):
        t0 = time.time()
        toks: list[str] = []
        for c in (req.candidates or []):
            toks.extend(tokens(c.text or ""))
        # de-dup preserving order
        seen = set()
        seen, name_tokens = set(), [t for t in toks if not (t in seen or seen.add(t))]
        if not name_tokens:
            return ForwardResp(hits=[])

        bbox = resolve_area_bbox(con, req.city_hint, req.country)
        rows = fetch_candidates(con, name_tokens, bbox, limit_scan=10000)

        settings = app.state.settings
        cands_texts = [c.text for c in (req.candidates or [])]
        hits_raw = score_rows(
            cands_texts, rows, req.limit,
            settings.weights, settings.type_boost,
            bbox=bbox, proximity_km=settings.proximity_km
        )
        return ForwardResp(hits=[Hit(**h) for h in hits_raw])

    @app.get("/healthz")
    def healthz(): return {"ok": True}

    return app

# entrypoint
SCOUT_CONFIG = os.getenv("SCOUT_CONFIG", "config.toml")
app = create_app(load_settings(SCOUT_CONFIG))