import { CATALOG } from "./data/catalog.js";
import { CATEGORIES, INGREDIENTS, DIETS, ALLERGENS, HEALTH } from "./data/dictionaries.js";

const APP_VERSION = "v2.3.0";
const BACKEND_TIMEOUT_MS = 8000;
let backendAvailable = null;

const FORCE_BACKEND = typeof window !== "undefined" && window.ENABLE_BACKEND === true;
const STATIC_MODE = !FORCE_BACKEND && (window.location.protocol === "file:" || (window.location.hostname && !/^(localhost|127\.0\.0\.1|0\.0\.0\.0)$/i.test(window.location.hostname)));
if (STATIC_MODE) {
  window.DISABLE_BACKEND = true;
  backendAvailable = false;
}

const PROMPT_SAMPLES = [
  {
    label: "Cita romántica elegante con envío gratis",
    value: "cita romántica con plato elegante, vino y envío gratis en Palermo",
  },
  {
    label: "Partido con amigos, porciones grandes",
    value: "combo abundante para ver el partido con amigos, porciones grandes y buena promo",
  },
  {
    label: "Almuerzo saludable sin gluten ni nueces",
    value: "almuerzo saludable sin gluten ni nueces para la oficina que llegue en menos de 25 minutos",
  },
  {
    label: "Postre con descuento y mismo precio",
    value: "helado artesanal con descuento y mismo precio que en el local para postre después de cenar",
  },
  {
    label: "Sushi vegano express",
    value: "sushi vegano express con costo de envío bajo y restaurantes bien calificados",
  },
];

function shouldUseBackend() {
  if (window.DISABLE_BACKEND) return false;
  if (backendAvailable === false) return false;
  return true;
}

async function callBackend(path, payload, options = {}) {
  const timeout = options.timeout ?? BACKEND_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!response.ok) {
      const err = new Error(`HTTP ${response.status}`);
      err.status = response.status;
      err.body = await response.text().catch(() => null);
      if (response.status >= 500) backendAvailable = false;
      throw err;
    }
    backendAvailable = true;
    return await response.json();
  } catch (err) {
    if (err.name === "AbortError" || err instanceof TypeError) {
      backendAvailable = false;
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

const parseViaBackend = (text) => callBackend("/parse", { text });
const searchViaBackend = (query) => callBackend("/search", { query });

function resolveStrategies(source) {
  if (!source) return [];
  if (Array.isArray(source)) return source;
  if (Array.isArray(source.llm_strategies)) return source.llm_strategies;
  return [];
}

function buildStatusMessage(parseStatus, searchPlan) {
  const lines = [];
  if (Array.isArray(searchPlan?.relaxed_filters) && searchPlan.relaxed_filters.length) {
    lines.push(`Se relajaron filtros automáticos para mostrar resultados: ${searchPlan.relaxed_filters.join(". ")}.`);
  }
  const llmInfo = (searchPlan && searchPlan.llm_status) || (parseStatus && parseStatus.llm);
  if (llmInfo) {
    const provider = llmInfo.provider || "IA";
    if (Array.isArray(llmInfo.notes)) {
      llmInfo.notes = [...new Set(llmInfo.notes)];
    }
    switch (llmInfo.status) {
      case "used": {
        let base = `Modo IA (${provider}) activo: combinando heurísticas y modelos.`;
        if (Array.isArray(llmInfo.notes) && llmInfo.notes.length) {
          base += ` ${llmInfo.notes.join(" ")}`;
        }
        lines.push(base);
        break;
      }
      case "disabled":
        lines.push("Modo offline: reglas determinísticas locales sin LLM.");
        break;
      case "error":
        lines.push(`LLM no disponible (${provider}): ${llmInfo.message || "se usó modo fallback."}`);
        break;
      case "no_data":
        lines.push(`LLM (${provider}) sin respuesta útil. Se mantienen filtros locales.`);
        break;
      default:
        lines.push(`Estado LLM (${provider}): ${llmInfo.status}`);
    }
  }

  if (searchPlan && searchPlan.backend_warning) {
    lines.push(`Fallback local: ${searchPlan.backend_warning}`);
  }

  const rawStrategies = [
    ...resolveStrategies(searchPlan && (searchPlan.strategies || searchPlan.llm_strategies)),
    ...resolveStrategies(parseStatus && parseStatus.strategies),
  ];
  const seenStrategies = new Set();
  const summaries = [];
  rawStrategies.forEach((s) => {
    if (!s) return;
    const key = `${s.label || ""}::${s.summary || ""}`;
    if (seenStrategies.has(key)) return;
    seenStrategies.add(key);
    const label = s.label || "Estrategia";
    if (s.summary) {
      summaries.push(`${label}: ${s.summary}`);
    } else if (s.filters && Object.keys(s.filters).length) {
      summaries.push(`${label}: filtros ${JSON.stringify(s.filters)}`);
    } else {
      summaries.push(label);
    }
  });
  if (summaries.length) {
    lines.push(`Estrategias activas:\n- ${summaries.join("\n- ")}`);
  }
  if (!llmInfo && (window.DISABLE_BACKEND || backendAvailable === false)) {
    lines.push("Modo offline: reglas determinísticas locales sin LLM.");
  }

  return lines.join("\n");
}

function updateStatusBanner(banner, parseStatus, searchPlan) {
  if (!banner) return;
  const message = buildStatusMessage(parseStatus, searchPlan);
  if (message) {
    banner.textContent = message;
    banner.classList.add("visible");
  } else {
    banner.textContent = "";
    banner.classList.remove("visible");
  }
}

function renderAdvisor(box, headlineEl, detailsEl, notesEl, statusEl, summary, notes, llmStatus) {
  if (!box || !headlineEl || !detailsEl || !notesEl || !statusEl) return;
  const cleanSummary = typeof summary === "string" ? summary.trim() : "";
  const summaryPartsRaw = cleanSummary ? cleanSummary.split(/\n+\s*/).filter(Boolean) : [];
  const summarySeen = new Set();
  const summaryParts = [];
  summaryPartsRaw.forEach((part) => {
    if (!summarySeen.has(part)) {
      summarySeen.add(part);
      summaryParts.push(part);
    }
  });
  const headline = summaryParts.shift() || "";
  const detailText = summaryParts.join(" ");

  const noteItemsRaw = Array.isArray(notes) ? notes.filter(Boolean) : [];
  const noteSeen = new Set();
  const noteItems = [];
  noteItemsRaw.forEach((note) => {
    if (!noteSeen.has(note)) {
      noteSeen.add(note);
      noteItems.push(note);
    }
  });

  const statusText = (() => {
    if (!llmStatus || typeof llmStatus !== "object") return "";
    const provider = llmStatus.provider || "IA";
    switch (llmStatus.status) {
      case "used":
        return `Modo IA (${provider}) activo.`;
      case "disabled":
        return "IA desactivada: usando reglas locales.";
      case "error":
        return `IA sin conexión: ${llmStatus.message || "se usan reglas locales."}`;
      case "no_data":
        return "IA sin respuesta útil: se mantienen reglas locales.";
      default:
        return llmStatus.status ? `Estado IA: ${llmStatus.status}` : "";
    }
  })();

  if (!headline && !detailText && noteItems.length === 0 && !statusText) {
    box.classList.remove("visible");
    box.hidden = true;
    headlineEl.textContent = "";
    detailsEl.textContent = "";
    notesEl.innerHTML = "";
    statusEl.textContent = "";
    return;
  }

  headlineEl.textContent = headline || "Plan del asistente";
  if (detailText) {
    detailsEl.textContent = detailText;
    detailsEl.style.display = "block";
  } else {
    detailsEl.textContent = "";
    detailsEl.style.display = "none";
  }

  notesEl.innerHTML = "";
  if (noteItems.length) {
    const frag = document.createDocumentFragment();
    noteItems.forEach((note) => {
      const li = document.createElement("li");
      li.textContent = note;
      frag.appendChild(li);
    });
    notesEl.appendChild(frag);
    notesEl.style.display = "block";
  } else {
    notesEl.style.display = "none";
  }

  statusEl.textContent = statusText;
  statusEl.style.display = statusText ? "block" : "none";

  box.classList.add("visible");
  box.hidden = false;
}

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

function augmentLocalCatalogIntents() {
  const romanticCats = new Set(["pasta", "sushi", "parrilla", "postres", "wok"]);
  const romanticCuisines = new Set(["italiana", "sushi", "parrilla"]);
  const friendsCats = new Set(["pizza", "burger", "tacos", "empanadas", "sandwich", "combos"]);
  const familyCats = new Set(["parrilla", "pizza", "pollo", "combos"]);
  const healthyCats = new Set(["ensalada", "vegano", "wok", "bowls"]);

  CATALOG.forEach((dish) => {
    const tags = new Set(dish.intent_tags || dish.experience_tags || []);
    tags.add("delivery_dining");
    const categories = new Set((dish.categories || []).map((c) => normBasic(c)));
    const cuisine = normBasic(dish.restaurant?.cuisines || "");
    const rating = dish.restaurant?.rating ?? 0;
    const price = dish.price_ars ?? 0;
    const eta = dish.delivery_eta_min ?? dish.restaurant?.eta_min ?? 60;

    const hasCategory = (set) => {
      for (const value of set) {
        if (categories.has(value)) return true;
      }
      return false;
    };

    if (rating >= 4.4 && (hasCategory(romanticCats) || romanticCuisines.has(cuisine))) {
      tags.add("romantic_evening");
      tags.add("date_night");
    }
    if (hasCategory(friendsCats)) {
      tags.add("friends_gathering");
      tags.add("movie_night");
    }
    if (hasCategory(familyCats)) {
      tags.add("family_sharing");
    }
    if (hasCategory(healthyCats)) {
      tags.add("healthy_choice");
    }
    if (price <= 6000) {
      tags.add("budget_friendly");
    }
    if (eta <= 25) {
      tags.add("express_delivery");
    }
    if (rating >= 4.7) {
      tags.add("top_rated");
    }
    if (categories.has("postres")) {
      tags.add("sweet_treat");
    }

    dish.intent_tags = Array.from(tags);
  });
}

augmentLocalCatalogIntents();

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

  // Detectar ingredientes en contextos de exclusión
  // Buscar "sin" seguido de una lista de ingredientes
  const sinContextMatch = textNorm.match(/\bsin\s+([^,]+(?:,\s*[^,]+)*)/);
  if (sinContextMatch) {
    // Extraer la lista de ingredientes después de "sin"
    const ingredientsList = sinContextMatch[1];
    // Buscar cada ingrediente en la lista
    for (const [syn, token] of ingredientMap.entries()) {
      const pattern = buildPattern(syn);
      if (pattern.test(ingredientsList)) {
        exclude.add(token);
      }
    }
    for (const [syn, token] of allergenMap.entries()) {
      const pattern = buildPattern(syn);
      if (pattern.test(ingredientsList)) {
        allergensExclude.add(token);
      }
    }
  }
  
  // También buscar patrones "ni X" independientes
  for (const [syn, token] of ingredientMap.entries()) {
    const niPattern = new RegExp(`\\bni\\s+${buildPattern(syn).source}\\b`, "i");
    if (niPattern.test(textNorm)) {
      exclude.add(token);
    }
  }
  for (const [syn, token] of allergenMap.entries()) {
    const niPattern = new RegExp(`\\bni\\s+${buildPattern(syn).source}\\b`, "i");
    if (niPattern.test(textNorm)) {
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

  // Solo incluir ingredientes que aparecen explícitamente con "con" o en contextos positivos
  // NO incluir ingredientes que aparecen en contextos de exclusión
  for (const [syn, token] of ingredientMap.entries()) {
    if (syn === "sal" && lowSodiumHit) continue;
    const basePattern = buildPattern(syn);
    const negPattern = new RegExp(`\\bsin\\s+${basePattern.source}`, "i");
    const conPattern = new RegExp(`\\bcon\\s+${basePattern.source}`, "i");
    
    // Solo incluir si aparece con "con" o en contextos claramente positivos
    // NO incluir si aparece con "sin" o en contextos de exclusión
    if (conPattern.test(textNorm) && !negPattern.test(textNorm)) {
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

function extendUnique(list, values) {
  const seen = new Set(list || []);
  values.forEach((value) => {
    if (!seen.has(value)) {
      list.push(value);
      seen.add(value);
    }
  });
  return list;
}

function percentileValue(sortedValues, pct) {
  if (!sortedValues?.length) return null;
  const clamped = Math.max(0, Math.min(1, pct));
  let index = Math.floor(clamped * sortedValues.length) - 1;
  index = Math.max(0, Math.min(sortedValues.length - 1, index));
  return sortedValues[index];
}

function priceFromPercentile(pct) {
  return percentileValue(IDX.prices_sorted, pct);
}

function etaFromPercentile(pct) {
  return percentileValue(IDX.etas_sorted, pct);
}

function tightenMinLimit(current, nextValue) {
  if (nextValue == null) return current;
  if (current == null) return nextValue;
  return Math.max(current, nextValue);
}

function tightenMaxLimit(current, nextValue) {
  if (nextValue == null) return current;
  if (current == null) return nextValue;
  return Math.min(current, nextValue);
}

function normalizePriceLimit(limit) {
  if (typeof limit === "string" && limit.startsWith("p")) {
    const pct = parseInt(limit.slice(1), 10);
    if (Number.isNaN(pct)) return null;
    return priceFromPercentile(pct / 100);
  }
  if (typeof limit === "number") return limit;
  return null;
}

function applyConversationScenarios(text, filters, rankingOverrides, hints, plan) {
  const summaries = [];
  const scenarioTags = [];
  const soft = normalizeSoft(text || "");

  const note = (label, detail) => {
    plan.push(`Escenario conversacional: ${label} -> ${detail}`);
  };

  const romanticPatterns = [
    /cita\s+romant/i,
    /salida\s+romant/i,
    /plan\s+romant/i,
    /con\s+mi\s+pareja/i,
    /cena\s+romant/i,
  ];
  if (romanticPatterns.some((re) => re.test(soft))) {
    scenarioTags.push("romantic_date");
    filters.rating_min = tightenMinLimit(filters.rating_min, 4.4);
    filters.available_only = true;
    extendUnique(hints, ["date", "special_evening"]);
    extendUnique(rankingOverrides.boost_tags, ["romantic", "date-night", "vino", "intimo"]);
    rankingOverrides.weights.rating = Math.max(rankingOverrides.weights.rating || 0.3, 0.45);
    rankingOverrides.weights.lex = Math.max(rankingOverrides.weights.lex || 0.1, 0.15);
    note("cita romántica", "priorizar lugares íntimos y con alto rating");
    summaries.push("Prioricé opciones con ambiente romántico, buen rating y etiquetas especiales de cita.");
  }

  const budgetPatterns = [
    /no\s+tengo\s+mucha\s+plata/i,
    /poco\s+presupuesto/i,
    /barato\s+pero\s+rico/i,
    /estoy\s+corto\s+de\s+plata/i,
  ];
  if (budgetPatterns.some((re) => re.test(soft))) {
    scenarioTags.push("budget_friendly");
    const basePrice = priceFromPercentile(0.28);
    const targetPrice = Math.min(basePrice ?? 4500, 4500);
    const current = normalizePriceLimit(filters.price_max);
    filters.price_max = tightenMaxLimit(current, targetPrice);
    extendUnique(rankingOverrides.boost_tags, ["budget_friendly", "ahorro", "combo"]);
    rankingOverrides.weights.price = Math.max(rankingOverrides.weights.price || 0.3, 0.45);
    rankingOverrides.weights.pop = Math.max(rankingOverrides.weights.pop || 0.1, 0.12);
    note("presupuesto ajustado", "fijar tope de precio y dar peso extra a opciones económicas");
    summaries.push("Ajusté la búsqueda a opciones accesibles y destaqué platos marcados como económicos.");
  }

  const quickPatterns = [
    /algo\s+rapido\s+para\s+almorzar/i,
    /almuerzo\s+rapido/i,
    /comer\s+rapido\s+al\s+mediodia/i,
    /necesito\s+algo\s+express/i,
  ];
  if (quickPatterns.some((re) => re.test(soft))) {
    scenarioTags.push("quick_lunch");
    const targetEta = etaFromPercentile(0.35) ?? 20;
    filters.eta_max = tightenMaxLimit(filters.eta_max, targetEta);
    const mm = new Set(filters.meal_moments_any || []);
    mm.add("almuerzo");
    filters.meal_moments_any = Array.from(mm).sort();
    extendUnique(rankingOverrides.boost_tags, ["quick_lunch", "sandwich", "wrap", "express"]);
    rankingOverrides.weights.eta = Math.max(rankingOverrides.weights.eta || 0.1, 0.22);
    rankingOverrides.weights.dist = Math.max(rankingOverrides.weights.dist || 0.1, 0.12);
    note("almuerzo rápido", "limitar tiempos de entrega y priorizar formatos express");
    summaries.push("Configuré filtros para almuerzos rápidos con entregas cortas y platos listos al paso.");
  }

  const dedup = Array.from(new Set(scenarioTags));
  return { summaries, scenarioTags: dedup };
}

function parseText(text) {
  const plan = [];
  const tn = normalize(text || "");
  const restHits = parseRestaurants(text || "", plan);

  const filters = {
    category_any: parseCategory(tn, plan),
    neighborhood_any: parseNeighborhoods(text || "", plan),
    cuisines_any: parseCuisines(text || "", plan),
    restaurant_any: restHits.length ? restHits : [],
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

  const scenario = applyConversationScenarios(text || "", filters, rankingOverrides, health.hints, plan);
  const advisorSummary = scenario.summaries.join(" ").trim() || null;

  return {
    query: {
      q: text,
      filters,
      hints: health.hints,
      ranking_overrides: rankingOverrides,
      advisor_summary: advisorSummary,
      scenario_tags: scenario.scenarioTags,
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
  const restAny = filters.restaurant_any || [];
  if (restAny.length && !restAny.includes(dish.restaurant?.name)) {
    return { ok: false, reasons: [`Restaurante no coincide ${JSON.stringify(restAny)}`] };
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
  const intentAny = filters.intent_tags_any || [];
  if (
    intentAny.length &&
    !(dish.intent_tags || dish.experience_tags || []).some((tag) => intentAny.includes(tag))
  ) {
    return { ok: false, reasons: [`No coincide intención ${JSON.stringify(intentAny)}`] };
  }
  let priceLimit = filters.price_max;
  if (typeof priceLimit === "string" && priceLimit.startsWith("p")) {
    priceLimit = percentilePrice(priceLimit);
  }
  if (priceLimit != null && dish.price_ars > priceLimit) {
    return { ok: false, reasons: ["Precio mayor a limite"] };
  }
  const etaMax = filters.eta_max;
  const etaValue = Math.min(
    dish.delivery_eta_min ?? Infinity,
    dish.restaurant?.eta_min ?? Infinity
  );
  if (etaMax != null && etaValue > etaMax) {
    return { ok: false, reasons: ["ETA mayor a limite"] };
  }
  const ratingMin = filters.rating_min;
  if (ratingMin != null && dish.restaurant?.rating < ratingMin) {
    return { ok: false, reasons: ["Rating menor a minimo"] };
  }
  return { ok: true, reasons };
}

const DEFAULT_WEIGHTS = {
  rating: 0.25,
  price: 0.2,
  eta: 0.1,
  pop: 0.1,
  dist: 0.1,
  lex: 0.1,
  promo: 0.1,
  fee: 0.05,
};

function norm(value, min, max) {
  if (max === min) return 0;
  return Math.max(0, Math.min(1, (value - min) / (max - min)));
}

const IDX = (() => {
  const prices = CATALOG.map((d) => d.price_ars);
  const etas = CATALOG.map((d) => d.restaurant?.eta_min ?? 0);
  const ratings = CATALOG.map((d) => d.restaurant?.rating ?? 0);
  const fees = CATALOG.map((d) => d.delivery_fee ?? 0);
  const discounts = CATALOG.map((d) => d.discount_pct ?? 0);
  return {
    price_min: Math.min(...prices),
    price_max: Math.max(...prices),
    eta_min: Math.min(...etas),
    eta_max: Math.max(...etas),
    rating_min: Math.min(...ratings),
    rating_max: Math.max(...ratings),
    fee_min: Math.min(...fees),
    fee_max: Math.max(...fees),
    discount_min: Math.min(...discounts),
    discount_max: Math.max(...discounts),
    prices_sorted: [...prices].sort((a, b) => a - b),
    etas_sorted: [...etas].sort((a, b) => a - b),
    ratings_sorted: [...ratings].sort((a, b) => a - b),
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
  const discountN = norm(dish.discount_pct ?? 0, IDX.discount_min, IDX.discount_max);
  const feeN = norm(dish.delivery_fee ?? 0, IDX.fee_min, IDX.fee_max);
  const distN = distanceScore(dish, filters);
  const lexN = lexScore(query.q || "", dish, filters);
  let score =
    weights.rating * ratingN +
    weights.price * (1 - priceN) +
    weights.eta * (1 - etaN) +
    weights.pop * popN +
    weights.dist * distN +
    weights.lex * lexN +
    weights.promo * discountN +
    weights.fee * (1 - feeN);
  const reasons = [
    `rating:${ratingN.toFixed(2)}`,
    `price_inv:${(1 - priceN).toFixed(2)}`,
    `eta_inv:${(1 - etaN).toFixed(2)}`,
    `pop:${popN.toFixed(2)}`,
    `dist:${distN.toFixed(2)}`,
    `lex:${lexN.toFixed(2)}`,
    `promo:${discountN.toFixed(2)}`,
    `fee_inv:${(1 - feeN).toFixed(2)}`,
  ];
  const boost = query.ranking_overrides?.boost_tags || [];
  const penal = query.ranking_overrides?.penalize_tags || [];
  const tags = new Set([
    ...(dish.health_tags || []),
    ...(dish.categories || []),
    ...(dish.experience_tags || []),
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

function localEffectiveWeights(query) {
  return {
    ...DEFAULT_WEIGHTS,
    ...(query.weights || {}),
    ...((query.ranking_overrides && query.ranking_overrides.weights) || {}),
  };
}

function runLocalSearchOnce(query) {
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
    ranking_weights: localEffectiveWeights(query),
    explain:
      "Se aplicaron filtros duros y luego orden ponderado. Boosts y penalizaciones consideradas.",
    rejected_sample: rejected.slice(0, 10),
  };
  if (query.advisor_summary) {
    plan.advisor_summary = query.advisor_summary;
  }
  if (query.scenario_tags?.length) {
    plan.scenario_tags = query.scenario_tags;
  }

  return { results, rejected, plan };
}

function searchCatalog(query) {
  const base = runLocalSearchOnce(query);
  const { results, plan } = base;
  if (query.metadata?.llm) {
    plan.llm_status = query.metadata.llm;
  }
  return { results, plan };
}

function tiny(obj) {
  return `<pre class="tiny">${typeof obj === "string" ? obj : JSON.stringify(obj, null, 2)}</pre>`;
}

document.addEventListener("DOMContentLoaded", () => {
  const q = document.getElementById("q");
  const btn = document.getElementById("btn");
  const structuredEl = document.getElementById("structured");
  const planEl = document.getElementById("plan");
  const statusBanner = document.getElementById("status-banner");
  const results = document.getElementById("results");
  const advisorBox = document.getElementById("llm-box");
  const advisorHeadline = document.getElementById("advisor-headline");
  const advisorDetails = document.getElementById("advisor-details");
  const advisorNotes = document.getElementById("advisor-notes");
  const advisorStatus = document.getElementById("advisor-status");
  const sampleSelect = document.getElementById("prompt-samples");
  const useSampleBtn = document.getElementById("use-sample");
  const showAllBtn = document.getElementById("show-all");

  if (sampleSelect) {
    PROMPT_SAMPLES.forEach((sample, index) => {
      const option = document.createElement("option");
      option.value = sample.value;
      option.textContent = `${index + 1}. ${sample.label}`;
      sampleSelect.appendChild(option);
    });
  }

  if (sampleSelect) {
    sampleSelect.addEventListener("change", () => {
      if (sampleSelect.value) q.value = sampleSelect.value;
    });
  }

  if (useSampleBtn) {
    useSampleBtn.addEventListener("click", () => {
      if (!sampleSelect || !sampleSelect.value) return;
      q.value = sampleSelect.value;
      runSearch("sample");
    });
  }

  if (showAllBtn) {
    showAllBtn.addEventListener("click", () => renderAllCatalog());
  }

  const versionBadge = document.getElementById("app-version");
  if (versionBadge) versionBadge.textContent = APP_VERSION;

  const resetAdvisor = () => {
    renderAdvisor(advisorBox, advisorHeadline, advisorDetails, advisorNotes, advisorStatus, "", [], null);
  };

  async function runSearch(trigger = "user") {
    resetAdvisor();
    updateStatusBanner(statusBanner, null, null);
    const text = q.value.trim();
    if (!text) {
      structuredEl.textContent = "";
      planEl.textContent = "";
      results.innerHTML = '<p class="error">Ingresá una descripción de lo que querés comer.</p>';
      statusBanner.textContent = "";
      statusBanner.classList.remove("visible");
      q.focus();
      return;
    }
    btn.disabled = true;
    results.innerHTML = "<p>Buscando resultados...</p>";
    try {
      let parsed;
      let usedBackend = false;
      if (shouldUseBackend()) {
        try {
          parsed = await parseViaBackend(text);
          usedBackend = true;
        } catch (backendErr) {
          console.warn("Fallo parser backend; se usa fallback local.", backendErr);
          parsed = parseText(text);
          if (!Array.isArray(parsed.plan)) parsed.plan = [];
          parsed.plan.push("Backend no disponible: se usó el parser local.");
        }
      }
      if (!parsed) {
        parsed = parseText(text);
        if (!Array.isArray(parsed.plan)) parsed.plan = [];
        if (backendAvailable === false) {
          parsed.plan.push("Backend no disponible: se usó el parser local.");
        }
      }

      structuredEl.textContent = JSON.stringify(parsed.query, null, 2);
      planEl.textContent = JSON.stringify(parsed.plan, null, 2);

      let searched;
      if (usedBackend) {
        try {
          searched = await searchViaBackend(parsed.query);
        } catch (backendErr) {
          console.warn("Fallo búsqueda backend; se usa ranking local.", backendErr);
          searched = searchCatalog(parsed.query);
          searched.plan = searched.plan || {};
          searched.plan.backend_warning =
            "Backend no disponible en este momento. Se muestran resultados locales.";
        }
      }
      if (!searched) {
        searched = searchCatalog(parsed.query);
        searched.plan = searched.plan || {};
        if (backendAvailable === false) {
          searched.plan.backend_warning =
            "Backend no disponible en este momento. Se muestran resultados locales.";
        }
      }

      if (!searched.plan) searched.plan = {};
      if (!searched.plan.llm_status && parsed.status?.llm) {
        searched.plan.llm_status = parsed.status.llm;
      }
      renderResults(results, searched);

      const advisorSummary = searched.plan?.advisor_summary || parsed.query?.advisor_summary || "";
      const llmNotes =
        searched.plan?.llm_status?.notes || parsed.status?.llm?.notes || parsed.plan?.llm_notes || [];
      const llmStatus = searched.plan?.llm_status || parsed.status?.llm;
      renderAdvisor(
        advisorBox,
        advisorHeadline,
        advisorDetails,
        advisorNotes,
        advisorStatus,
        advisorSummary,
        llmNotes,
        llmStatus
      );
      updateStatusBanner(statusBanner, parsed.status, searched.plan);
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
      resetAdvisor();
      updateStatusBanner(statusBanner, null, null);
    } finally {
      btn.disabled = false;
    }
  }

  btn.addEventListener("click", () => runSearch());
  q.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runSearch();
  });

  const PREVIEW_LIMIT = 60;

  function renderPreviewCatalog() {
    const preview = [...CATALOG]
      .sort((a, b) => (b.restaurant?.rating ?? 0) - (a.restaurant?.rating ?? 0))
      .slice(0, PREVIEW_LIMIT)
      .map((item) => ({ item, score: item.restaurant?.rating ?? 0, reasons: ["vista previa"] }));
    const planData = {
      hard_filters: {},
      explain: "Vista previa de platos destacados. Escribí un prompt o usá el botón de ver todo.",
      ranking_weights: DEFAULT_WEIGHTS,
    };
    renderResults(results, { results: preview, plan: planData });
    structuredEl.textContent = JSON.stringify({ nota: "Sin filtros aplicados" }, null, 2);
    planEl.textContent = JSON.stringify(planData, null, 2);
    statusBanner.textContent = `Mostrando ${PREVIEW_LIMIT} platos destacados. Podés escribir un prompt o ver los ${CATALOG.length} platos disponibles.`;
    statusBanner.classList.add("visible");
    const offlineLLM = window.DISABLE_BACKEND || backendAvailable === false ? { status: "disabled", provider: "local" } : null;
    renderAdvisor(advisorBox, advisorHeadline, advisorDetails, advisorNotes, advisorStatus, "", [], offlineLLM);
  }

  function renderAllCatalog() {
    const allResults = CATALOG.map((item) => ({ item, score: 0, reasons: ["catálogo completo"] }));
    const planData = {
      hard_filters: {},
      explain: "Catálogo completo sin filtros.",
      ranking_weights: DEFAULT_WEIGHTS,
    };
    renderResults(results, { results: allResults, plan: planData });
    structuredEl.textContent = JSON.stringify({ nota: "Sin filtros aplicados" }, null, 2);
    planEl.textContent = JSON.stringify(planData, null, 2);
    statusBanner.textContent = `Mostrando todos los ${allResults.length} platos disponibles.`;
    statusBanner.classList.add("visible");
    const offlineLLM = window.DISABLE_BACKEND || backendAvailable === false ? { status: "disabled", provider: "local" } : null;
    renderAdvisor(advisorBox, advisorHeadline, advisorDetails, advisorNotes, advisorStatus, "", [], offlineLLM);
  }

  renderPreviewCatalog();
  window.renderAllCatalog = renderAllCatalog;
});

function renderResults(container, data) {
  container.innerHTML = "";
  if (!data.results || data.results.length === 0) {
    container.innerHTML = "<p>No hay resultados. Ajustá tu consulta.</p>" + tiny(data.plan);
    return;
  }
  data.results.forEach((r, idx) => {
    const d = r.item;
    const etaMin = d.delivery_eta_min ?? d.restaurant?.eta_min ?? 0;
    const etaMax = d.delivery_eta_max ?? d.restaurant?.eta_max ?? etaMin;
    const deliveryFee = d.delivery_fee ?? 0;
    const feeLabel = deliveryFee === 0 ? "gratis" : `$${deliveryFee}`;
    const badgeSet = new Set();
    if ((d.discount_pct ?? 0) > 0) badgeSet.add(`${d.discount_pct}% OFF`);
    if (deliveryFee === 0) badgeSet.add("Envío gratis");
    if (d.same_price_as_local) badgeSet.add("Mismo precio que en el local");
    if (d.is_new) badgeSet.add("Nuevo ingreso");
    (d.promotion_tags || []).forEach((tag) => badgeSet.add(tag));
    const badgeHtml = Array.from(badgeSet)
      .map((tag) => `<span>${tag}</span>`)
      .join("");
    const tags = [
      ...(d.categories || []),
      ...(d.health_tags || []),
      ...(d.intent_tags || []),
      ...(d.experience_tags || []),
    ];
    const tagHtml = tags.map((tag) => `<span>${tag}</span>`).join("");
    const metaParts = [
      `Rating ${d.restaurant?.rating?.toFixed(1) ?? "–"}`,
      `ETA ${etaMin}-${etaMax} min`,
      `Envío ${feeLabel}`,
      `Score ${r.score.toFixed(3)}`,
    ];
    const debug = {
      id: d.id,
      categories: d.categories,
      synonyms: d.synonyms,
      ingredients: d.ingredients,
      allergens: d.allergens,
      diet_flags: d.diet_flags,
      health_tags: d.health_tags,
      intent_tags: d.intent_tags,
      experience_tags: d.experience_tags,
      promotion_tags: d.promotion_tags,
      delivery_fee: d.delivery_fee,
      discount_pct: d.discount_pct,
      delivery_eta_min: d.delivery_eta_min,
      delivery_eta_max: d.delivery_eta_max,
      restaurant: d.restaurant,
    };
    const reasonsHtml = `<div class="reasons">Razones: ${r.reasons.join(", ")}</div>`;
    const detailsHtml = `
      <details class="details-block">
        <summary>Detalles y debug</summary>
        ${reasonsHtml}
        ${tiny(debug)}
      </details>
    `;
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = `
      <div class="title">
        <span>${idx + 1}. ${d.dish_name}</span>
        <span class="price">$${d.price_ars}</span>
      </div>
      <div class="sub">${d.restaurant.name} · ${d.restaurant.neighborhood} · ${d.restaurant.cuisines}</div>
      <div class="meta">${metaParts.map((part) => `<span>${part}</span>`).join("")}</div>
      ${badgeHtml ? `<div class="badges">${badgeHtml}</div>` : ""}
      <div class="desc">${d.description}</div>
      ${tagHtml ? `<div class="tags"><strong>Tags:</strong>${tagHtml}</div>` : ""}
      ${detailsHtml}
    `;
    container.appendChild(el);
  });
  const planEl = document.getElementById("plan");
  if (planEl) planEl.textContent = JSON.stringify(data.plan, null, 2);
}
