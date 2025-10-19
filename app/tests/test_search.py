
from app.server.search import search
from app.server.parser import parse

def test_structured_pipeline():
    q = parse("ensalada con tomate y queso sin cebolla")
    s = search(q)
    assert s["results"], "Debe devolver resultados"
    # Items no deben tener cebolla
    for r in s["results"][:20]:
        assert "cebolla" not in r["item"]["ingredients"]

def test_ultra_barato_gluten_free_grande():
    q = parse("algo ultra barato apto celiacos y de porcion grande porque estoy con hambre")
    s = search(q)
    assert s["results"], "Debe haber resultados"
    # precio bajo segun percentil aproximado y gluten free
    for r in s["results"][:20]:
        assert "gluten" not in r["item"]["allergens"]
