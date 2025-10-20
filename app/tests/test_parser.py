
import json
from app.server.parser import parse
from app.server.search import search as do_search

def _run(text):
    pq = parse(text)
    res = do_search(pq)
    return pq, res

def top_names(res, k=5):
    return [r["item"]["dish_name"] for r in res["results"][:k]]

def test_vegetariano_no_carnes():
    pq, res = _run("vegetariano")
    tops = top_names(res, 20)
    for name in tops:
        assert "Milanesa" not in name and "Burger clásica" not in name

def test_sin_nueces_excluye():
    pq, res = _run("sin nueces")
    for r in res["results"][:30]:
        assert "nueces" not in r["item"]["ingredients"]

def test_apto_celiacos_excluye_gluten():
    pq, res = _run("apto celiacos")
    for r in res["results"][:30]:
        assert "gluten" not in r["item"]["allergens"]

def test_pasta_barata_sin_espinaca():
    pq, res = _run("pasta barata sin espinaca")
    assert any("Ravioles" in r["item"]["dish_name"] or "Ñoquis" in r["item"]["dish_name"] for r in res["results"])

def test_no_caiga_pesado_no_fritos_top5():
    pq, res = _run("no me caiga pesado")
    names = top_names(res, 5)
    for r in res["results"][:5]:
        assert "fried" not in r["item"]["health_tags"]

def test_rapido_eta_25():
    pq, res = _run("rapido")
    for r in res["results"][:20]:
        assert r["item"]["restaurant"]["eta_min"] <= 25

def test_porcion_grande_barata():
    pq, res = _run("porcion grande barata")
    # expect some portion_large pizzas or combos in top results with reasonable price
    assert any("portion_large" in r["item"]["health_tags"] for r in res["results"][:10])

def test_buen_rating_prioriza():
    pq1, res1 = _run("pasta con buen rating")
    pq2, res2 = _run("pasta")
    assert res1["results"][0]["item"]["restaurant"]["rating"] >= 4.3

def test_sushi_belgrano_filtra():
    pq, res = _run("sushi en Belgrano")
    for r in res["results"][:20]:
        assert r["item"]["restaurant"]["neighborhood"] == "Belgrano" and r["item"]["restaurant"]["cuisines"] == "Sushi"

def test_no_match_plan():
    pq, res = _run("sin sentido xyz con ingrediente inexistente qwerty")
    # Force an impossible include to simulate no results
    pq["query"]["filters"]["ingredients_include"] = ["ingrediente_inexistente_xyz"]
    res2 = do_search(pq)
    assert res2["results"] == []

def test_cita_romantica_activa_asesor():
    pq, res = _run("tengo una cita romántica en Palermo")
    assert "romantic_date" in pq["query"].get("scenario_tags", [])
    assert pq["query"].get("advisor_summary")
    assert pq["query"]["filters"]["rating_min"] >= 4.4
    romantic_hits = [r for r in res["results"][:5] if "romantic" in (r["item"].get("experience_tags") or [])]
    assert romantic_hits

def test_presupuesto_ajustado_limita_precio():
    pq, res = _run("quiero comer pero no tengo mucha plata")
    assert "budget_friendly" in pq["query"].get("scenario_tags", [])
    price_cap = pq["query"]["filters"]["price_max"]
    assert price_cap is not None and price_cap <= 4500
    assert all(r["item"]["price_ars"] <= price_cap for r in res["results"][:10])

def test_almuerzo_rapido_prioriza_eta():
    pq, res = _run("algo rapido para almorzar")
    assert "quick_lunch" in pq["query"].get("scenario_tags", [])
    assert pq["query"]["filters"]["eta_max"] <= 25
    quick_hits = [r for r in res["results"][:8] if "quick_lunch" in (r["item"].get("experience_tags") or [])]
    assert quick_hits


def test_llm_stub_merges_filters(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv(
        "LLM_STUB_RESPONSE",
        json.dumps(
            {
                "headline": "Asistente LLM",
                "details": "Preferencias detectadas automáticamente.",
                "filters": {"category_any": ["Parrilla"], "price_max": 3500},
                "ranking_overrides": {"boost_tags": ["romantic"]},
                "hints": ["llm_hint"],
                "scenario_tags": ["llm_defined"],
            }
        ),
    )
    pq = parse("busco algo romantico con carne")
    filters = pq["query"]["filters"]
    assert "Parrilla" in filters["category_any"]
    assert filters["price_max"] == 3500
    assert "romantic" in pq["query"]["ranking_overrides"]["boost_tags"]
    assert "llm_hint" in pq["query"]["hints"]
    assert "llm_defined" in pq["query"]["scenario_tags"]
    assert any("LLM" in step for step in pq["plan"])
