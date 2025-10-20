
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

ROMANTIC_CATEGORIES = {"pasta", "sushi", "parrilla", "wok", "postres"}
FRIENDS_CATEGORIES = {"pizza", "hamburguesas", "tacos", "sandwiches", "empanadas"}
FAMILY_CATEGORIES = {"parrilla", "pasta", "sopas", "bowls"}
HEALTH_CATEGORIES = {"ensaladas", "bowls", "wok"}


def augment_catalog_intents() -> None:
    for dish in CATALOG:
        tags = set(dish.get("intent_tags") or dish.get("experience_tags") or [])
        tags.add("delivery_dining")
        categories = {c.lower() for c in dish.get("categories", [])}
        cuisine = _norm_str(dish.get("restaurant", {}).get("cuisines", ""))
        rating = dish.get("restaurant", {}).get("rating", 0)
        price = dish.get("price_ars", 0)
        eta = dish.get("restaurant", {}).get("eta_min", 60)
        health_tags = set(_norm_str(t) for t in dish.get("health_tags", []))

        if rating >= 4.4 and (categories & ROMANTIC_CATEGORIES or cuisine in {"italiana", "sushi", "parrilla"}):
            tags.update({"romantic_evening", "date_night"})
        if categories & FRIENDS_CATEGORIES:
            tags.update({"friends_gathering", "movie_night"})
        if categories & FAMILY_CATEGORIES:
            tags.add("family_sharing")
        if categories & HEALTH_CATEGORIES or health_tags & {"no_fry", "low_sodium"}:
            tags.add("healthy_choice")
        if price <= 6000:
            tags.add("budget_friendly")
        if eta <= 25:
            tags.update({"express_delivery", "quick_lunch"})
        if rating >= 4.7:
            tags.add("top_rated")
        if "postres" in categories:
            tags.add("sweet_treat")

        dish["intent_tags"] = sorted(tags)


augment_catalog_intents()

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

BASE_WEIGHTS = {"rating":0.25,"price":0.2,"eta":0.1,"pop":0.1,"dist":0.1,"lex":0.1,"promo":0.1,"fee":0.05}

def build_indexes():
    prices = [d["price_ars"] for d in CATALOG]
    etas = [d["restaurant"]["eta_min"] for d in CATALOG]
    ratings = [d["restaurant"]["rating"] for d in CATALOG]
    fees = [d.get("delivery_fee", 0) for d in CATALOG]
    discounts = [d.get("discount_pct", 0) for d in CATALOG]
    return {
        "price_min": min(prices), "price_max": max(prices),
        "eta_min": min(etas), "eta_max": max(etas),
        "rating_min": min(ratings), "rating_max": max(ratings),
        "fee_min": min(fees), "fee_max": max(fees),
        "discount_min": min(discounts), "discount_max": max(discounts),
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
    intent_any = f.get("intent_tags_any") or []
    if intent_any:
        dish_intents = d.get("intent_tags") or d.get("experience_tags") or []
        if not any(tag in dish_intents for tag in intent_any):
            return False, [f"No coincide intención {intent_any}"]
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
    eta_value = min(
        d.get("delivery_eta_min", float("inf")),
        d["restaurant"].get("eta_min", float("inf"))
    )
    if em is not None and eta_value > em:
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
    weights = dict(BASE_WEIGHTS)
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
    discount = d.get("discount_pct", 0)
    promo_n = norm(discount, IDX["discount_min"], IDX["discount_max"])
    fee = d.get("delivery_fee", IDX["fee_max"])
    fee_n = norm(fee, IDX["fee_min"], IDX["fee_max"])
    restaurant_hits = set((q.get("metadata") or {}).get("restaurant_hits") or [])
    score = (
        weights["rating"] * rating_n +
        weights["price"] * (1 - price_n) +
        weights["eta"]   * (1 - eta_n) +
        weights["pop"]   * pop_n +
        weights["dist"]  * dist_n +
        weights["lex"]   * lex_n +
        weights["promo"] * promo_n +
        weights["fee"]   * (1 - fee_n)
    )
    reasons = [
        f"rating:{rating_n:.2f}",
        f"price_inv:{1-price_n:.2f}",
        f"eta_inv:{1-eta_n:.2f}",
        f"pop:{pop_n:.2f}",
        f"dist:{dist_n:.2f}",
        f"lex:{lex_n:.2f}",
        f"promo:{promo_n:.2f}",
        f"fee_inv:{1-fee_n:.2f}"
    ]
    if restaurant_hits:
        rest_name = d.get("restaurant", {}).get("name")
        if rest_name in restaurant_hits:
            score += 0.4
            reasons.append("rest_hit")
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

def _effective_weights_snapshot(query: Dict[str, Any]) -> Dict[str, float]:
    weights = dict(BASE_WEIGHTS)
    weights.update(query.get("weights") or {})
    ro_weights = (query.get("ranking_overrides") or {}).get("weights") or {}
    weights.update(ro_weights)
    return weights


def _run_single_search(query: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    filters = query.get("filters", {}) or {}
    results: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for d in CATALOG:
        ok, why_not = apply_filters(d, filters)
        if not ok:
            rejected.append({"id": d["id"], "why": why_not})
            continue
        s, reasons = compute_score(d, filters, query)
        results.append({"item": d, "score": s, "reasons": reasons})
    results.sort(key=lambda x: x["score"], reverse=True)
    plan = {
        "hard_filters": filters,
        "ranking_weights": _effective_weights_snapshot(query),
        "explain": "Se aplicaron filtros duros y luego orden ponderado. Boosts y penalizaciones consideradas.",
        "rejected_sample": rejected[:10]
    }
    if query.get("advisor_summary"):
        plan["advisor_summary"] = query.get("advisor_summary")
    if query.get("scenario_tags"):
        plan["scenario_tags"] = query.get("scenario_tags")
    return results, rejected, plan


def search(req: Dict[str, Any]) -> Dict[str, Any]:
    q = req.get("query") or {"filters": req.get("filters", {})}
    results, rejected, plan = _run_single_search(q)
    relaxations: List[str] = []
    if not results:
        relaxed_query = json.loads(json.dumps(q, ensure_ascii=False))
        filters_rel = relaxed_query.get("filters", {}) or {}
        metadata_rel = relaxed_query.setdefault("metadata", {})
        auto = set(metadata_rel.get("auto_constraints") or [])

        def relax_numeric(field: str, label: str):
            nonlocal results, rejected, plan
            if filters_rel.get(field) is None or field not in auto:
                return False
            previous = filters_rel.get(field)
            filters_rel[field] = None
            relaxations.append(f"Se quitó {label} automático ({previous}).")
            results, rejected, plan = _run_single_search(relaxed_query)
            return bool(results)

        def relax_list(field: str, label: str):
            nonlocal results, rejected, plan
            if not (filters_rel.get(field) or []):
                return False
            previous = list(filters_rel.get(field) or [])
            filters_rel[field] = []
            relaxations.append(f"Se ignoró {label}: {previous}.")
            results, rejected, plan = _run_single_search(relaxed_query)
            return bool(results)

        if relax_numeric("rating_min", "el mínimo de rating sugerido"):
            pass
        elif relax_numeric("eta_max", "el tope de entrega sugerido"):
            pass
        elif relax_numeric("price_max", "el tope de precio sugerido"):
            pass
        else:
            relaxed = relax_list("health_any", "los requisitos de salud sugeridos")
            if not relaxed:
                relax_list("intent_tags_any", "los tags de intención sugeridos")

        if relaxations:
            plan.setdefault("relaxed_filters", relaxations)
            q = relaxed_query
    metadata = q.get("metadata") or {}
    if metadata.get("llm"):
        plan["llm_status"] = metadata["llm"]
    if metadata.get("llm_notes"):
        if not isinstance(plan.get("llm_status"), dict):
            plan["llm_status"] = metadata.get("llm", {})
        if isinstance(plan.get("llm_status"), dict):
            existing_notes = plan["llm_status"].get("notes") or []
            if not existing_notes:
                plan["llm_status"]["notes"] = metadata["llm_notes"]
    return {"results": results, "plan": plan}
