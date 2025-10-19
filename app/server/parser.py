
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


def parse_rating(text_norm: str, plan: List[str]):
    """
    Accepts:
      - "buen rating"
      - "rating mayor a 4,6" or "rating >= 4,6"
      - "rating 4,6" or "puntaje 4,6"
      - "4,6 o mas de rating"
    Uses comma or dot as decimal separator.
    """
    if "buen rating" in text_norm or "bien puntuado" in text_norm or "mejor valorado" in text_norm:
        plan.append("Calidad: rating_min=4.3")
        return 4.3

    patterns = [
        r"(?:rating|puntaje|puntuacion)\s*(?:mayor(?:\s*a)?|>=?)\s*([0-5](?:[.,]\d+)?)",
        r"(?:rating|puntaje|puntuacion)\s*([0-5](?:[.,]\d+)?)",
        r"\b([0-5](?:[.,]\d+)?)\b\s*(?:o\s*mas|para\s*arriba)\s*(?:de\s*(?:rating|puntaje|puntuacion))?"
    ]
    for pat in patterns:
        m = re.search(pat, text_norm)
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

def parse(text: str):
    plan = []
    tn = normalize(text)
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
    filters["rating_min"] = parse_rating(tn, plan)

    ranking_overrides = {
        "boost_tags": boost,
        "penalize_tags": penal,
        "weights": parse_weights(tn, plan)
    }
    return {
        "query": ParsedQuery(
            q=text,
            filters=ParseFilters(**filters),
            hints=hints,
            ranking_overrides=RankingOverrides(**ranking_overrides)
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
