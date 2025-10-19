
import json, math, re
from typing import Dict, Any, List, Tuple, Set
from pathlib import Path
from .schema import Dish, SearchRequest, SearchResponse, SearchResult

def _norm_str(t: str) -> str:
    return (t or "").lower()\
        .replace("á","a").replace("é","e").replace("í","i")\
        .replace("ó","o").replace("ú","u").replace("ñ","n")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DICT_DIR = DATA_DIR / "dictionaries"

CATALOG: List[Dict[str, Any]] = json.loads((DATA_DIR / "catalog.json").read_text(encoding="utf-8"))

def load_ingredient_synonyms() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    try:
        data = json.loads((DICT_DIR / "ingredients.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return mapping
    for canonical, obj in data.items():
        norm_canon = _norm_str(canonical)
        mapping.setdefault(norm_canon, canonical)
        for syn in obj.get("synonyms", []):
            mapping.setdefault(_norm_str(syn), canonical)
    return mapping

INGREDIENT_SYNONYM_MAP = load_ingredient_synonyms()

def load_ingredient_groups() -> Dict[str, Set[str]]:
    groups: Dict[str, Set[str]] = {}
    try:
        data = json.loads((DICT_DIR / "ingredients.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return groups
    for canonical, obj in data.items():
        normalized = { _norm_str(canonical) }
        for syn in obj.get("synonyms", []):
            normalized.add(_norm_str(syn))
        groups[canonical] = normalized
    return groups

INGREDIENT_GROUPS = load_ingredient_groups()

def norm(val, vmin, vmax):
    if vmax == vmin:
        return 0.0
    return max(0.0, min(1.0, (val - vmin) / (vmax - vmin)))

def build_indexes():
    prices = [d["price_ars"] for d in CATALOG]
    etas = [d["restaurant"]["eta_min"] for d in CATALOG]
    ratings = [d["restaurant"]["rating"] for d in CATALOG]
    return {
        "price_min": min(prices), "price_max": max(prices),
        "eta_min": min(etas), "eta_max": max(etas),
        "rating_min": min(ratings), "rating_max": max(ratings),
        "prices_sorted": sorted(prices)
    }

IDX = build_indexes()

def percentile_price(label: str) -> int:
    # label like "p20"
    try:
        p = int(label[1:]) / 100.0
        idx = max(0, min(len(IDX["prices_sorted"])-1, int(p * len(IDX["prices_sorted"]))-1))
        return IDX["prices_sorted"][idx]
    except Exception:
        return None



def lex_score(q: str, dish: Dict[str, Any], filters: Dict[str, Any]) -> float:
    if not q:
        return 0.0
    qn = _norm_str(q)
    q_words = set(re.findall(r"\w+", qn))

    base = " ".join([
        dish["dish_name"],
        dish["description"],
        " ".join(dish.get("synonyms", [])),
        " ".join(dish.get("ingredients", [])),
        dish["restaurant"]["name"],
    ])
    base = _norm_str(base)
    base_words = set(re.findall(r"\w+", base))

    if not q_words:
        return 0.0

    inter = q_words & base_words
    score = len(inter) / max(1, len(q_words))

    # boost por nombre de restaurante exacto, pero solo si no contradice categorías pedidas
    rn = _norm_str(dish["restaurant"]["name"])
    cat_filter = set((filters or {}).get("category_any") or [])
    if rn and rn in qn and (not cat_filter or any(c in dish.get("categories", []) for c in cat_filter)):
        score = min(1.0, score + 0.4)
    return score



def expand_ingredients(ingredients: List[str]) -> Set[str]:
    tokens = {_norm_str(raw) for raw in ingredients}
    canonical_hits = set()
    for canonical, group in INGREDIENT_GROUPS.items():
        if group & tokens:
            canonical_hits.add(canonical)
    return tokens | canonical_hits

def apply_filters(d: Dict[str, Any], f: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons = []
    dish_ingredients = expand_ingredients(d.get("ingredients", []))
    if f.get("available_only", True) and not d.get("available", True):
        return False, ["No disponible"]
    # categories
    mm = f.get("meal_moments_any") or []
    if mm and not any(m in d.get("meal_moments", []) for m in mm):
        return False, [f"Meal moment no coincide {mm}"]
    # categories
    cats = f.get("category_any") or []
    if cats and not any(c in d["categories"] for c in cats):
        return False, [f"Categoria no coincide {cats}"]
    # neighborhood
    nhs = f.get("neighborhood_any") or []
    if nhs and d["restaurant"]["neighborhood"] not in nhs:
        return False, [f"Barrio no coincide {nhs}"]
    # cuisines
    cu = f.get("cuisines_any") or []
    if cu and d["restaurant"]["cuisines"] not in cu:
        return False, [f"Cocina no coincide {cu}"]
    exp = f.get("experience_tags_any") or []
    if exp and not any(tag in (d.get("experience_tags") or []) for tag in exp):
        return False, [f"Experiencia no coincide {exp}"]
    # include ingredients
    inc = f.get("ingredients_include") or []
    if inc and not all((_norm_str(i) in dish_ingredients) or (INGREDIENT_SYNONYM_MAP.get(_norm_str(i)) in dish_ingredients) or (i in dish_ingredients) for i in inc):
        return False, [f"Falta ingrediente requerido"]
    # exclude ingredients
    exc = f.get("ingredients_exclude") or []
    if exc and any((_norm_str(i) in dish_ingredients) or (INGREDIENT_SYNONYM_MAP.get(_norm_str(i)) in dish_ingredients) or (i in dish_ingredients) for i in exc):
        return False, [f"Contiene ingrediente excluido"]
    # diet must
    dm = f.get("diet_must") or []
    if dm and not all(d["diet_flags"].get(flag, False) for flag in dm):
        return False, [f"No cumple dietas requeridas {dm}"]
    # allergens exclude
    ae = f.get("allergens_exclude") or []
    if ae and any(a in d["allergens"] for a in ae):
        return False, [f"Contiene alergenos excluidos {ae}"]
    # health any
    ha = f.get("health_any") or []
    if ha and not any(h in d.get("health_tags", []) for h in ha):
        return False, [f"No coincide salud {ha}"]
    # price max
    pm = f.get("price_max")
    if isinstance(pm, str) and pm and pm.startswith("p"):
        pm_val = percentile_price(pm)
    else:
        pm_val = pm
    if pm_val is not None and d["price_ars"] > pm_val:
        return False, [f"Precio mayor a limite"]
    # eta max
    em = f.get("eta_max")
    if em is not None and d["restaurant"]["eta_min"] > em:
        return False, [f"ETA mayor a limite"]
    # rating min
    rm = f.get("rating_min")
    if rm is not None and d["restaurant"]["rating"] < rm:
        return False, [f"Rating menor a minimo"]
    return True, reasons

def distance_score(d: Dict[str, Any], f: Dict[str, Any]) -> float:
    # simple proxy: if neighborhood matches any, score 1 else 0.5
    nhs = f.get("neighborhood_any") or []
    if not nhs:
        return 0.5
    return 1.0 if d["restaurant"]["neighborhood"] in nhs else 0.0

def compute_score(d: Dict[str, Any], f: Dict[str, Any], q: Dict[str, Any]) -> Tuple[float, List[str]]:
    weights = {"rating":0.3,"price":0.3,"eta":0.1,"pop":0.1,"dist":0.1,"lex":0.1}
    weights.update(q.get("weights", {}))
    weights.update((q.get("ranking_overrides") or {}).get("weights", {}))
    # normalize
    r = d["restaurant"]["rating"]
    rating_n = norm(r, IDX["rating_min"], IDX["rating_max"])
    price_n = norm(d["price_ars"], IDX["price_min"], IDX["price_max"])
    eta_n = norm(d["restaurant"]["eta_min"], IDX["eta_min"], IDX["eta_max"])
    pop_n = d.get("popularity", 0) / 100.0
    dist_n = distance_score(d, q.get("filters", {}))
    lex_n = lex_score(q.get("q",""), d, q.get("filters", {}))
    score = (
        weights["rating"] * rating_n +
        weights["price"] * (1 - price_n) +
        weights["eta"]   * (1 - eta_n) +
        weights["pop"]   * pop_n +
        weights["dist"]  * dist_n +
        weights["lex"]   * lex_n
    )
    reasons = [
        f"rating:{rating_n:.2f}",
        f"price_inv:{1-price_n:.2f}",
        f"eta_inv:{1-eta_n:.2f}",
        f"pop:{pop_n:.2f}",
        f"dist:{dist_n:.2f}",
        f"lex:{lex_n:.2f}"
    ]
    # boosts and penalties
    ro = (q.get("ranking_overrides") or {})
    boost = ro.get("boost_tags") or []
    penal = ro.get("penalize_tags") or []
    tags = set(d.get("health_tags", []) + d.get("categories", []) + d.get("experience_tags", []) + [d["restaurant"]["cuisines"].lower()])
    if any(b in tags for b in boost):
        score *= 1.10
        reasons.append("boost")
    if any(p in tags for p in penal):
        score *= 0.85
        reasons.append("penal")
    return score, reasons

def search(req: Dict[str, Any]) -> Dict[str, Any]:
    q = req.get("query") or {"filters": req.get("filters", {})}
    filters = q.get("filters", {})
    results: List[Dict[str, Any]] = []
    rejected = []
    for d in CATALOG:
        ok, why_not = apply_filters(d, filters)
        if not ok:
            rejected.append({"id": d["id"], "why": why_not})
            continue
        s, reasons = compute_score(d, filters, q)
        results.append({"item": d, "score": s, "reasons": reasons})
    results.sort(key=lambda x: x["score"], reverse=True)
    plan = {
        "hard_filters": filters,
        "ranking_weights": {**{"rating":0.3,"price":0.3,"eta":0.1,"pop":0.1,"dist":0.1,"lex":0.1}, **(q.get("weights") or {}), **((q.get("ranking_overrides") or {}).get("weights") or {})},
        "explain": "Se aplicaron filtros duros y luego orden ponderado. Boosts y penalizaciones consideradas.",
        "rejected_sample": rejected[:10]
    }
    if q.get("advisor_summary"):
        plan["advisor_summary"] = q.get("advisor_summary")
    if q.get("advisor_details"):
        plan["advisor_details"] = q.get("advisor_details")
    if q.get("scenario_tags"):
        plan["scenario_tags"] = q.get("scenario_tags")
    return {"results": results, "plan": plan}
