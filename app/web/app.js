
const APP_VERSION = "v1.1.1";

const DEFAULT_API = "http://127.0.0.1:8000";
const API_STORAGE_KEY = "foodsearch.apiBase";
const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "0.0.0.0", "::1"]);

function tryParseUrl(value) {
  if (!value) return null;
  try {
    return new URL(value);
  } catch (err) {
    return null;
  }
}

function isLocalHostname(hostname) {
  if (!hostname) return false;
  const normalized = hostname.toLowerCase();
  if (LOCAL_HOSTS.has(normalized)) {
    return true;
  }
  if (normalized.startsWith("127.")) {
    return true;
  }
  return false;
}

function getLocalApiWarning(apiBase) {
  const parsed = tryParseUrl(apiBase);
  if (!parsed) return "";
  if (!isLocalHostname(parsed.hostname)) {
    return "";
  }
  if (isLocalHostname(location.hostname) || parsed.hostname === location.hostname) {
    return "";
  }
  return `El backend configurado (${parsed.origin}) apunta a tu computadora local. Solo funciona desde el dispositivo que está ejecutando ese servidor. Abrí la app en esa máquina o configurá un backend accesible (por ejemplo con ?apiBase=https://tu-servidor).`;
}

function normalizeBase(raw) {
  if (!raw) return "";
  let candidate = String(raw).trim();
  if (!candidate) return "";
  if (!/^https?:\/\//i.test(candidate)) {
    candidate = `${location.protocol}//${candidate}`;
  }
  try {
    const parsed = new URL(candidate);
    const cleanPath = parsed.pathname === "/" ? "" : parsed.pathname.replace(/\/$/, "");
    return `${parsed.protocol}//${parsed.host}${cleanPath}`;
  } catch (err) {
    return "";
  }
}

function resolveApiBase() {
  const params = new URLSearchParams(location.search);
  const paramValue = params.get("apiBase") || params.get("api");
  if (paramValue) {
    const normalized = normalizeBase(paramValue);
    if (normalized) {
      localStorage.setItem(API_STORAGE_KEY, normalized);
      return normalized;
    }
  }

  const stored = localStorage.getItem(API_STORAGE_KEY);
  if (stored) {
    const normalized = normalizeBase(stored);
    if (normalized) {
      return normalized;
    }
    localStorage.removeItem(API_STORAGE_KEY);
  }

  const meta = document.querySelector('meta[name="food-search-api-base"]');
  if (meta?.content) {
    const normalized = normalizeBase(meta.content);
    if (normalized) {
      return normalized;
    }
  }

  if (LOCAL_HOSTS.has(location.hostname)) {
    return `${location.protocol}//${location.host}`;
  }

  if (location.origin === "null") {
    return DEFAULT_API;
  }

  return DEFAULT_API;
}

let API = resolveApiBase();

function renderApiBase() {
  const label = document.getElementById("api-base");
  if (label) {
    label.textContent = API;
  }
  const input = document.getElementById("api-input");
  if (input && document.activeElement !== input) {
    input.value = API;
  }
  const warning = document.getElementById("api-warning");
  if (warning) {
    const message = getLocalApiWarning(API);
    if (message) {
      warning.hidden = false;
      warning.textContent = message;
    } else {
      warning.hidden = true;
      warning.textContent = "";
    }
  }
}

function setApiBase(value) {
  const normalized = normalizeBase(value);
  if (!normalized) {
    throw new Error("URL inválida. Usá un formato como https://servidor:puerto");
  }
  API = normalized;
  localStorage.setItem(API_STORAGE_KEY, API);
  renderApiBase();
}

function resetApiBase() {
  localStorage.removeItem(API_STORAGE_KEY);
  API = resolveApiBase();
  renderApiBase();
}

async function doParse(text){
  const res = await fetch(`${API}/parse`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({text})
  });
  return await res.json();
}

async function doSearch(structuredQuery){
  const res = await fetch(`${API}/search`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ query: structuredQuery })
  });
  return await res.json();
}

function tiny(obj){
  return `<pre class="tiny">${typeof obj === "string" ? obj : JSON.stringify(obj, null, 2)}</pre>`;
}

function renderResults(container, data){
  container.innerHTML = "";
  if(!data.results || data.results.length === 0){
    container.innerHTML = "<p>No hay resultados. Ajustá tu consulta.</p>" + tiny(data.plan);
    return;
  }
  data.results.slice(0,30).forEach((r, idx) => {
    const d = r.item;
    const debug = {
      id: d.id,
      categories: d.categories,
      synonyms: d.synonyms,
      ingredients: d.ingredients,
      allergens: d.allergens,
      diet_flags: d.diet_flags,
      health_tags: d.health_tags,
      restaurant: d.restaurant
    };
    const el = document.createElement("div");
    el.className = "card";
    el.innerHTML = `
      <div class="title">${idx+1}. ${d.dish_name} <span class="price">$${d.price_ars}</span></div>
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
  if(plan) plan.textContent = JSON.stringify(data.plan, null, 2);
}

document.addEventListener("DOMContentLoaded", () => {
  const q = document.getElementById("q");
  const btn = document.getElementById("btn");
  const structured = document.getElementById("structured");
  const plan = document.getElementById("plan");
  const results = document.getElementById("results");
  const apiForm = document.getElementById("api-form");
  const apiReset = document.getElementById("api-reset");

  renderApiBase();

  if (apiForm) {
    apiForm.addEventListener("submit", (evt) => {
      evt.preventDefault();
      const input = document.getElementById("api-input");
      const value = input?.value ?? "";
      try {
        setApiBase(value);
      } catch (error) {
        alert(error.message);
      }
    });
  }

  if (apiReset) {
    apiReset.addEventListener("click", (evt) => {
      evt.preventDefault();
      resetApiBase();
    });
  }

  async function runSearch(){
    const text = q.value.trim();
    if(!text){
      structured.textContent = "";
      plan.textContent = "";
      results.innerHTML = '<p class="error">Ingresá una descripción de lo que querés comer para iniciar la búsqueda.</p>';
      q.focus();
      return;
    }
    btn.disabled = true;
    results.innerHTML = "<p>Buscando resultados...</p>";
    try {
      const parsed = await doParse(text);
      structured.textContent = JSON.stringify(parsed.query, null, 2);
      plan.textContent = JSON.stringify(parsed.plan, null, 2);
      // Send only parsed.query to /search
      const searched = await doSearch(parsed.query);
      renderResults(results, searched);
    } catch (err) {
      console.error("Error al buscar", err);
      const errorDetails = {
        version: APP_VERSION,
        message: err?.message ?? String(err),
        name: err?.name,
        stack: err?.stack,
        apiBase: API,
        online: navigator.onLine,
        query: text,
        timestamp: new Date().toISOString()
      };
      const localWarning = getLocalApiWarning(API);
      if (localWarning) {
        errorDetails.hint = localWarning;
      }
      const warningHtml = localWarning ? `<p class="config-warning">${localWarning}</p>` : "";
      results.innerHTML = '<p class="error">No pudimos completar la búsqueda. Verificá tu conexión o ajustá la configuración de backend.</p>' + warningHtml + tiny(errorDetails);
    } finally {
      btn.disabled = false;
    }
  }

  btn.addEventListener("click", runSearch);
  q.addEventListener("keydown", (e) => { if(e.key === "Enter") runSearch(); });
  const versionBadge = document.getElementById("app-version");
  if(versionBadge) versionBadge.textContent = APP_VERSION;
});
