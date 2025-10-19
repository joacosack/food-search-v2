import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class LLMProviderError(RuntimeError):
    """Raised when the configured LLM provider is misconfigured."""


def _dedent(text: str) -> str:
    # Lightweight dedent without importing textwrap to keep dependencies slim.
    lines = text.splitlines()
    if not lines:
        return text
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return ""
    prefix = None
    for line in lines:
        stripped = len(line) - len(line.lstrip())
        if line.strip():
            prefix = stripped if prefix is None else min(prefix, stripped)
    if not prefix:
        return "\n".join(lines)
    return "\n".join(line[prefix:] if len(line) >= prefix else line for line in lines)


class LLMPlanner:
    """Thin wrapper around Groq/LLaMA style chat-completions."""

    def __init__(self, opener: Optional[urllib.request.OpenerDirector] = None) -> None:
        self._opener = opener or urllib.request.build_opener()

    def is_enabled(self) -> bool:
        provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
        if provider == "stub":
            return bool(os.getenv("LLM_STUB_RESPONSE"))
        if provider in {"groq", "llama"}:
            return True
        return False

    def plan(self, user_text: str, baseline: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
        if provider == "stub":
            stub_payload = os.getenv("LLM_STUB_RESPONSE")
            if not stub_payload:
                return None
            try:
                return json.loads(stub_payload)
            except json.JSONDecodeError as exc:
                raise LLMProviderError(f"LLM_STUB_RESPONSE inválido: {exc}") from exc

        if provider not in {"groq", "llama"}:
            return None

        api_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("LLAMA_API_KEY")
        if not api_key:
            raise LLMProviderError(
                "Falta la API key. Definí LLM_API_KEY, GROQ_API_KEY o LLAMA_API_KEY para usar el modo LLM."
            )

        base_url = os.getenv("LLM_BASE_URL")
        if not base_url:
            if provider == "groq":
                base_url = "https://api.groq.com/openai/v1/chat/completions"
            else:
                raise LLMProviderError(
                    "Definí LLM_BASE_URL con el endpoint OpenAI-compatible del modelo LLaMA que quieras usar."
                )

        model = os.getenv("LLM_MODEL", "llama3-8b-8192")
        timeout = float(os.getenv("LLM_TIMEOUT", "20"))

        payload = self._build_openai_payload(user_text, baseline, model)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            data = self._post_json(base_url, headers, payload, timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore") if hasattr(exc, "read") else str(exc)
            raise LLMProviderError(f"El proveedor devolvió HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError(f"No se pudo conectar al proveedor LLM: {exc}") from exc
        return self._extract_plan_from_openai(data)

    def _post_json(self, url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            body = resp.read().decode(charset)
        return json.loads(body)

    def _build_openai_payload(self, user_text: str, baseline: Dict[str, Any], model: str) -> Dict[str, Any]:
        # Baseline is already a plain dict, but make sure it's JSON serializable.
        safe_baseline = json.loads(json.dumps(baseline))

        system_prompt = _dedent(
            """
            Eres un planificador gastronómico experto.
            Debes analizar la consulta del usuario, entender su intención y devolver un único objeto JSON.
            El JSON debe tener estrictamente las claves:
            {
              "advisor_summary": string corto que sintetiza el plan (<= 200 caracteres),
              "advisor_details": texto explicativo con 2-3 frases,
              "filters": objeto con los filtros duros a aplicar usando claves conocidas (category_any, cuisines_any, experience_tags_any, etc.),
              "ranking_overrides": objeto con listas boost_tags, penalize_tags y weights numéricos,
              "scenario_tags": lista de strings con etiquetas de escenario detectadas,
              "hints": lista de strings opcionales para guiar la UI,
              "query_text": string con la consulta libre sugerida para ranking léxico,
              "explanation": frase corta del razonamiento del modelo
            }
            Respetá las estructuras existentes y usá únicamente categorías, cocinas, dietas y tags vistos en el contexto.
            Si algo no aplica, usá null o listas vacías.
            Devolvé solo JSON válido sin texto adicional.
            """
        )

        user_prompt = _dedent(
            """
            Usuario: {user_text}
            Contexto actual de filtros y hints:
            {baseline}
            Lista de categorías disponibles: {categories}
            Lista de cocinas disponibles: {cuisines}
            Lista de dietas conocidas: {diets}
            Lista de tags de experiencia frecuentes: {experience_tags}
            Recordá responder únicamente con JSON válido.
            """
        ).format(
            user_text=user_text,
            baseline=json.dumps(safe_baseline, ensure_ascii=False, indent=2),
            categories=
                "[" + ", ".join(sorted(baseline.get("_categories", []))) + "]",
            cuisines=
                "[" + ", ".join(sorted(baseline.get("_cuisines", []))) + "]",
            diets=
                "[" + ", ".join(sorted(baseline.get("_diets", []))) + "]",
            experience_tags=
                "[" + ", ".join(sorted(baseline.get("_experience_tags", []))) + "]",
        )

        return {
            "model": model,
            "temperature": 0.2,
            "max_tokens": 600,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

    def _extract_plan_from_openai(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        choices = payload.get("choices") or []
        if not choices:
            return None
        content = choices[0].get("message", {}).get("content") or ""
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None
        text = match.group(0)
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        return data


# Default singleton used across the app
planner = LLMPlanner()

