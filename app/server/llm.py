import json
import os
import re
from typing import Any, Dict, Optional, List

import httpx


class LLMError(RuntimeError):
    """LLM interaction failure."""


DEFAULT_MODEL = os.getenv("LLM_MODEL", "grok-code-fast-1-0825")
DEFAULT_TIMEOUT_SEC = float(os.getenv("LLM_TIMEOUT", "15"))


def _provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "").strip().lower()


def llm_enabled() -> bool:
    provider = _provider()
    if not provider or provider in {"none", "off"}:
        return False
    if provider == "stub":
        return True
    if provider == "groq":
        return bool(os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY"))
    # Generic OpenAI-compatible provider
    return bool(os.getenv("LLM_API_KEY"))


def provider_name() -> str:
    return _provider()


def _build_messages(user_text: str, context: Dict[str, Any]) -> list[Dict[str, str]]:
    system_prompt = (
        "Sos un planificador gastronómico de Buenos Aires. "
        "Debés interpretar la intención del usuario y responder únicamente con un JSON válido sin texto adicional. "
        "El JSON debe seguir este esquema:\n"
        "{\n"
        '  "headline": string,  # resumen breve inspirador\n'
        '  "details": string,   # explicación extendida con sugerencias y razonamiento detallado paso a paso\n'
        '  "filters": {         # claves opcionales: category_any, cuisines_any, neighborhood_any, '
        'ingredients_include, ingredients_exclude, diet_must, allergens_exclude, health_any, meal_moments_any, '
        'price_max, eta_max, rating_min, available_only }\n'
        '  "ranking_overrides": {\n'
        '     "boost_tags": string[],\n'
        '     "penalize_tags": string[],\n'
        '     "weights": { "rating"?: float, "price"?: float, "eta"?: float, "pop"?: float, "dist"?: float, "lex"?: float }\n'
        "  },\n"
        '  "hints": string[],\n'
        '  "scenario_tags": string[],\n'
        '  "notes": string[],  # opcional, con insights relevantes\n'
        '  "strategies": [     # opcional, para búsquedas múltiples coordinadas\n'
        '     {\n'
        '       "label": string,\n'
        '       "summary": string,\n'
        '       "filters": { ... },\n'
        '       "ranking_overrides": { ... },\n'
        '       "hints": string[]\n'
        "     }\n"
        "  ]\n"
        "}\n"
        "Respetá los nombres de campo y usá valores concretos. "
        "Si no tenés información para un campo, devolvé un array vacío, objeto vacío o null según corresponda. "
        "No inventes restaurantes específicos fuera del catálogo. "
        "El campo 'details' debe describir explícitamente los pasos de razonamiento: qué variables considerás, qué filtros aplicarás y cómo combinarás estrategias."
    )
    user_payload = {
        "user_request": user_text,
        "base_filters": context.get("filters", {}),
        "base_hints": context.get("hints", []),
        "scenario_tags": context.get("scenario_tags", []),
        "catalog_facets": context.get("catalog_facets", {}),
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]


def _stub_response() -> Dict[str, Any]:
    stub = os.getenv("LLM_STUB_RESPONSE")
    if stub:
        try:
            return json.loads(stub)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM_STUB_RESPONSE inválido: {exc}") from exc
    return {
        "headline": "Modo demostración activo",
        "details": (
            "El asistente LLM está en modo stub. Usá GROQ_API_KEY o LLM_API_KEY para habilitar la interpretación real."
        ),
        "filters": {},
        "ranking_overrides": {},
        "hints": [],
        "scenario_tags": [],
        "notes": ["Respuesta generada localmente sin LLM."],
        "strategies": [
            {
                "label": "Plan principal",
                "summary": "Exploraré opciones variadas usando las reglas locales.",
                "filters": {},
                "ranking_overrides": {},
                "hints": [],
            }
        ],
    }


def _groq_request(messages: list[Dict[str, str]], model: str) -> str:
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        raise LLMError("Falta GROQ_API_KEY para el proveedor Groq.")
    base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 900,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=DEFAULT_TIMEOUT_SEC) as client:
        response = client.post(url, json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"Error HTTP {exc.response.status_code} desde Groq: {exc.response.text}") from exc
        data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError("Respuesta de Groq sin contenido válido.") from exc


def _generic_request(messages: list[Dict[str, str]], model: str) -> str:
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    if not api_key or not base_url:
        raise LLMError("Para proveedores genéricos se requieren LLM_API_KEY y LLM_BASE_URL.")
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 900,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=DEFAULT_TIMEOUT_SEC) as client:
        response = client.post(url, json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"Error HTTP {exc.response.status_code} desde el proveedor LLM genérico: {exc.response.text}"
            ) from exc
        data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError("Respuesta LLM sin contenido válido.") from exc


def request_plan(user_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    provider = _provider()
    if provider == "stub":
        return _stub_response()
    messages = _build_messages(user_text, context)
    model = DEFAULT_MODEL
    if provider == "groq":
        content = _groq_request(messages, model)
    else:
        content = _generic_request(messages, model)
    try:
        payload = _extract_json_payload(content)
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Respuesta del LLM no es JSON válido: {content}") from exc


def enrich_query(user_text: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not llm_enabled():
        return None
    return request_plan(user_text, context)


def _extract_json_payload(raw: str) -> str:
    """
    Extrae el primer objeto JSON válido encontrado en el texto.
    Maneja respuestas envueltas en fences Markdown como ```json ... ```.
    """
    if not raw:
        raise LLMError("Respuesta del LLM vacía.")
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*)```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    # Buscar primer objeto JSON balanceado
    start = text.find("{")
    while start != -1:
        depth = 0
        for idx in range(start, len(text)):
            ch = text[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    return candidate
        start = text.find("{", start + 1)
    raise LLMError(f"Respuesta del LLM no contiene JSON válido: {raw}")
