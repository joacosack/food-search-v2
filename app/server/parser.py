
import json, re
from pathlib import Path
from typing import Dict, Any, List, Iterable, Optional
from copy import deepcopy
from .schema import ParsedQuery, ParseFilters, RankingOverrides
from . import llm

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "dictionaries"

def load_json(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))

CATEGORIES = load_json("categories.json")
INGREDIENTS = load_json("ingredients.json")
DIETS = load_json("diets.json")
ALLERGENS = load_json("allergens.json")
HEALTH = load_json("health.json")
INTENTS = load_json("intents.json")

NEIGHBORHOODS = [
    "Palermo","Belgrano","Colegiales","Recoleta","Chacarita","Villa Crespo","Almagro",
    "Caballito","Núñez","Boedo","San Telmo","Microcentro","Balvanera","Devoto","Saavedra",
    "Puerto Madero","Villa Urquiza","Flores","Parque Chas","Barracas","Parque Patricios"
]
CUISINES = [
    "Argentina","Parrilla","Italiana","Pizzería","Empanadas","Ensaladas","Wok","Árabe",
    "Japonesa","Mexicana","Hamburguesas","Vegana","Vegetariana","Sushi","Tacos","Sandwiches",
    "Bowls","Sopas","Postres","Heladería","Peruana","India","Thai","Mediterránea","Cafetería",
    "Mariscos","Pollo","Wraps","Poke","Veggie"
]

CATALOG_FACETS = {
    "categories": sorted(CATEGORIES.keys()),
    "diets": sorted(DIETS.keys()),
    "allergens": sorted(ALLERGENS.keys()),
    "health_tags": sorted(HEALTH["tags"].keys()),
    "neighborhoods": NEIGHBORHOODS,
    "cuisines": CUISINES,
    "ingredients": sorted(INGREDIENTS.keys()),
}

# Cargar nombres de restaurantes desde el catálogo para detectar coincidencias exactas en la consulta
CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
def get_restaurant_names():
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        names = sorted({ d["restaurant"]["name"] for d in data })
        return names
    except Exception:
        return []

RESTAURANT_NAMES = get_restaurant_names()

def load_catalog_metrics():
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"prices": [], "etas": [], "ratings": []}
    prices = sorted(d.get("price_ars", 0) for d in data)
    etas = sorted(d.get("restaurant", {}).get("eta_min", 0) for d in data)
    ratings = sorted(d.get("restaurant", {}).get("rating", 0.0) for d in data)
    return {"prices": prices, "etas": etas, "ratings": ratings}

CATALOG_METRICS = load_catalog_metrics()

def parse_restaurants(text_raw: str, plan: List[str]) -> List[str]:
    t = normalize_soft(text_raw)
    hits = []
    for rn in RESTAURANT_NAMES:
        rnn = normalize_soft(rn)
        if rnn and rnn in t:
            hits.append(rn)
    if hits:
        plan.append(f"Restaurantes detectados: {hits}")
    return hits


MEAL_MOMENTS = {
    "desayuno": ["desayuno","desayunos"],
    "almuerzo": ["almuerzo","almuerzos","almorzar"],
    "merienda": ["merienda","meriendas","merendar"],
    "cena": ["cena","cenas","cenar"],
    "postre": ["postre","postres"]
}

def normalize(s: str) -> str:
    s = s.lower()
    s = s.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("ñ","n")
    return re.sub(r"[^a-z0-9\s]", " ", s)

def normalize_soft(s: str) -> str:
    # Minusculas y sin tildes, pero conserva dígitos, espacios, punto y coma
    s = s.lower()
    s = s.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("ñ","n")
    s = re.sub(r"[^a-z0-9\s\.,]", " ", s)
    return s

def percentile_value(values: List[Any], pct: float):
    if not values:
        return None
    pct = max(0.0, min(1.0, pct))
    idx = int(len(values) * pct) - 1
    idx = max(0, min(len(values) - 1, idx))
    return values[idx]

def price_from_percentile(pct: float):
    return percentile_value(CATALOG_METRICS.get("prices", []), pct)

def eta_from_percentile(pct: float):
    return percentile_value(CATALOG_METRICS.get("etas", []), pct)

def rating_from_percentile(pct: float):
    return percentile_value(CATALOG_METRICS.get("ratings", []), pct)

def tighten_min_limit(current, new_value):
    if new_value is None:
        return current
    if current is None:
        return new_value
    return max(current, new_value)

def tighten_max_limit(current, new_value):
    if new_value is None:
        return current
    if current is None:
        return new_value
    return min(current, new_value)

def normalize_percentile_limit(limit):
    if isinstance(limit, str) and limit.startswith("p"):
        try:
            pct = int(limit[1:]) / 100.0
        except ValueError:
            return None
        return price_from_percentile(pct)
    if isinstance(limit, (int, float)):
        return float(limit)
    return None

def _as_list(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    if isinstance(values, Iterable):
        return [str(v) for v in values if v]
    return []

def _price_value(limit: Any) -> Optional[float]:
    if limit is None:
        return None
    if isinstance(limit, str):
        limit = limit.strip()
        if limit.lower().startswith("p"):
            return normalize_percentile_limit(limit.lower())
        try:
            return float(limit.replace(",", "."))
        except ValueError:
            return None
    if isinstance(limit, (int, float)):
        return float(limit)
    return None

def _numeric_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return None
    return None

def _merge_max_limit(current: Any, candidate: Any, converter) -> Any:
    cand_val = converter(candidate)
    if cand_val is None:
        return current
    current_val = converter(current)
    if current_val is None or cand_val < current_val:
        return candidate
    return current

def _merge_min_limit(current: Any, candidate: Any, converter) -> Any:
    cand_val = converter(candidate)
    if cand_val is None:
        return current
    current_val = converter(current)
    if current_val is None or cand_val > current_val:
        return candidate
    return current

def _merge_list_field(target: Dict[str, List[str]], key: str, addition: Any) -> bool:
    values = [str(v) for v in _as_list(addition) if v]
    if not values:
        return False
    target.setdefault(key, [])
    before = list(target[key])
    extend_unique_list(target[key], values)
    return target[key] != before

def _merge_into_list(target: List[str], addition: Any) -> bool:
    values = [str(v) for v in _as_list(addition) if v]
    if not values:
        return False
    before = list(target)
    extend_unique_list(target, values)
    return target != before

def parse_price(text_norm: str, plan: List[str]):
    PRICE_WORDS = {
        "ultra barato":"p15",
        "muy barato":"p20",
        "baratisimo":"p20",
        "barato":"p35",
        "economico":"p40",
        "caro":"p80",
        "premium":"p85"
    }
    for k, v in PRICE_WORDS.items():
        if k in text_norm:
            plan.append(f"Detectado precio {k} -> {v}")
            return v
    m = re.search(r"(hasta|<=|menos de|<)\s*(\d{3,6})", text_norm)
    if m:
        val = int(m.group(2))
        plan.append(f"Limite de precio detectado {val}")
        return val
    return None

def parse_eta(text_norm: str, plan: List[str]):
    if "rapido" in text_norm or "entrega rapida" in text_norm or "express" in text_norm:
        plan.append("Velocidad: eta_max=25")
        return 25
    return None


def parse_rating(text_raw: str, plan: List[str]):
    t = normalize_soft(text_raw)

    # atajos
    if "buen rating" in t or "bien puntuado" in t or "mejor valorado" in t:
        plan.append("Calidad: rating_min=4.3")
        return 4.3

    patterns = [
        r"(?:rating|puntaje|puntuacion)\s*(?:mayor(?:\s*a)?|>=?)\s*([0-5](?:[.,]\d+)?)",
        r"(?:rating|puntaje|puntuacion)\s*([0-5](?:[.,]\d+)?)",
        r"\b([0-5](?:[.,]\d+)?)\b\s*(?:o\s*mas|para\s*arriba)\s*(?:de\s*(?:rating|puntaje|puntuacion))?"
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            val = float(m.group(1).replace(",", "."))
            val = max(0.0, min(5.0, val))
            plan.append(f"Calidad: rating_min={val}")
            return val
    return None

def parse_category(text_norm: str, plan: List[str]):
    cats = []
    for cat, syns in CATEGORIES.items():
        for s in syns:
            s_norm = normalize(s)
            pattern = rf"\b{re.escape(s_norm)}\b"
            if re.search(pattern, text_norm):
                negative = re.search(
                    rf"(sin|evitar|alergia(?:s)?|intoleranc(?:ia|ias)|no\s+quiero)(?:\s+\w+){{0,5}}\s+{re.escape(s_norm)}",
                    text_norm,
                )
                if negative:
                    plan.append(f"Categoría omitida por contexto negativo: {cat}")
                    continue
                cats.append(cat)
                break
    if cats:
        plan.append(f"Categorias: {sorted(set(cats))}")
    return sorted(set(cats))

def parse_neighborhoods(text: str, plan: List[str]):
    selected = []
    t = normalize(text)
    for n in NEIGHBORHOODS:
        if re.search(rf"\b{re.escape(normalize(n))}\b", t):
            selected.append(n)
    if selected:
        plan.append(f"Barrios: {selected}")
    return selected


def parse_cuisines(text: str, plan: List[str]):
    selected = []
    t = normalize(text)
    for c in CUISINES:
        c_norm = normalize(c)
        if c in ["Vegana","Vegetariana"]:
            if re.search(rf"\bcocina\s+{re.escape(c_norm)}\b", t):
                selected.append(c)
        else:
            if re.search(rf"\b{re.escape(c_norm)}\b", t):
                negative = re.search(
                    rf"(sin|evitar|alergia(?:s)?|intoleranc(?:ia|ias)|no\s+quiero)(?:\s+\w+){{0,5}}\s+{re.escape(c_norm)}",
                    t,
                )
                if negative:
                    plan.append(f"Cocina omitida por contexto negativo: {c}")
                    continue
                selected.append(c)
    if selected:
        plan.append(f"Cocinas: {selected}")
    return selected


def extract_include_exclude(text_norm: str, plan: List[str]):
    include, exclude, allergens_ex = [], [], []

    # First: map "poca sal" or "sin sal" to low_sodium and prevent 'sal' as ingredient include
    low_sodium_hit = bool(re.search(r"\b(poca|baja)\s+sal\b", text_norm) or re.search(r"\bsin\s+sal\b", text_norm))

    # Build normalized synonym maps
    ing_map = {}
    for token, group in INGREDIENTS.items():
        for s in group["synonyms"]:
            ing_map[normalize(s)] = token
    allerg_map = {}
    for token, group in ALLERGENS.items():
        for s in group["synonyms"]:
            allerg_map[normalize(s)] = token

    def pat(syn):
        return rf"\b{re.escape(syn)}(?:s|es|ito|itos|ita|itas)?\b"

    negative_prefixes = [
        r"sin",
        r"ni",
        r"odio",
        r"odio\s+la",
        r"odio\s+el",
        r"no\s+quiero",
        r"evito",
        r"evitar",
        r"alergia",
        r"alergias",
        r"intolerancia",
        r"intolerancias",
        r"nada\s+de",
        r"nada\s+con",
    ]

    def in_negative_context(pattern: str) -> bool:
        for prefix in negative_prefixes:
            if re.search(rf"{prefix}(?:\s+\w+){{0,5}}\s+{pattern}", text_norm):
                return True
        return False

    for syn_norm, token in ing_map.items():
        token_pattern = pat(syn_norm)
        if in_negative_context(token_pattern):
            exclude.append(token)

    for syn_norm, token in allerg_map.items():
        token_pattern = pat(syn_norm)
        if in_negative_context(token_pattern):
            allergens_ex.append(token)

    # "con X"
    for syn_norm, token in ing_map.items():
        if re.search(rf"\bcon\s+{pat(syn_norm)}", text_norm):
            if not (low_sodium_hit and syn_norm == "sal"):
                include.append(token)

    # Solo incluir ingredientes que aparecen explícitamente con "con" o en contextos positivos
    # NO incluir ingredientes que aparecen en contextos de exclusión
    for syn_norm, token in ing_map.items():
        if syn_norm == "sal" and low_sodium_hit:
            continue
        # Solo incluir si aparece con "con" y no con "sin"
        if re.search(rf"\bcon\s+{pat(syn_norm)}", text_norm) and not re.search(rf"\bsin\s+{pat(syn_norm)}", text_norm):
            include.append(token)

    include = sorted(set(include))
    exclude = sorted(set(exclude))
    allergens_ex = sorted(set(allergens_ex))

    if include:
        plan.append(f"Incluir ingredientes: {include}")
    if exclude:
        plan.append(f"Excluir ingredientes: {exclude}")
    if allergens_ex:
        plan.append(f"Excluir alergenos: {allergens_ex}")
    return include, exclude, allergens_ex
def parse_diets(text_norm: str, plan: List[str]):
    must = []
    for dkey, dobj in DIETS.items():
        for s in dobj["synonyms"]:
            s_norm = normalize(s)
            if re.search(rf"\b{re.escape(s_norm)}\w*\b", text_norm):
                must.append(dkey)
                break
    if "apto celiacos" in text_norm or "apto celiaco" in text_norm or "sin gluten" in text_norm:
        if "gluten_free" not in must:
            must.append("gluten_free")
    if must:
        plan.append(f"Dietas requeridas: {sorted(set(must))}")
    return sorted(set(must))

def parse_health_and_intents(text_norm: str, plan: List[str]):
    health_any, hints, boost, penal = [], [], [], []
    for tag, syns in HEALTH["tags"].items():
        for s in syns:
            s_norm = normalize(s)
            if re.search(rf"\b{re.escape(s_norm)}\w*\b", text_norm):
                health_any.append(tag)
                break
    if "saludable" in text_norm or "saludables" in text_norm or re.search(r"\b(poca|baja)\s+sal\b", text_norm) or re.search(r"\bsin\s+sal\b", text_norm):
        if "no_fry" not in health_any:
            health_any.append("no_fry")
        if "low_sodium" not in health_any:
            health_any.append("low_sodium")
    if "no me caiga pesado" in text_norm or "mal de la panza" in text_norm or "liviano" in text_norm:
        for t in ["no_fry","grilled","baked","low_sodium"]:
            if t not in health_any: health_any.append(t)
        boost += ["soup","no_fry","grilled","baked","rice"]
        penal += ["fried","spicy","creamy","very_greasy"]
        hints.append("light_digest")
    if "porcion grande" in text_norm or "para compartir" in text_norm or "tengo hambre" in text_norm or "abundante" in text_norm:
        if "portion_large" not in boost: boost.append("portion_large")
        if "combos" not in boost: boost.append("combos")
        hints.append("portion_large")
    # category nudges from common nouns
    if re.search(r"\bcarne\b", text_norm):
        boost.append("parrilla")
    if re.search(r"\bpescado\b", text_norm):
        boost.append("sushi")
    if health_any:
        plan.append(f"Salud: {sorted(set(health_any))}")
    if boost:
        plan.append(f"Boost: {sorted(set(boost))}")
    if penal:
        plan.append(f"Penalizar: {sorted(set(penal))}")
    if hints:
        plan.append(f"Hints: {sorted(set(hints))}")
    return list(sorted(set(health_any))), list(sorted(set(hints))), list(sorted(set(boost))), list(sorted(set(penal)))

def parse_weights(text_norm: str, plan: List[str]):
    weights = {}
    if "buen rating" in text_norm:
        weights["rating"] = 0.35
    if "ultra barato" in text_norm:
        weights["price"] = 0.45
    return weights

def extend_unique_list(lst: List[str], values: List[str]) -> List[str]:
    existing = set(lst or [])
    for v in values:
        if v not in existing:
            lst.append(v)
            existing.add(v)
    return lst

def apply_conversation_scenarios(
    text: str,
    filters: Dict[str, Any],
    ranking_overrides: Dict[str, Any],
    hints: List[str],
    intent_tags: List[str],
    auto_constraints: List[str],
    plan: List[str],
):
    summaries: List[str] = []
    scenario_tags: List[str] = []
    text_soft = normalize_soft(text)

    def note(label: str, details: str):
        plan.append(f"Escenario conversacional: {label} -> {details}")

    # Escenario: cita romántica
    romantic_patterns = [
        r"cita\s+romant", r"salida\s+romant", r"plan\s+romant", r"con\s+mi\s+pareja", r"cena\s+romant"
    ]
    if any(re.search(pat, text_soft) for pat in romantic_patterns):
        scenario_tags.append("romantic_date")
        current_rating = filters.get("rating_min")
        tightened_rating = tighten_min_limit(current_rating, 4.4)
        if tightened_rating != current_rating:
            filters["rating_min"] = tightened_rating
            if "rating_min" not in auto_constraints:
                auto_constraints.append("rating_min")
        filters["available_only"] = True
        extend_unique_list(intent_tags, ["romantic_evening", "date_night"])
        extend_unique_list(hints, ["date", "special_evening"])
        extend_unique_list(ranking_overrides.setdefault("boost_tags", []), ["romantic", "date-night", "vino", "intimo"])
        weights = ranking_overrides.setdefault("weights", {})
        weights["rating"] = max(weights.get("rating", 0.3), 0.45)
        weights["lex"] = max(weights.get("lex", 0.1), 0.15)
        note("cita romántica", "priorizar lugares íntimos y con alto rating")
        summaries.append("Prioricé opciones con ambiente romántico, buen rating y etiquetas especiales de cita.")

    # Escenario: presupuesto ajustado
    budget_patterns = [
        r"no\s+tengo\s+mucha\s+plata", r"poco\s+presupuesto", r"barato\s+pero\s+rico", r"estoy\s+corto\s+de\s+plata"
    ]
    if any(re.search(pat, text_soft) for pat in budget_patterns):
        scenario_tags.append("budget_friendly")
        target_price = price_from_percentile(0.28)
        if target_price is None:
            target_price = 4500
        else:
            target_price = min(target_price, 4500)
        new_price_cap = tighten_max_limit(filters.get("price_max"), target_price)
        if new_price_cap != filters.get("price_max"):
            filters["price_max"] = new_price_cap
            if "price_max" not in auto_constraints:
                auto_constraints.append("price_max")
        extend_unique_list(intent_tags, ["budget_friendly"])
        extend_unique_list(ranking_overrides.setdefault("boost_tags", []), ["budget_friendly", "ahorro", "combo"])
        weights = ranking_overrides.setdefault("weights", {})
        weights["price"] = max(weights.get("price", 0.3), 0.45)
        weights["pop"] = max(weights.get("pop", 0.1), 0.12)
        note("presupuesto ajustado", "fijar tope de precio y dar peso extra a opciones económicas")
        summaries.append("Ajusté la búsqueda a opciones accesibles y destaqué platos marcados como económicos.")

    # Escenario: almuerzo rápido
    quick_patterns = [
        r"algo\s+rapido\s+para\s+almorzar", r"almuerzo\s+rapido", r"comer\s+rapido\s+al\s+mediodia", r"necesito\s+algo\s+express"
    ]
    if any(re.search(pat, text_soft) for pat in quick_patterns):
        scenario_tags.append("quick_lunch")
        target_eta = eta_from_percentile(0.35) or 20
        new_eta = tighten_max_limit(filters.get("eta_max"), target_eta)
        if new_eta != filters.get("eta_max"):
            filters["eta_max"] = new_eta
            if "eta_max" not in auto_constraints:
                auto_constraints.append("eta_max")
        filters["meal_moments_any"] = sorted(set((filters.get("meal_moments_any") or []) + ["almuerzo"]))
        extend_unique_list(intent_tags, ["quick_lunch"])
        extend_unique_list(ranking_overrides.setdefault("boost_tags", []), ["quick_lunch", "sandwich", "wrap", "express"])
        weights = ranking_overrides.setdefault("weights", {})
        weights["eta"] = max(weights.get("eta", 0.1), 0.22)
        weights["dist"] = max(weights.get("dist", 0.1), 0.12)
        main_cats = ["ensalada", "bowls", "wok", "platos principales", "parrilla", "pasta", "sandwich"]
        current_cats = filters.get("category_any") or []
        filtered = [c for c in current_cats if c != "postres"]
        filters["category_any"] = filtered or main_cats
        note("almuerzo rápido", "limitar tiempos de entrega, priorizar platos livianos y evitar postres.")
        summaries.append("Configuré filtros para almuerzos rápidos con entregas cortas y platos listos al paso.")

    gamer_patterns = [r"juntada", r"gamer", r"amigos", r"maraton\s+de\s+juego", r"maraton\s+de\s+series"]
    if any(re.search(pat, text_soft) for pat in gamer_patterns):
        scenario_tags.append("friends_gathering")
        extend_unique_list(intent_tags, ["friends_gathering", "movie_night"])
        extend_unique_list(ranking_overrides.setdefault("boost_tags", []), ["portion_large", "combos", "friends_gathering"])
        filters["meal_moments_any"] = sorted(set((filters.get("meal_moments_any") or []) + ["cena"]))
        main_cats = ["platos principales", "parrilla", "wok", "bowls", "ensalada", "pasta", "pizza", "sandwich", "combos", "burger"]
        current_cats = filters.get("category_any") or []
        filtered = [c for c in current_cats if c != "postres"]
        filters["category_any"] = filtered or main_cats
        note("plan con amigos", "priorizar platos abundantes y dejar los postres para pedidos explícitos.")
        summaries.append("Ajusté la búsqueda a platos principales abundantes y promociones pensadas para compartir con amigos.")

    family_patterns = [r"familia", r"familiar", r"chicos", r"nen(?:es|os)", r"hijos"]
    if any(re.search(pat, text_soft) for pat in family_patterns):
        scenario_tags.append("family_sharing")
        extend_unique_list(intent_tags, ["family_sharing"])
        extend_unique_list(ranking_overrides.setdefault("boost_tags", []), ["family_sharing", "combos"])
        filters["meal_moments_any"] = sorted(set((filters.get("meal_moments_any") or []) + ["cena"]))
        main_cats = ["platos principales", "parrilla", "bowls", "pasta", "pizza", "sandwich", "combos"]
        current_cats = filters.get("category_any") or []
        filtered = [c for c in current_cats if c != "postres"]
        filters["category_any"] = filtered or main_cats
        note("plan familiar", "destacar opciones rendidoras y aptas para compartir con chicos.")
        summaries.append("Configuré la búsqueda a platos principales abundantes pensados para compartir en familia.")

    # remover duplicados preservando orden
    seen = set()
    dedup_tags = []
    for tag in scenario_tags:
        if tag not in seen:
            dedup_tags.append(tag)
            seen.add(tag)
    return summaries, dedup_tags

def parse(text: str):
    plan = []
    tn = normalize(text)
    text_soft = normalize_soft(text)
    rest_hits = parse_restaurants(text, plan)
    filters = {
        "category_any": parse_category(tn, plan),
        "neighborhood_any": parse_neighborhoods(text, plan),
        "cuisines_any": parse_cuisines(text, plan),
        "restaurant_any": [],
        "ingredients_include": [],
        "ingredients_exclude": [],
        "ingredients_any": [],
        "diet_must": [],
        "allergens_exclude": [],
        "health_any": [],
        "intent_tags_any": [],
        "meal_moments_any": parse_meal_moments(tn, plan),
        "price_max": None,
        "eta_max": None,
        "rating_min": None,
        "available_only": True
    }
    filters_before_llm = deepcopy(filters)
    auto_constraints: List[str] = []
    inc, exc, allerg_exc = extract_include_exclude(tn, plan)
    filters["ingredients_include"] = inc
    filters["ingredients_exclude"] = exc
    filters["allergens_exclude"] = allerg_exc
    filters["diet_must"] = parse_diets(tn, plan)
    filters["health_any"], hints, boost, penal = parse_health_and_intents(tn, plan)
    filters["price_max"] = parse_price(tn, plan)
    filters["eta_max"] = parse_eta(tn, plan)
    filters["rating_min"] = parse_rating(text, plan)

    def add_ingredient_any(tokens: List[str]) -> None:
        if not tokens:
            return
        filters.setdefault("ingredients_any", [])
        extend_unique_list(filters["ingredients_any"], tokens)

    if "popeye" in tn:
        extend_unique_list(filters.setdefault("ingredients_include", []), ["espinaca"])
        plan.append("Referencia cultural: Popeye -> incluir espinaca.")
    if "bugs bunny" in tn or "conejo" in tn:
        add_ingredient_any(["zanahoria", "espinaca", "calabaza"])
        extend_unique_list(hints, ["veggie"])
        plan.append("Referencia cultural: Bugs Bunny -> priorizar zanahoria/espinaca/calabaza.")

    ranking_overrides = {
        "boost_tags": boost,
        "penalize_tags": penal,
        "weights": parse_weights(tn, plan)
    }

    intent_tags_local: List[str] = []
    scenario_summaries, scenario_tags = apply_conversation_scenarios(
        text, filters, ranking_overrides, hints, intent_tags_local, auto_constraints, plan
    )
    if intent_tags_local:
        filters["intent_tags_any"] = sorted(set((filters.get("intent_tags_any") or []) + intent_tags_local))
    advisor_summary = " ".join(scenario_summaries).strip() or None

    llm_headline = None
    llm_details = None
    llm_notes_accum: List[str] = []
    llm_info: Dict[str, Any]
    llm_provider = llm.provider_name()
    llm_enabled_flag = llm.llm_enabled()
    if llm_enabled_flag:
        llm_info = {"status": "pending", "provider": llm_provider or "desconocido"}
    else:
        llm_info = {"status": "disabled"}
        plan.append("LLM deshabilitado: se utilizan únicamente reglas locales.")

    enrichment: Dict[str, Any] = {}
    llm_raw_snapshot: Dict[str, Any] = {}
    llm_applied_filters: Dict[str, Any] = {}
    llm_overrides_applied: Dict[str, Any] = {}
    if llm_enabled_flag:
        try:
            enrichment = llm.enrich_query(
                text,
                {
                    "filters": filters,
                    "hints": hints,
                    "scenario_tags": scenario_tags,
                    "catalog_facets": CATALOG_FACETS,
                },
            ) or {}
        except llm.LLMError as exc:
            error_msg = f"Error de IA ({llm_provider or 'Groq'}): {str(exc)}"
            llm_info = {"status": "error", "provider": llm_provider or "Groq", "message": error_msg}
            plan.append(f"❌ {error_msg}")
        except Exception as exc:
            error_msg = f"Error inesperado de IA ({llm_provider or 'Groq'}): {str(exc)}"
            llm_info = {"status": "error", "provider": llm_provider or "Groq", "message": error_msg}
            plan.append(f"❌ {error_msg}")

    if enrichment:
        llm_raw_snapshot = deepcopy(enrichment)
        llm_info["status"] = "used"
        notes = enrichment.get("notes") or []
        if notes:
            llm_notes_accum.extend(notes)
        plan.append("LLM activado: se combinaron sugerencias con heurísticas.")
        llm_filters = enrichment.get("filters") or {}
        user_defined_constraints = {
            "price_max": filters.get("price_max") is not None,
            "eta_max": filters.get("eta_max") is not None,
            "rating_min": filters.get("rating_min") is not None,
        }
        llm_applied_filters = {}
        for key in {
            "category_any",
            "meal_moments_any",
            "neighborhood_any",
            "cuisines_any",
            "ingredients_include",
            "ingredients_exclude",
            "diet_must",
            "allergens_exclude",
            "health_any",
            "intent_tags_any",
            "ingredients_any",
        }:
            if key not in llm_filters:
                continue
            sanitized_values = _sanitize_llm_list_values(key, llm_filters[key])
            if not sanitized_values:
                continue
            existing_values = filters.get(key) or []
            allow_merge = bool(existing_values) or key in {
                "intent_tags_any",
                "ingredients_include",
                "ingredients_exclude",
                "diet_must",
                "allergens_exclude",
                "health_any",
            }
            if not allow_merge:
                continue
            before = list(existing_values)
            filters.setdefault(key, [])
            extend_unique_list(filters[key], sanitized_values)
            if filters[key] != before:
                llm_applied_filters[key] = filters[key]
        if "price_max" in llm_filters and user_defined_constraints.get("price_max"):
            merged = _merge_max_limit(filters.get("price_max"), llm_filters["price_max"], _price_value)
            if merged != filters.get("price_max"):
                filters["price_max"] = merged
                applied_filters["price_max"] = filters["price_max"]
        if "eta_max" in llm_filters and user_defined_constraints.get("eta_max"):
            merged = _merge_max_limit(filters.get("eta_max"), llm_filters["eta_max"], _numeric_value)
            if merged != filters.get("eta_max"):
                filters["eta_max"] = merged
                applied_filters["eta_max"] = filters["eta_max"]
        if "rating_min" in llm_filters and user_defined_constraints.get("rating_min"):
            merged = _merge_min_limit(filters.get("rating_min"), llm_filters["rating_min"], _numeric_value)
            if merged != filters.get("rating_min"):
                filters["rating_min"] = merged
                applied_filters["rating_min"] = filters["rating_min"]
        if "available_only" in llm_filters:
            new_val = bool(llm_filters["available_only"])
            if new_val != filters.get("available_only", True):
                filters["available_only"] = new_val
                llm_applied_filters["available_only"] = filters["available_only"]
        if llm_filters:
            plan.append(f"LLM filtros sugeridos (raw): {json.dumps(llm_filters, ensure_ascii=False)}")
        if llm_applied_filters:
            plan.append(f"LLM filtros combinados: {json.dumps(llm_applied_filters, ensure_ascii=False)}")

        overrides = enrichment.get("ranking_overrides") or {}
        llm_overrides_applied = {}
        if overrides:
            if _merge_list_field(ranking_overrides, "boost_tags", overrides.get("boost_tags")):
                llm_overrides_applied["boost_tags"] = ranking_overrides["boost_tags"]
            if _merge_list_field(ranking_overrides, "penalize_tags", overrides.get("penalize_tags")):
                llm_overrides_applied["penalize_tags"] = ranking_overrides["penalize_tags"]
            weight_updates = overrides.get("weights") or {}
            if isinstance(weight_updates, dict) and weight_updates:
                ranking_overrides.setdefault("weights", {})
                before = dict(ranking_overrides["weights"])
                for wk, wv in weight_updates.items():
                    val = _numeric_value(wv)
                    if val is not None:
                        ranking_overrides["weights"][wk] = val
                if ranking_overrides["weights"] != before:
                    llm_overrides_applied["weights"] = ranking_overrides["weights"]
        if overrides:
            plan.append(f"LLM overrides sugeridos (raw): {json.dumps(overrides, ensure_ascii=False)}")
        if llm_overrides_applied:
            plan.append(f"LLM ranking overrides: {json.dumps(llm_overrides_applied, ensure_ascii=False)}")

        if _merge_into_list(hints, enrichment.get("hints")):
            plan.append(f"LLM hints añadidos: {json.dumps(hints, ensure_ascii=False)}")
        if _merge_into_list(scenario_tags, enrichment.get("scenario_tags")):
            plan.append(f"LLM escenarios extendidos: {json.dumps(scenario_tags, ensure_ascii=False)}")

        llm_headline = enrichment.get("headline")
        llm_details = enrichment.get("details")
        for note in enrichment.get("notes", []) or []:
            plan.append(f"LLM nota: {note}")
        llm_notes_accum.extend(enrichment.get("notes", []) or [])

        strategies = enrichment.get("strategies") or []
        for strategy in strategies:
            summary = strategy.get("summary") or strategy.get("details") or strategy.get("explanation")
            if summary:
                llm_notes_accum.append(summary)
            strategy_filters = strategy.get("filters") or {}
            strategy_overrides = strategy.get("ranking_overrides") or {}
            strategy_hints = strategy.get("hints") or []
            if strategy_filters.get("intent_tags_any"):
                extend_unique_list(filters["intent_tags_any"], [str(v) for v in _as_list(strategy_filters["intent_tags_any"])])
            if strategy_hints:
                extend_unique_list(hints, [str(v) for v in _as_list(strategy_hints)])
            if strategy_overrides.get("boost_tags"):
                _merge_list_field(ranking_overrides, "boost_tags", strategy_overrides.get("boost_tags"))
            if strategy_overrides.get("penalize_tags"):
                _merge_list_field(ranking_overrides, "penalize_tags", strategy_overrides.get("penalize_tags"))
            if isinstance(strategy_overrides.get("weights"), dict):
                ranking_overrides.setdefault("weights", {})
                for wk, wv in strategy_overrides["weights"].items():
                    val = _numeric_value(wv)
                    if val is not None:
                        ranking_overrides["weights"][wk] = val
    elif llm_enabled_flag and llm_info.get("status") not in {"error"}:
        llm_info["status"] = "no_data"

    def _enforce_course_preferences() -> None:
        nonlocal filters
        categories = filters.get("category_any") or []
        dessert_terms = re.compile(r"\b(postre|postres|dulce|helado|dessert)\b")
        wants_dessert = bool(dessert_terms.search(text_soft))
        meal_terms = re.compile(r"\b(almuerzo|almorzar|cena|cenar|comida|plato|juntada|gamer|oficina|trabajo|express|rapido|almuerz[ao]|cenit[oa])\b")
        wants_meal = bool(meal_terms.search(text_soft) or filters.get("meal_moments_any"))
        savory_defaults = [
            "platos principales",
            "parrilla",
            "wok",
            "bowls",
            "ensalada",
            "pasta",
            "pizza",
            "sandwich",
            "combos",
            "empanadas",
            "burger",
            "sopas",
        ]

        if wants_dessert and not wants_meal:
            if not categories or categories == ["postres"]:
                filters["category_any"] = ["postres"]
                plan.append("Categoría inferida: postres.")
            return

        if categories:
            filtered = [c for c in categories if c != "postres"]
            if wants_meal and len(filtered) != len(categories):
                filters["category_any"] = filtered or savory_defaults
                plan.append("Se removieron postres para priorizar platos principales.")
        elif wants_meal:
            filters["category_any"] = savory_defaults
            plan.append("Categorías inferidas (plato principal): platos principales, parrilla, wok, bowls, ensalada, pasta, pizza.")

    _enforce_course_preferences()

    extra_meal_tags: List[str] = []
    meal_any = filters.get("meal_moments_any") or []
    if meal_any:
        valid_meals = set(MEAL_MOMENTS.keys())
        kept = []
        for token in meal_any:
            if token in valid_meals:
                kept.append(token)
            else:
                extra_meal_tags.append(token)
        filters["meal_moments_any"] = kept
    if extra_meal_tags:
        extend_unique_list(filters["intent_tags_any"], extra_meal_tags)
        plan.append(f"Tokens de escenario convertidos a tags de intención: {extra_meal_tags}")
    if filters.get("intent_tags_any"):
        filters["intent_tags_any"] = sorted(set(filters["intent_tags_any"]))

    catalog_min_price = None
    prices_snapshot = CATALOG_METRICS.get("prices") or []
    if prices_snapshot:
        catalog_min_price = prices_snapshot[0]
    price_filter_value = _numeric_value(filters.get("price_max"))
    if catalog_min_price is not None and price_filter_value is not None and price_filter_value < catalog_min_price:
        filters["price_max"] = catalog_min_price
        plan.append(f"Precio máximo ajustado al mínimo disponible del catálogo ({catalog_min_price}).")

    advisor_parts = []
    if llm_headline:
        advisor_parts.append(llm_headline)
    if advisor_summary and advisor_summary not in advisor_parts:
        advisor_parts.append(advisor_summary)
    if llm_details:
        advisor_parts.append(llm_details)
    combined_advisor = "\n\n".join([p for p in advisor_parts if p]).strip() or None

    if rest_hits:
        # Si el nombre de restaurante contiene "wok", no generes categoría/cocina por esa palabra
        joined = " ".join(rest_hits).lower()
        if "wok" in joined:
            filters["category_any"] = [c for c in (filters.get("category_any") or []) if c != "wok"]
            filters["cuisines_any"] = [c for c in (filters.get("cuisines_any") or []) if c.lower() != "wok"]
        filters["restaurant_any"] = rest_hits
    if llm_notes_accum:
        dedup_notes = list(dict.fromkeys(llm_notes_accum))
        llm_info["notes"] = dedup_notes

    final_filters_model = ParseFilters(**filters)
    metadata = {
        "llm": llm_info,
        "auto_constraints": auto_constraints,
        "restaurant_hits": rest_hits,
        "llm_notes": list(dict.fromkeys(llm_notes_accum)) if llm_notes_accum else [],
        "llm_raw": llm_raw_snapshot or None,
        "llm_filters_base": filters_before_llm,
        "llm_filters_applied": llm_applied_filters or {},
        "llm_overrides_applied": llm_overrides_applied or {},
        "llm_filters_final": final_filters_model.dict(),
    }
    return {
        "query": ParsedQuery(
            q=text,
            filters=final_filters_model,
            hints=hints,
            ranking_overrides=RankingOverrides(**ranking_overrides),
            advisor_summary=combined_advisor,
            scenario_tags=scenario_tags,
            metadata=metadata,
        ).dict(),
        "plan": plan,
        "status": metadata
    }

def parse_meal_moments(text_norm: str, plan: List[str]):
    mm = []
    for tag, syns in MEAL_MOMENTS.items():
        for s in syns:
            if re.search(rf"\b{re.escape(s)}\b", text_norm):
                mm.append(tag)
                break
    if mm:
        plan.append(f"Meal moments: {sorted(set(mm))}")
    extra = []
    if "oficina" in text_norm or "trabajo" in text_norm or "contra reloj" in text_norm:
        extra.append("almuerzo")
    if "cena" in text_norm or "noche" in text_norm:
        extra.append("cena")
    if extra:
        combined = sorted(set(mm + extra))
        plan.append(f"Meal moments inferidos: {combined}")
        return combined
    return sorted(set(mm))
def _build_synonym_lookup(source: Dict[str, Any]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for canonical, data in source.items():
        tokens = [canonical]
        if isinstance(data, dict):
            tokens.extend(data.get("synonyms") or [])
        for token in tokens:
            norm = normalize(token)
            if norm:
                lookup[norm] = canonical
    return lookup


INGREDIENT_LOOKUP = _build_synonym_lookup(INGREDIENTS)
ALLERGEN_LOOKUP = _build_synonym_lookup(ALLERGENS)
DIET_LOOKUP = _build_synonym_lookup(DIETS)
HEALTH_LOOKUP = _build_synonym_lookup(HEALTH.get("tags", {}))
def _sanitize_llm_list_values(key: str, values: Any) -> List[str]:
    raw_values = [v for v in _as_list(values) if v]
    if not raw_values:
        return []

    def canon_from_lookup(token: str, lookup: Dict[str, str]) -> Optional[str]:
        norm = normalize(token)
        if not norm:
            return None
        return lookup.get(norm)

    if key in {"ingredients_include", "ingredients_exclude"}:
        sanitized = []
        for token in raw_values:
            canonical = canon_from_lookup(token, INGREDIENT_LOOKUP)
            if canonical:
                sanitized.append(canonical)
        return sanitized
    if key == "diet_must":
        sanitized = []
        for token in raw_values:
            canonical = canon_from_lookup(token, DIET_LOOKUP)
            if canonical:
                sanitized.append(canonical)
        return sanitized
    if key == "allergens_exclude":
        sanitized = []
        for token in raw_values:
            canonical = canon_from_lookup(token, ALLERGEN_LOOKUP)
            if canonical:
                sanitized.append(canonical)
        return sanitized
    if key == "health_any":
        sanitized = []
        for token in raw_values:
            canonical = canon_from_lookup(token, HEALTH_LOOKUP)
            if canonical:
                sanitized.append(canonical)
        return sanitized
    return [str(v) for v in raw_values if v]
