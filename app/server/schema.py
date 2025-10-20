
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class Restaurant(BaseModel):
    name: str
    neighborhood: str
    cuisines: str
    rating: float
    eta_min: int

class Dish(BaseModel):
    id: str
    dish_name: str
    description: str
    categories: List[str]
    synonyms: List[str]
    ingredients: List[str]
    allergens: List[str]
    diet_flags: Dict[str, bool]
    health_tags: List[str]
    experience_tags: List[str] = Field(default_factory=list)
    not_contains: List[str]
    price_ars: int
    popularity: int
    restaurant: Restaurant
    available: bool

class ParseFilters(BaseModel):
    category_any: List[str] = Field(default_factory=list)
    meal_moments_any: List[str] = Field(default_factory=list)
    neighborhood_any: List[str] = Field(default_factory=list)
    cuisines_any: List[str] = Field(default_factory=list)
    restaurant_any: List[str] = Field(default_factory=list)
    ingredients_include: List[str] = Field(default_factory=list)
    ingredients_exclude: List[str] = Field(default_factory=list)
    diet_must: List[str] = Field(default_factory=list)
    allergens_exclude: List[str] = Field(default_factory=list)
    health_any: List[str] = Field(default_factory=list)
    intent_tags_any: List[str] = Field(default_factory=list)
    price_max: Optional[Any] = None  # number or percentile label like "p20"
    eta_max: Optional[int] = None
    rating_min: Optional[float] = None
    available_only: bool = True

class RankingOverrides(BaseModel):
    boost_tags: List[str] = Field(default_factory=list)
    penalize_tags: List[str] = Field(default_factory=list)
    weights: Dict[str, float] = Field(default_factory=dict)

class ParsedQuery(BaseModel):
    q: str
    filters: ParseFilters
    hints: List[str] = Field(default_factory=list)
    weights: Dict[str, float] = Field(default_factory=lambda: {"rating":0.3,"price":0.3,"eta":0.1,"pop":0.1,"dist":0.1,"lex":0.1})
    ranking_overrides: RankingOverrides = Field(default_factory=RankingOverrides)
    advisor_summary: Optional[str] = None
    scenario_tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SearchRequest(BaseModel):
    query: Optional[ParsedQuery] = None
    filters: Optional[ParseFilters] = None

class SearchResult(BaseModel):
    item: Dish
    score: float
    reasons: List[str]

class SearchResponse(BaseModel):
    results: List[SearchResult]
    plan: Dict[str, Any]
