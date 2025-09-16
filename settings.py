import os
from dataclasses import dataclass
import tomllib

@dataclass
class Settings:
    db_path: str = "data/gazetteer.duckdb"
    pbf_url: str = ""
    build_overwrite: bool = False
    weights: dict | None = None
    type_boost: dict | None = None
    proximity_km: float = 25.0

def _get_bool(s: str | bool | None, default=False) -> bool:
    if isinstance(s, bool): return s
    if s is None: return default
    return str(s).lower() in {"1","true","yes","y","on"}

def load_settings(path: str | None = "config.toml") -> Settings:
    cfg = {}
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            cfg = tomllib.load(f)

    data = cfg.get("data", {})
    rank = cfg.get("ranking", {})
    w    = rank.get("weights", {})
    tb   = rank.get("type_boost", {}) or {}
    build= cfg.get("build", {})

    db_path = os.getenv("GAZETTEER_DB_PATH", data.get("db_path", "data/gazetteer.duckdb"))
    pbf_url = os.getenv("PBF_URL", data.get("pbf_url", ""))
    overwrite = _get_bool(os.getenv("OVERWRITE"), build.get("overwrite", False))

    return Settings(
        db_path=db_path,
        pbf_url=pbf_url,
        build_overwrite=overwrite,
        weights={
            "similarity": float(w.get("similarity", 0.60)),
            "type":       float(w.get("type", 0.25)),
            "importance": float(w.get("importance", 0.15)),
            "proximity":  float(w.get("proximity", 0.15)),
        },
        type_boost=tb,
        proximity_km=float(w.get("proximity_km", 25)),
    )