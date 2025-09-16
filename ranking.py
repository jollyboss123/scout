import math
from rapidfuzz import fuzz

def norm(s: str) -> str:
    return " ".join(
        s.lower().replace("#"," ").replace("@"," ")
        .translate({ord(c):" " for c in r"""!"$%&'()*+,./:;<=>?@[\]^_`{|}~"""})
        .split()
    )

def tokens(name: str) -> list[str]:
    return [t for t in norm(name).split() if t]

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def score_rows(cands_texts, rows, limit, weights, type_boost_map, bbox=None, proximity_km=25.0):
    def type_boost(k: str) -> float:
        for key, val in type_boost_map.items():
            if key != "default" and k.startswith(key):
                return float(val)
        return float(type_boost_map.get("default", 0.4))

    ctr_lat = ctr_lon = None
    if bbox:
        _, _, _, _, ctr_lat, ctr_lon = bbox

    scored = []
    for r in rows:
        (osm_id, name_local, name_en, local_norm, en_norm,
         amenity, shop, tourism, leisure, office,
         city, state, country, lat, lon, kind, importance) = r

        best_sim = 0.0
        for qtext in cands_texts:
            q = norm(qtext or "")
            if not q: continue
            target_local = (local_norm or norm(name_local or ""))
            target_en    = (en_norm    or norm(name_en    or ""))
            sim = max(fuzz.WRatio(q, target_local) if target_local else 0,
                      fuzz.WRatio(q, target_en)    if target_en    else 0)
            best_sim = max(best_sim, sim / 100.0)

        s = (weights["similarity"] * best_sim) \
            + (weights["type"]       * type_boost(kind)) \
            + (weights["importance"] * float(importance or 0.0))

        if ctr_lat is not None and ctr_lon is not None and lat is not None and lon is not None:
            d = haversine_km(float(lat), float(lon), float(ctr_lat), float(ctr_lon))
            prox = max(0.0, 1.0 - min(d / proximity_km, 1.0))
            s += weights["proximity"] * prox

        label = name_local or name_en or ""
        scored.append((s, {
            "name": label, "lat": float(lat), "lon": float(lon),
            "country": country, "state": state, "city": city,
            "osm_id": int(osm_id), "kind": kind, "score": s
        }))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [hit for _, hit in scored[:limit]]