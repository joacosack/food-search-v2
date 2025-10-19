
const isLocal = ["127.0.0.1", "localhost"].some((host) => location.origin.includes(host));
const API = (isLocal || location.origin === "null") ? "http://127.0.0.1:8000" : location.origin;

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
      results.innerHTML = '<p class="error">No pudimos completar la búsqueda. Verificá tu conexión o volvé a intentar.</p>';
    } finally {
      btn.disabled = false;
    }
  }

  btn.addEventListener("click", runSearch);
  q.addEventListener("keydown", (e) => { if(e.key === "Enter") runSearch(); });
});
