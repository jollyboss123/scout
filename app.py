import os
import time
from typing import Optional, List, Generator

import duckdb
from fastapi import FastAPI, Depends, Body
from pydantic import BaseModel

from ranking import tokens, score_rows
from repo import resolve_area_bbox, fetch_candidates
from settings import load_settings, Settings


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


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="scout", version="1.0.0")

    def get_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
        con = duckdb.connect(settings.db_path, read_only=True)
        try:
            try:
                con.execute("LOAD spatial;")
            except duckdb.Error:
                con.execute("INSTALL spatial; LOAD spatial;")
            yield con
        finally:
            try:
                con.close()
            except Exception:
                pass

    @app.middleware("http")
    async def add_server_timing(request, call_next):
        t0 = time.perf_counter()
        resp = await call_next(request)
        dur_ms = (time.perf_counter() - t0) * 1000.0
        resp.headers["Server-Timing"] = f"app;dur={dur_ms:.1f}"
        resp.headers["X-Process-Time"] = f"{dur_ms:.1f}ms"
        return resp

    @app.post(
        "/v1/geocode/forward",
        response_model=ForwardResp,
        summary="Name → lat/lon",
        tags=["geocoding"],
    )
    def forward(
        req: ForwardReq = Body(
            openapi_examples={
                "basic": {
                    "summary": "Restaurant by country",
                    "value": {
                        "candidates": [{"text": "Monograph Dining"}],
                        "country": "my",
                        "limit": 3,
                    },
                }
            }
        ),
        con: duckdb.DuckDBPyConnection = Depends(get_db),
    ):
        # build tokens
        toks: list[str] = []
        for c in req.candidates or []:
            toks.extend(tokens(c.text or ""))

        # de-dup while preserving order
        seen: set[str] = set()
        name_tokens = [t for t in toks if not (t in seen or seen.add(t))]
        if not name_tokens:
            return ForwardResp(hits=[])

        # bbox + fetch
        bbox = resolve_area_bbox(con, req.city_hint, req.country)
        rows = fetch_candidates(con, name_tokens, bbox, limit_scan=10000)

        # score using closed-over `settings` (no app.state.settings)
        cands_texts = [c.text for c in (req.candidates or [])]
        hits_raw = score_rows(
            cands_texts,
            rows,
            req.limit,
            settings.weights,
            settings.type_boost,
            bbox=bbox,
            proximity_km=settings.proximity_km,
        )
        return ForwardResp(hits=[Hit(**h) for h in hits_raw])

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    return app


# entrypoint
SCOUT_CONFIG = os.getenv("SCOUT_CONFIG", "config.toml")
app = create_app(load_settings(SCOUT_CONFIG))
