
import json, re
from pathlib import Path
from typing import Dict, Any, List
from .schema import ParsedQuery, ParseFilters, RankingOverrides

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
    "Caballito","Núñez","Boedo","San Telmo","Microcentro","Balvanera","Devoto","Saavedra"
]
CUISINES = ["Argentina","Parrilla","Italiana","Pizzería","Empanadas","Ensaladas","Wok","Árabe","Japonesa","Mexicana","Hamburguesas","Vegana","Vegetariana","Sushi","Tacos","Sandwiches","Bowls","Sopas","Postres"]

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
            if re.search(rf"\b{re.escape(s_norm)}\b", text_norm):
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

    # "sin X"
    for syn_norm, token in ing_map.items():
        if re.search(rf"\bsin\s+{pat(syn_norm)}", text_norm):
            exclude.append(token)
    for syn_norm, token in allerg_map.items():
        if re.search(rf"\bsin\s+{pat(syn_norm)}", text_norm):
            allergens_ex.append(token)

    # "con X"
    for syn_norm, token in ing_map.items():
        if re.search(rf"\bcon\s+{pat(syn_norm)}", text_norm):
            if not (low_sodium_hit and syn_norm == "sal"):
                include.append(token)

    # Bare mentions as soft include if not excluded
    for syn_norm, token in ing_map.items():
        if syn_norm == "sal" and low_sodium_hit:
            continue
        if re.search(pat(syn_norm), text_norm) and not re.search(rf"\bsin\s+{pat(syn_norm)}", text_norm):
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

def apply_conversation_scenarios(text: str, filters: Dict[str, Any], ranking_overrides: Dict[str, Any], hints: List[str], plan: List[str]):
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
        filters["rating_min"] = tighten_min_limit(filters.get("rating_min"), 4.4)
        filters["available_only"] = True
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
        current = normalize_percentile_limit(filters.get("price_max"))
        filters["price_max"] = tighten_max_limit(current, target_price)
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
        filters["eta_max"] = tighten_max_limit(filters.get("eta_max"), target_eta)
        filters["meal_moments_any"] = sorted(set((filters.get("meal_moments_any") or []) + ["almuerzo"]))
        extend_unique_list(ranking_overrides.setdefault("boost_tags", []), ["quick_lunch", "sandwich", "wrap", "express"])
        weights = ranking_overrides.setdefault("weights", {})
        weights["eta"] = max(weights.get("eta", 0.1), 0.22)
        weights["dist"] = max(weights.get("dist", 0.1), 0.12)
        note("almuerzo rápido", "limitar tiempos de entrega y priorizar formatos express")
        summaries.append("Configuré filtros para almuerzos rápidos con entregas cortas y platos listos al paso.")

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
    rest_hits = parse_restaurants(text, plan)
    filters = {
        "category_any": parse_category(tn, plan),
        "neighborhood_any": parse_neighborhoods(text, plan),
        "cuisines_any": parse_cuisines(text, plan),
        "ingredients_include": [],
        "ingredients_exclude": [],
        "diet_must": [],
        "allergens_exclude": [],
        "health_any": [],
        "meal_moments_any": parse_meal_moments(tn, plan),
        "price_max": None,
        "eta_max": None,
        "rating_min": None,
        "available_only": True
    }
    inc, exc, allerg_exc = extract_include_exclude(tn, plan)
    filters["ingredients_include"] = inc
    filters["ingredients_exclude"] = exc
    filters["allergens_exclude"] = allerg_exc
    filters["diet_must"] = parse_diets(tn, plan)
    filters["health_any"], hints, boost, penal = parse_health_and_intents(tn, plan)
    filters["price_max"] = parse_price(tn, plan)
    filters["eta_max"] = parse_eta(tn, plan)
    filters["rating_min"] = parse_rating(text, plan)

    ranking_overrides = {
        "boost_tags": boost,
        "penalize_tags": penal,
        "weights": parse_weights(tn, plan)
    }

    scenario_summaries, scenario_tags = apply_conversation_scenarios(text, filters, ranking_overrides, hints, plan)
    advisor_summary = " ".join(scenario_summaries).strip() or None
    if rest_hits:
        # Si el nombre de restaurante contiene "wok", no generes categoría/cocina por esa palabra
        joined = " ".join(rest_hits).lower()
        if "wok" in joined:
            filters["category_any"] = [c for c in (filters.get("category_any") or []) if c != "wok"]
            filters["cuisines_any"] = [c for c in (filters.get("cuisines_any") or []) if c.lower() != "wok"]
    return {
        "query": ParsedQuery(
            q=text,
            filters=ParseFilters(**filters),
            hints=hints,
            ranking_overrides=RankingOverrides(**ranking_overrides),
            advisor_summary=advisor_summary,
            scenario_tags=scenario_tags
        ).dict(),
        "plan": plan
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
    return sorted(set(mm))
