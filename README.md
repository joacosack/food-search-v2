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

La IA está configurada y funcionando con Groq:

```bash
# Variables ya configuradas
export LLM_PROVIDER=groq
export GROQ_API_KEY=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
export LLM_MODEL=llama-3.3-70b-versatile

# O usar el script de inicio
./app/start_server.sh
```

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
