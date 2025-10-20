import pytest

from server import parser


def filters_for(text: str):
    result = parser.parse(text)
    return result["query"]["filters"]


def test_allergy_avoids_shellfish_category():
    filters = filters_for("plan familiar con chicos y hay alergia fuerte a maní y mariscos, que alcance para todos")
    assert "peanut" in filters["allergens_exclude"]
    assert "shellfish" in filters["allergens_exclude"]
    assert "mariscos" not in filters["category_any"]
    assert "combos" in filters["category_any"] or "platos principales" in filters["category_any"]


def test_bugs_bunny_infers_carrot():
    filters = filters_for("almuerzo vegetariano digno de Bugs Bunny sin nada de lácteos")
    assert any(token in {"zanahoria", "espinaca", "calabaza"} for token in filters["ingredients_any"])
    assert "almuerzo" in filters["meal_moments_any"]
    assert "postres" not in filters["category_any"]
    assert "dairy" in filters["allergens_exclude"]


def test_office_rush_excludes_onion():
    filters = filters_for("estoy contra reloj en la oficina y odio cuando la comida trae cebolla")
    assert "cebolla" in filters["ingredients_exclude"]
    assert "postres" not in filters["category_any"]
    assert "almuerzo" in filters["meal_moments_any"]


def test_romantic_dinner_sets_savory_category():
    filters = filters_for("organizo una noche romántica especial y nada de frutos secos")
    assert "tree_nut" in filters["allergens_exclude"]
    assert "postres" not in filters["category_any"]
    assert any(cat in filters["category_any"] for cat in ["platos principales", "parrilla", "wok", "ensalada"])


def test_budget_vegan_dinner_infers_constraints():
    filters = filters_for("cena saludable que cuide el presupuesto, nada frito y que sea apta veganos")
    assert "vegan" in filters["diet_must"]
    assert "no_fry" in filters["health_any"]
    assert "cena" in filters["meal_moments_any"]
    assert "postres" not in filters["category_any"]
