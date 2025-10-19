
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
