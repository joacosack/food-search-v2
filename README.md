# Food Search v2 - Buscador Delivery Inteligente

Un buscador inteligente de platos de delivery que utiliza IA para interpretar consultas en lenguaje natural y encontrar las mejores opciones del catálogo.

## 🚀 Características

- **Búsqueda inteligente**: Interpreta consultas como "almuerzo sin carne, cebolla ni queso"
- **Filtros avanzados**: Por ingredientes, alergenos, dietas, precio, tiempo de entrega
- **IA integrada**: Usa LLM para mejorar la interpretación de consultas
- **Modo offline**: Funciona sin conexión usando reglas locales
- **Catálogo completo**: 5000+ platos de restaurantes de Buenos Aires

## 🏃‍♂️ Uso Rápido

### GitHub Pages (Recomendado)
La aplicación está disponible automáticamente en GitHub Pages con el catálogo completo:
- Los archivos estáticos se generan automáticamente
- Incluye todos los 5000 platos del catálogo
- Funciona sin necesidad de servidor backend

### Desarrollo Local

#### Opción 1: Solo Frontend (Modo Estático)
```bash
# Generar archivos estáticos
python3 build_static.py

# Servir archivos estáticos
cd app/web
python3 -m http.server 8000
# Abrir http://localhost:8000
```

#### Opción 2: Con Backend (Modo Completo)
```bash
# Instalar dependencias
cd app
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt

# Ejecutar servidor
uvicorn server.main:app --host 0.0.0.0 --port 8000
# Abrir http://localhost:8000
```

## 🔧 Configuración de IA

La integración con Groq se maneja mediante variables de entorno. Para evitar exponer credenciales en el repositorio:

1. Copiá `app/.env.example` a `app/.env.local` (este nombre ya está ignorado por git).
2. Completá los valores necesarios:

```bash
cp app/.env.example app/.env.local
```

Editá `app/.env.local`:

```bash
LLM_PROVIDER=groq
GROQ_API_KEY="tu_api_key"
LLM_MODEL=llama-3.3-70b-versatile
```

3. Ejecutá el backend cargando esa configuración:

```bash
cd app
./start_server.sh
```

El script detecta automáticamente `.env.local`, exporta las variables y lanza el servidor. Si preferís hacerlo manualmente, exportá las variables en tu shell antes de iniciar `uvicorn`. Nunca subas tu `.env.local` ni la clave real al repositorio.

### Backend gratuito (Render)

El archivo [`render.yaml`](./render.yaml) deja listo el despliegue del backend en [Render](https://render.com), que ofrece un plan gratuito para servicios web (dormirá tras unos minutos de inactividad, pero se reactiva solo).

1. Subí el repo a GitHub sin la API key.
2. En Render: **New → Blueprint** y seleccioná el repo. Render toma las instrucciones de `render.yaml`.
3. Durante la creación, cargá las variables:
   - `GROQ_API_KEY` (marcada como secreto, no queda en el repo).
   - `LLM_PROVIDER=groq`, `LLM_MODEL=llama-3.3-70b-versatile` ya vienen preconfiguradas.
4. Tras el deploy, Render expone una URL como `https://food-search-backend.onrender.com`.

Para usar la LLM desde GitHub Pages u otro hosting estático, agregá antes del `<script type="module" src="app.js">` en `app/web/index.html`:

```html
<script>
  window.ENABLE_BACKEND = true;
  window.BACKEND_URL = "https://food-search-backend.onrender.com";
</script>
```

Luego ejecutá `python build_static.py` y publicá la carpeta `web_static` generada; la UI consumirá `/parse` y `/search` del backend seguro sin exponer la key.

## 📁 Estructura del Proyecto

```
app/
├── data/                    # Datos del catálogo
│   ├── catalog.json        # 5000 platos
│   └── dictionaries/       # Diccionarios de ingredientes, etc.
├── server/                 # Backend Python
│   ├── main.py            # API FastAPI
│   ├── parser.py          # Parser de consultas
│   ├── search.py          # Lógica de búsqueda
│   └── llm.py             # Integración con IA
├── web/                    # Frontend
│   ├── index.html         # Interfaz principal
│   ├── app.js             # Lógica del frontend
│   └── data/              # Archivos generados
└── tests/                  # Tests
```

## 🧪 Testing

```bash
cd app
source venv/bin/activate
pytest
```

## 🔍 Ejemplos de Consultas

- "almuerzo sin carne, cebolla ni queso"
- "pizza vegana con envío gratis"
- "cena romántica elegante"
- "algo rápido para almorzar"
- "postre con descuento"

## 🛠️ Desarrollo

### Generar Archivos Estáticos
```bash
python3 build_static.py
```

### Ejecutar Tests
```bash
cd app
pytest tests/
```

### Verificar Lógica de Exclusión
```bash
# Probar parser localmente
curl -X POST http://localhost:8000/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "almuerzo sin carne, cebolla ni queso"}'
```

## 📝 Notas Técnicas

- **Lógica de Exclusión**: Corregida para manejar correctamente "sin X" y "ni X"
- **Patrones de Regex**: Mejorados para detectar listas de ingredientes
- **GitHub Pages**: Configurado para generar archivos estáticos automáticamente
- **Modo Offline**: Funciona sin backend usando reglas locales

## 🚀 Despliegue

El proyecto se despliega automáticamente en GitHub Pages cuando se hace push a la rama `main`. Los archivos estáticos se generan automáticamente usando GitHub Actions.
