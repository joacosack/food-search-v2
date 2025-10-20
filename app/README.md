
# Buscador inteligente v2 de platos y restaurantes

Aplicación completa y funcional para buscar platos tipo food delivery de Buenos Aires. Usa reglas determinísticas, diccionarios y parsing con expresiones regulares, y opcionalmente puede delegar la interpretación de la intención a un LLM gratuito (Groq u otro endpoint compatible con OpenAI). Incluye backend FastAPI, frontend HTML CSS JS, dataset de 150 platos y tests con Pytest. La UI detecta automáticamente el backend y cae a modo offline si no está disponible.

## Estructura

```
/app
  /server
    main.py
    search.py
    parser.py
    schema.py
  /web
    index.html
    app.js
    styles.css
  /data
    catalog.json
    dictionaries/
      categories.json
      ingredients.json
      diets.json
      allergens.json
      health.json
      intents.json
  README.md
  requirements.txt
  /tests
    test_parser.py
    test_search.py
```

## Instalación

1. Crear y activar un entorno virtual
```
python3 -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias
```
pip install -r requirements.txt
```

3. (Opcional) Levantar el backend (requerido para el modo LLM)
```
uvicorn app.server.main:app --reload
```

4. Abrir el frontend  
Si corrés sin backend, abrí `app/web/index.html` en el navegador. Si levantaste FastAPI, podés usar `http://localhost:8000/web/index.html`; la interfaz detecta el servidor y enviará las consultas a `/parse` y `/search`.

## Modo IA con LLM gratuito (Groq / OpenAI compatible)

1. Conseguí una API key:
   - [Groq](https://console.groq.com/) ofrece un plan gratuito. Creá una cuenta y generá una API key.
   - Para otro endpoint compatible con OpenAI/LLaMA, asegurate de tener la URL base y el token.
2. Exportá las variables de entorno antes de iniciar el backend:
   ```bash
   export LLM_PROVIDER=groq
   export GROQ_API_KEY="tu_api_key"
   export LLM_MODEL="llama3-8b-8192"   # opcional, por defecto usa ese modelo
   # Alternativa genérica:
   # export LLM_PROVIDER=openai
   # export LLM_API_KEY="token"
   # export LLM_BASE_URL="https://tu-endpoint/openai/v1"
   ```
   Extras útiles:
   - `LLM_STUB_RESPONSE='{"headline":"Demo","details":"Sin red","filters":{}}'` fuerza una respuesta estática para depurar sin red.
   - `LLM_TIMEOUT=15` ajusta el timeout (en segundos) del request al LLM.
3. Iniciá FastAPI con `uvicorn`. El parser combinará heurísticas locales con las sugerencias del modelo para enriquecer filtros, boosts y el resumen asesor. La UI mostrará el titular y detalle generados por el LLM. Si el backend o el modelo fallan, todo vuelve automáticamente al modo offline con filtros determinísticos.

## Pipeline

1. **Parser**: transforma texto libre a consulta estructurada usando diccionarios en `app/data/dictionaries`. Detecta categorías, barrios, cocinas, dietas, alérgenos, ingredientes a incluir y excluir, precio, rating, velocidad, salud, y genera hints y overrides.
2. **Filtros duros**: se aplican sobre el catálogo. Si `price_max` viene como percentil, el buscador traduce la etiqueta a un valor real con la distribución de precios.
3. **Orden fino**: score ponderado
```
score = w_rating*norm(rating) + w_price*(1-norm(price)) + w_eta*(1-norm(eta)) + w_pop*pop + w_dist*dist + w_lex*lex
```
Con boosts y penalizaciones según `ranking_overrides` y tags de salud y categoría.

4. **Plan de búsqueda**: el backend devuelve `plan` con filtros aplicados, pesos y ejemplos de rechazados.

## Diccionarios

- `categories.json`: categorías y sinónimos
- `ingredients.json`: ingredientes y sinónimos
- `diets.json`: mapeo de dietas
- `allergens.json`: alérgenos y sinónimos
- `health.json`: tags de salud y estilo de cocción, con keywords
- `intents.json`: hints de contexto

Para extender, agregá sinónimos o nuevas claves y el parser las respetará sin tocar el código.

## Ejemplos de consultas

- `mi novia está mal de la panza, no quiere algo que le caiga pesado`
- `algo ultra barato apto celíacos y de porción grande porque estoy con hambre`
- `ensalada con tomate y queso sin cebolla`
- `pasta con salsa de tomate sin nueces y con buen rating`
- `parrilla para compartir con amigos`
- `sushi en Belgrano con entrega rápida`

## Cómo correr tests

```
pytest -q
```

## Extensiones futuras

- Agregar embeddings para *lexical expansion* offline y precalcular vectores para no usar LLM en runtime.
- Incorporar un cross-encoder para re-ranking como paso 2.5, con caché de features.
- Enriquecer distancia con coordenadas y Haversine.
- Aprender pesos con validación A/B o regresión por clics reales.
