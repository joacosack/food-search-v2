import { CATALOG } from "./data/catalog.js";
import { CATEGORIES, INGREDIENTS, DIETS, ALLERGENS, HEALTH } from "./data/dictionaries.js";

const APP_VERSION = "v2.0.0";

function stripAccents(text = "") {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ñ/g, "n");
}

function normalize(text = "") {
  return stripAccents(text.toLowerCase())
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeSoft(text = "") {
  return stripAccents(text.toLowerCase())
    .replace(/[^a-z0-9\s\.,]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normBasic(text = "") {
  return stripAccents(String(text || "").toLowerCase());
}

function wordSet(text = "") {
  return new Set((text.match(/\w+/g) || []).map((w) => w));
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const RESTAURANT_NAMES = Array.from(
  new Set(CATALOG.map((item) => item.restaurant?.name || ""))
)
  .filter(Boolean)
  .sort();

function parseRestaurants(textRaw, plan) {
  const hits = [];
  const normalizedInput = normBasic(textRaw || "");
  RESTAURANT_NAMES.forEach((name) => {
    const normName = normBasic(name);
    if (normName && normalizedInput.includes(normName)) {
      hits.push(name);
    }
  });
  if (hits.length) {
    plan.push(`Restaurantes detectados: ${JSON.stringify(hits)}`);
  }
  return hits;
}

const MEAL_MOMENTS = {
  desayuno: ["desayuno", "desayunos"],
  almuerzo: ["almuerzo", "almuerzos", "almorzar"],
  merienda: ["merienda", "meriendas", "merendar"],
  cena: ["cena", "cenas", "cenar"],
  postre: ["postre", "postres"],
};

const NEIGHBORHOODS = [
  "Palermo",
  "Belgrano",
  "Colegiales",
  "Recoleta",
  "Chacarita",
  "Villa Crespo",
  "Almagro",
  "Caballito",
  "Núñez",
  "Boedo",
  "San Telmo",
  "Microcentro",
  "Balvanera",
  "Devoto",
  "Saavedra",
];

const CUISINES = [
  "Argentina",
  "Parrilla",
  "Italiana",
  "Pizzería",
  "Empanadas",
  "Ensaladas",
  "Wok",
  "Árabe",
  "Japonesa",
  "Mexicana",
  "Hamburguesas",
  "Vegana",
  "Vegetariana",
  "Sushi",
  "Tacos",
  "Sandwiches",
  "Bowls",
  "Sopas",
  "Postres",
];

function parsePrice(textNorm, plan) {
  const PRICE_WORDS = {
    "ultra barato": "p15",
    "muy barato": "p20",
    baratisimo: "p20",
    barato: "p35",
    economico: "p40",
    caro: "p80",
    premium: "p85",
  };
  for (const [keyword, value] of Object.entries(PRICE_WORDS)) {
    if (textNorm.includes(keyword)) {
      plan.push(`Detectado precio ${keyword} -> ${value}`);
      return value;
    }
  }
  const match = textNorm.match(/(hasta|<=|menos de|<)\s*(\d{3,6})/);
  if (match) {
    const val = parseInt(match[2], 10);
    plan.push(`Limite de precio detectado ${val}`);
    return val;
  }
  return null;
}

function parseEta(textNorm, plan) {
  if (
    textNorm.includes("rapido") ||
    textNorm.includes("entrega rapida") ||
    textNorm.includes("express")
  ) {
    plan.push("Velocidad: eta_max=25");
    return 25;
  }
  return null;
}

function parseRating(textRaw, plan) {
  const t = normalizeSoft(textRaw || "");
  if (t.includes("buen rating") || t.includes("bien puntuado") || t.includes("mejor valorado")) {
    plan.push("Calidad: rating_min=4.3");
    return 4.3;
  }
  const patterns = [
    /(?:rating|puntaje|puntuacion)\s*(?:mayor(?:\s*a)?|>=?)\s*([0-5](?:[.,]\d+)?)/,
    /(?:rating|puntaje|puntuacion)\s*([0-5](?:[.,]\d+)?)/,
    /\b([0-5](?:[.,]\d+)?)\b\s*(?:o\s*mas|para\s*arriba)\s*(?:de\s*(?:rating|puntaje|puntuacion))?/,
  ];
  for (const pattern of patterns) {
    const match = t.match(pattern);
    if (match) {
      const val = Math.max(0, Math.min(5, parseFloat(match[1].replace(",", "."))));
      plan.push(`Calidad: rating_min=${val}`);
      return val;
    }
  }
  return null;
}

function parseCategory(textNorm, plan) {
  const cats = [];
  for (const [cat, syns] of Object.entries(CATEGORIES)) {
    for (const syn of syns) {
      const normalizedSyn = normalize(syn);
      if (!normalizedSyn) continue;
      const regex = new RegExp(`\\b${escapeRegex(normalizedSyn)}\\b`, "i");
      if (regex.test(textNorm)) {
        cats.push(cat);
        break;
      }
    }
  }
  const unique = Array.from(new Set(cats)).sort();
  if (unique.length) {
    plan.push(`Categorias: ${JSON.stringify(unique)}`);
  }
  return unique;
}

function parseNeighborhoods(textRaw, plan) {
  const selected = [];
  const textNorm = normalize(textRaw || "");
  NEIGHBORHOODS.forEach((n) => {
    const nNorm = normalize(n);
    if (!nNorm) return;
    const regex = new RegExp(`\\b${escapeRegex(nNorm)}\\b`, "i");
    if (regex.test(textNorm)) {
      selected.push(n);
    }
  });
  if (selected.length) {
    plan.push(`Barrios: ${JSON.stringify(selected)}`);
  }
  return selected;
}

function parseCuisines(textRaw, plan) {
  const selected = [];
  const textNorm = normalize(textRaw || "");
  CUISINES.forEach((c) => {
    const cNorm = normalize(c);
    if (!cNorm) return;
    if (c === "Vegana" || c === "Vegetariana") {
      const regex = new RegExp(`\\bcocina\\s+${escapeRegex(cNorm)}\\b`, "i");
      if (regex.test(textNorm)) {
        selected.push(c);
      }
    } else {
      const regex = new RegExp(`\\b${escapeRegex(cNorm)}\\b`, "i");
      if (regex.test(textNorm)) {
        selected.push(c);
      }
    }
  });
  if (selected.length) {
    plan.push(`Cocinas: ${JSON.stringify(selected)}`);
  }
  return selected;
}

function parseMealMoments(textNorm, plan) {
  const mm = [];
  for (const [tag, syns] of Object.entries(MEAL_MOMENTS)) {
    for (const syn of syns) {
      const regex = new RegExp(`\\b${escapeRegex(syn)}\\b`, "i");
      if (regex.test(textNorm)) {
        mm.push(tag);
        break;
      }
    }
  }
  const unique = Array.from(new Set(mm)).sort();
  if (unique.length) {
    plan.push(`Meal moments: ${JSON.stringify(unique)}`);
  }
  return unique;
}

const INGREDIENT_SYNONYM_MAP = (() => {
  const mapping = new Map();
  for (const [canonical, obj] of Object.entries(INGREDIENTS)) {
    const canonNorm = normBasic(canonical);
    if (canonNorm && !mapping.has(canonNorm)) {
      mapping.set(canonNorm, canonical);
    }
    (obj.synonyms || []).forEach((syn) => {
      const normSyn = normBasic(syn);
      if (normSyn && !mapping.has(normSyn)) {
        mapping.set(normSyn, canonical);
      }
    });
  }
  return mapping;
})();

const INGREDIENT_GROUPS = (() => {
  const groups = new Map();
  for (const [canonical, obj] of Object.entries(INGREDIENTS)) {
    const normalized = new Set();
    normalized.add(normBasic(canonical));
    (obj.synonyms || []).forEach((syn) => normalized.add(normBasic(syn)));
    groups.set(canonical, normalized);
  }
  return groups;
})();

function extractIncludeExclude(textNorm, plan) {
  const include = new Set();
  const exclude = new Set();
  const allergensExclude = new Set();

  const lowSodiumHit =
    /\b(poca|baja)\s+sal\b/.test(textNorm) || /\bsin\s+sal\b/.test(textNorm);

  const ingredientMap = new Map();
  for (const [token, group] of Object.entries(INGREDIENTS)) {
    (group.synonyms || []).forEach((syn) => {
      const n = normalize(syn);
      if (n) ingredientMap.set(n, token);
    });
  }

  const allergenMap = new Map();
  for (const [token, group] of Object.entries(ALLERGENS)) {
    (group.synonyms || []).forEach((syn) => {
      const n = normalize(syn);
      if (n) allergenMap.set(n, token);
    });
  }

  const buildPattern = (syn) => new RegExp(`\\b${escapeRegex(syn)}(?:s|es|ito|itos|ita|itas)?\\b`, "i");

  for (const [syn, token] of ingredientMap.entries()) {
    const pattern = new RegExp(`\\bsin\\s+${buildPattern(syn).source}`, "i");
    if (pattern.test(textNorm)) {
      exclude.add(token);
    }
  }

  for (const [syn, token] of allergenMap.entries()) {
    const pattern = new RegExp(`\\bsin\\s+${buildPattern(syn).source}`, "i");
    if (pattern.test(textNorm)) {
      allergensExclude.add(token);
    }
  }

  for (const [syn, token] of ingredientMap.entries()) {
    const pattern = new RegExp(`\\bcon\\s+${buildPattern(syn).source}`, "i");
    if (pattern.test(textNorm)) {
      if (!(lowSodiumHit && syn === "sal")) {
        include.add(token);
      }
    }
  }

  for (const [syn, token] of ingredientMap.entries()) {
    if (syn === "sal" && lowSodiumHit) continue;
    const basePattern = buildPattern(syn);
    const negPattern = new RegExp(`\\bsin\\s+${basePattern.source}`, "i");
    if (basePattern.test(textNorm) && !negPattern.test(textNorm)) {
      include.add(token);
    }
  }

  if (include.size) {
    plan.push(`Incluir ingredientes: ${JSON.stringify(Array.from(include).sort())}`);
  }
  if (exclude.size) {
    plan.push(`Excluir ingredientes: ${JSON.stringify(Array.from(exclude).sort())}`);
  }
  if (allergensExclude.size) {
    plan.push(`Excluir alergenos: ${JSON.stringify(Array.from(allergensExclude).sort())}`);
  }

  return {
    include: Array.from(include).sort(),
    exclude: Array.from(exclude).sort(),
    allergensExclude: Array.from(allergensExclude).sort(),
  };
}

function parseDiets(textNorm, plan) {
  const must = new Set();
  for (const [dKey, dObj] of Object.entries(DIETS)) {
    (dObj.synonyms || []).forEach((syn) => {
      const normSyn = normalize(syn);
      if (!normSyn) return;
      const regex = new RegExp(`\\b${escapeRegex(normSyn)}\\w*\\b`, "i");
      if (regex.test(textNorm)) {
        must.add(dKey);
      }
    });
  }
  if (
    textNorm.includes("apto celiacos") ||
    textNorm.includes("apto celiaco") ||
    textNorm.includes("sin gluten")
  ) {
    must.add("gluten_free");
  }
  const result = Array.from(must).sort();
  if (result.length) {
    plan.push(`Dietas requeridas: ${JSON.stringify(result)}`);
  }
  return result;
}

function parseHealthAndIntents(textNorm, plan) {
  const healthAny = new Set();
  const hints = new Set();
  const boost = new Set();
  const penal = new Set();

  for (const [tag, syns] of Object.entries(HEALTH.tags || {})) {
    (syns || []).forEach((syn) => {
      const normSyn = normalize(syn);
      if (!normSyn) return;
      const regex = new RegExp(`\\b${escapeRegex(normSyn)}\\w*\\b`, "i");
      if (regex.test(textNorm)) {
        healthAny.add(tag);
      }
    });
  }

  if (
    textNorm.includes("saludable") ||
    textNorm.includes("saludables") ||
    /\b(poca|baja)\s+sal\b/.test(textNorm) ||
    /\bsin\s+sal\b/.test(textNorm)
  ) {
    healthAny.add("no_fry");
    healthAny.add("low_sodium");
  }

  if (
    textNorm.includes("no me caiga pesado") ||
    textNorm.includes("mal de la panza") ||
    textNorm.includes("liviano")
  ) {
    ["no_fry", "grilled", "baked", "low_sodium"].forEach((tag) => healthAny.add(tag));
    ["soup", "no_fry", "grilled", "baked", "rice"].forEach((tag) => boost.add(tag));
    ["fried", "spicy", "creamy", "very_greasy"].forEach((tag) => penal.add(tag));
    hints.add("light_digest");
  }

  if (
    textNorm.includes("porcion grande") ||
    textNorm.includes("para compartir") ||
    textNorm.includes("tengo hambre") ||
    textNorm.includes("abundante")
  ) {
    boost.add("portion_large");
    boost.add("combos");
    hints.add("portion_large");
  }

  if (/\bcarne\b/.test(textNorm)) {
    boost.add("parrilla");
  }
  if (/\bpescado\b/.test(textNorm)) {
    boost.add("sushi");
  }

  const healthList = Array.from(healthAny).sort();
  const hintList = Array.from(hints).sort();
  const boostList = Array.from(boost).sort();
  const penalList = Array.from(penal).sort();

  if (healthList.length) {
    plan.push(`Salud: ${JSON.stringify(healthList)}`);
  }
  if (boostList.length) {
    plan.push(`Boost: ${JSON.stringify(boostList)}`);
  }
  if (penalList.length) {
    plan.push(`Penalizar: ${JSON.stringify(penalList)}`);
  }
  if (hintList.length) {
    plan.push(`Hints: ${JSON.stringify(hintList)}`);
  }

  return {
    healthAny: healthList,
    hints: hintList,
    boost: boostList,
    penal: penalList,
  };
}

function parseWeights(textNorm, plan) {
  const weights = {};
  if (textNorm.includes("buen rating")) {
    weights.rating = 0.35;
  }
  if (textNorm.includes("ultra barato")) {
    weights.price = 0.45;
  }
  if (Object.keys(weights).length) {
    plan.push(`Pesos ajustados: ${JSON.stringify(weights)}`);
  }
  return weights;
}

function parseText(text) {
  const plan = [];
  const tn = normalize(text || "");
  const restHits = parseRestaurants(text || "", plan);

  const filters = {
    category_any: parseCategory(tn, plan),
    neighborhood_any: parseNeighborhoods(text || "", plan),
    cuisines_any: parseCuisines(text || "", plan),
    ingredients_include: [],
    ingredients_exclude: [],
    diet_must: [],
    allergens_exclude: [],
    health_any: [],
    meal_moments_any: parseMealMoments(tn, plan),
    price_max: null,
    eta_max: null,
    rating_min: null,
    available_only: true,
  };

  const incExc = extractIncludeExclude(tn, plan);
  filters.ingredients_include = incExc.include;
  filters.ingredients_exclude = incExc.exclude;
  filters.allergens_exclude = incExc.allergensExclude;
  filters.diet_must = parseDiets(tn, plan);
  const health = parseHealthAndIntents(tn, plan);
  filters.health_any = health.healthAny;
  filters.price_max = parsePrice(tn, plan);
  filters.eta_max = parseEta(tn, plan);
  filters.rating_min = parseRating(text || "", plan);

  const rankingOverrides = {
    boost_tags: health.boost,
    penalize_tags: health.penal,
    weights: parseWeights(tn, plan),
  };

  if (restHits.length) {
    const joined = restHits.join(" ").toLowerCase();
    if (joined.includes("wok")) {
      filters.category_any = (filters.category_any || []).filter((c) => c !== "wok");
      filters.cuisines_any = (filters.cuisines_any || []).filter(
        (c) => c.toLowerCase() !== "wok"
      );
    }
  }

  return {
    query: {
      q: text,
      filters,
      hints: health.hints,
      ranking_overrides: rankingOverrides,
    },
    plan,
  };
}

function expandIngredients(ingredients) {
  const tokens = new Set((ingredients || []).map((raw) => normBasic(raw)));
  const canonicalHits = new Set();
  for (const [canonical, group] of INGREDIENT_GROUPS.entries()) {
    for (const token of group) {
      if (tokens.has(token)) {
        canonicalHits.add(canonical);
        break;
      }
    }
  }
  canonicalHits.forEach((canon) => tokens.add(normBasic(canon)));
  return tokens;
}

function percentilePrice(label) {
  if (!label || typeof label !== "string" || !label.startsWith("p")) {
    return null;
  }
  const pct = parseInt(label.slice(1), 10);
  if (Number.isNaN(pct)) return null;
  const index = Math.max(
    0,
    Math.min(IDX.prices_sorted.length - 1, Math.floor((pct / 100) * IDX.prices_sorted.length) - 1)
  );
  return IDX.prices_sorted[index];
}

function applyFilters(dish, filters) {
  const reasons = [];
  const dishIngredients = expandIngredients(dish.ingredients || []);
  if ((filters.available_only ?? true) && dish.available === false) {
    return { ok: false, reasons: ["No disponible"] };
  }
  const mealMoments = filters.meal_moments_any || [];
  if (mealMoments.length && !(dish.meal_moments || []).some((m) => mealMoments.includes(m))) {
    return { ok: false, reasons: [`Meal moment no coincide ${JSON.stringify(mealMoments)}`] };
  }
  const cats = filters.category_any || [];
  if (cats.length && !(dish.categories || []).some((c) => cats.includes(c))) {
    return { ok: false, reasons: [`Categoria no coincide ${JSON.stringify(cats)}`] };
  }
  const neighborhoods = filters.neighborhood_any || [];
  if (neighborhoods.length && !neighborhoods.includes(dish.restaurant?.neighborhood)) {
    return { ok: false, reasons: [`Barrio no coincide ${JSON.stringify(neighborhoods)}`] };
  }
  const cuisines = filters.cuisines_any || [];
  if (cuisines.length && !cuisines.includes(dish.restaurant?.cuisines)) {
    return { ok: false, reasons: [`Cocina no coincide ${JSON.stringify(cuisines)}`] };
  }
  const include = filters.ingredients_include || [];
  if (
    include.length &&
    !include.every((inc) => {
      const normInc = normBasic(inc);
      const canonical = INGREDIENT_SYNONYM_MAP.get(normInc);
      return (
        dishIngredients.has(normInc) ||
        (canonical && dishIngredients.has(normBasic(canonical))) ||
        dishIngredients.has(normBasic(inc))
      );
    })
  ) {
    return { ok: false, reasons: ["Falta ingrediente requerido"] };
  }
  const exclude = filters.ingredients_exclude || [];
  if (
    exclude.some((exc) => {
      const normExc = normBasic(exc);
      const canonical = INGREDIENT_SYNONYM_MAP.get(normExc);
      return (
        dishIngredients.has(normExc) ||
        (canonical && dishIngredients.has(normBasic(canonical))) ||
        dishIngredients.has(normBasic(exc))
      );
    })
  ) {
    return { ok: false, reasons: ["Contiene ingrediente excluido"] };
  }
  const diets = filters.diet_must || [];
  if (diets.length && !diets.every((flag) => dish.diet_flags?.[flag])) {
    return { ok: false, reasons: [`No cumple dietas requeridas ${JSON.stringify(diets)}`] };
  }
  const allergens = filters.allergens_exclude || [];
  if (allergens.length && (dish.allergens || []).some((a) => allergens.includes(a))) {
    return { ok: false, reasons: [`Contiene alergenos excluidos ${JSON.stringify(allergens)}`] };
  }
  const healthAny = filters.health_any || [];
  if (healthAny.length && !(dish.health_tags || []).some((tag) => healthAny.includes(tag))) {
    return { ok: false, reasons: [`No coincide salud ${JSON.stringify(healthAny)}`] };
  }
  let priceLimit = filters.price_max;
  if (typeof priceLimit === "string" && priceLimit.startsWith("p")) {
    priceLimit = percentilePrice(priceLimit);
  }
  if (priceLimit != null && dish.price_ars > priceLimit) {
    return { ok: false, reasons: ["Precio mayor a limite"] };
  }
  const etaMax = filters.eta_max;
  if (etaMax != null && dish.restaurant?.eta_min > etaMax) {
    return { ok: false, reasons: ["ETA mayor a limite"] };
  }
  const ratingMin = filters.rating_min;
  if (ratingMin != null && dish.restaurant?.rating < ratingMin) {
    return { ok: false, reasons: ["Rating menor a minimo"] };
  }
  return { ok: true, reasons };
}

const DEFAULT_WEIGHTS = {
  rating: 0.3,
  price: 0.3,
  eta: 0.1,
  pop: 0.1,
  dist: 0.1,
  lex: 0.1,
};

function norm(value, min, max) {
  if (max === min) return 0;
  return Math.max(0, Math.min(1, (value - min) / (max - min)));
}

const IDX = (() => {
  const prices = CATALOG.map((d) => d.price_ars);
  const etas = CATALOG.map((d) => d.restaurant?.eta_min ?? 0);
  const ratings = CATALOG.map((d) => d.restaurant?.rating ?? 0);
  return {
    price_min: Math.min(...prices),
    price_max: Math.max(...prices),
    eta_min: Math.min(...etas),
    eta_max: Math.max(...etas),
    rating_min: Math.min(...ratings),
    rating_max: Math.max(...ratings),
    prices_sorted: [...prices].sort((a, b) => a - b),
  };
})();

function lexScore(q, dish, filters) {
  if (!q) return 0;
  const qn = normBasic(q);
  const qWords = wordSet(qn);
  if (!qWords.size) return 0;
  const baseParts = [
    dish.dish_name,
    dish.description,
    (dish.synonyms || []).join(" "),
    (dish.ingredients || []).join(" "),
    dish.restaurant?.name || "",
  ];
  const base = normBasic(baseParts.join(" "));
  const baseWords = wordSet(base);
  let score = 0;
  const intersection = new Set();
  qWords.forEach((w) => {
    if (baseWords.has(w)) {
      intersection.add(w);
    }
  });
  if (!intersection.size) return 0;
  score = intersection.size / Math.max(1, qWords.size);
  const rn = normBasic(dish.restaurant?.name || "");
  const categoryFilter = new Set((filters?.category_any || []).map((c) => c));
  if (
    rn &&
    qn.includes(rn) &&
    (!categoryFilter.size || (dish.categories || []).some((c) => categoryFilter.has(c)))
  ) {
    score = Math.min(1, score + 0.4);
  }
  return score;
}

function distanceScore(dish, filters) {
  const nhs = filters?.neighborhood_any || [];
  if (!nhs.length) return 0.5;
  return nhs.includes(dish.restaurant?.neighborhood) ? 1 : 0;
}

function computeScore(dish, filters, query) {
  const weights = { ...DEFAULT_WEIGHTS, ...(query.weights || {}) };
  if (query.ranking_overrides?.weights) {
    Object.assign(weights, query.ranking_overrides.weights);
  }
  const ratingN = norm(dish.restaurant?.rating ?? 0, IDX.rating_min, IDX.rating_max);
  const priceN = norm(dish.price_ars, IDX.price_min, IDX.price_max);
  const etaN = norm(dish.restaurant?.eta_min ?? 0, IDX.eta_min, IDX.eta_max);
  const popN = (dish.popularity || 0) / 100;
  const distN = distanceScore(dish, filters);
  const lexN = lexScore(query.q || "", dish, filters);
  let score =
    weights.rating * ratingN +
    weights.price * (1 - priceN) +
    weights.eta * (1 - etaN) +
    weights.pop * popN +
    weights.dist * distN +
    weights.lex * lexN;
  const reasons = [
    `rating:${ratingN.toFixed(2)}`,
    `price_inv:${(1 - priceN).toFixed(2)}`,
    `eta_inv:${(1 - etaN).toFixed(2)}`,
    `pop:${popN.toFixed(2)}`,
    `dist:${distN.toFixed(2)}`,
    `lex:${lexN.toFixed(2)}`,
  ];
  const boost = query.ranking_overrides?.boost_tags || [];
  const penal = query.ranking_overrides?.penalize_tags || [];
  const tags = new Set([
    ...(dish.health_tags || []),
    ...(dish.categories || []),
    (dish.restaurant?.cuisines || "").toLowerCase(),
  ]);
  if (boost.some((tag) => tags.has(tag))) {
    score *= 1.1;
    reasons.push("boost");
  }
  if (penal.some((tag) => tags.has(tag))) {
    score *= 0.85;
    reasons.push("penal");
  }
  return { score, reasons };
}

function searchCatalog(query) {
  const filters = (query && query.filters) || {};
  const results = [];
  const rejected = [];

  CATALOG.forEach((dish) => {
    const { ok, reasons } = applyFilters(dish, filters);
    if (!ok) {
      rejected.push({ id: dish.id, why: reasons });
      return;
    }
    const { score, reasons: scoreReasons } = computeScore(dish, filters, query);
    results.push({ item: dish, score, reasons: scoreReasons });
  });

  results.sort((a, b) => b.score - a.score);

  const plan = {
    hard_filters: filters,
    ranking_weights: {
      ...DEFAULT_WEIGHTS,
      ...(query.weights || {}),
      ...((query.ranking_overrides && query.ranking_overrides.weights) || {}),
    },
    explain:
      "Se aplicaron filtros duros y luego orden ponderado. Boosts y penalizaciones consideradas.",
    rejected_sample: rejected.slice(0, 10),
  };

  return { results, plan };
}

function tiny(obj) {
  return `<pre class="tiny">${typeof obj === "string" ? obj : JSON.stringify(obj, null, 2)}</pre>`;
}

document.addEventListener("DOMContentLoaded", () => {
  const q = document.getElementById("q");
  const btn = document.getElementById("btn");
  const structured = document.getElementById("structured");
  const plan = document.getElementById("plan");
  const results = document.getElementById("results");

  async function runSearch() {
    const text = q.value.trim();
    if (!text) {
      structured.textContent = "";
      plan.textContent = "";
      results.innerHTML = '<p class="error">Ingresá una descripción de lo que querés comer para iniciar la búsqueda.</p>';
      q.focus();
      return;
    }
    btn.disabled = true;
    results.innerHTML = "<p>Buscando resultados...</p>";
    try {
      const parsed = parseText(text);
      structured.textContent = JSON.stringify(parsed.query, null, 2);
      plan.textContent = JSON.stringify(parsed.plan, null, 2);
      const searched = searchCatalog(parsed.query);
      renderResults(results, searched);
    } catch (err) {
      console.error("Error al buscar", err);
      const errorDetails = {
        version: APP_VERSION,
        message: err?.message ?? String(err),
        name: err?.name,
        stack: err?.stack,
        query: text,
        timestamp: new Date().toISOString(),
      };
      results.innerHTML = '<p class="error">No pudimos completar la búsqueda.</p>' + tiny(errorDetails);
    } finally {
      btn.disabled = false;
    }
  }

  btn.addEventListener("click", runSearch);
  q.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runSearch();
  });
  const versionBadge = document.getElementById("app-version");
  if (versionBadge) versionBadge.textContent = APP_VERSION;
});

function renderResults(container, data) {
  container.innerHTML = "";
  if (!data.results || data.results.length === 0) {
    container.innerHTML = "<p>No hay resultados. Ajustá tu consulta.</p>" + tiny(data.plan);
    return;
  }
  data.results.slice(0, 30).forEach((r, idx) => {
    const d = r.item;
    const debug = {
      id: d.id,
      categories: d.categories,
      synonyms: d.synonyms,
      ingredients: d.ingredients,
      allergens: d.allergens,
      diet_flags: d.diet_flags,
      health_tags: d.health_tags,
      restaurant: d.restaurant,
    };
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = `
      <div class="title">${idx + 1}. ${d.dish_name} <span class="price">$${d.price_ars}</span></div>
      <div class="sub">${d.restaurant.name} · ${d.restaurant.neighborhood} · ${d.restaurant.cuisines}</div>
      <div class="meta">Rating ${d.restaurant.rating} · ETA ${d.restaurant.eta_min} min · Score ${r.score.toFixed(3)}</div>
      <div class="desc">${d.description}</div>
      <div class="tags">Tags: ${[...d.categories, ...d.health_tags].join(", ")}</div>
      <div class="reasons">Razones: ${r.reasons.join(", ")}</div>
      <details>
        <summary>Debug</summary>
        ${tiny(debug)}
      </details>
    `;
    container.appendChild(el);
  });
  const plan = document.getElementById("plan");
  if (plan) plan.textContent = JSON.stringify(data.plan, null, 2);
}
