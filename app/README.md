# Fix para GitHub Pages en `docs/`

Este ZIP incluye una demo mínima para comprobar que tu sitio funciona en `docs/` con rutas correctas en GitHub Pages y en local.

## Qué incluye
- `docs/index.html` con `<base>` dinámico según dominio.
- `docs/404.html` clon del index para SPA y rutas amigables en Pages.
- `docs/main.js` con `new URL('./data/data.json', import.meta.url)` para fetch sin romper rutas.
- `docs/styles.css` con estilos básicos.
- `docs/data/data.json` con datos de ejemplo.

## Cómo usarlo en tu repo
1. Copiá la carpeta `docs/` de este ZIP encima de tu `docs/` actual o integrá los cambios equivalentes.
2. Commit y push:
   ```bash
   git add docs
   git commit -m "Fix Pages: base dinámico, rutas relativas y 404 fallback"
   git push
   ```
3. En GitHub → Settings → Pages:
   - Source: Deploy from a branch
   - Branch: `main`
   - Folder: `/docs`
4. Esperar 1 a 2 minutos y abrir `https://joacosack.github.io/food-search-v2/`

## Probar en local
No uses `file://`. Levantá un server en la carpeta `docs`:
```bash
# Python
python -m http.server 5173
# Node
npx serve -p 5173 .
```
Abrí http://localhost:5173

## Integración con tu app
- Si ya tenés JS y CSS propios, solo asegurate de:
  - Rutas sin barra inicial. Usá `./` o `new URL('./ruta', import.meta.url)`.
  - Si armás rutas absolutas en runtime, prepende `window.__PATH_BASE__`.
- Si usás enrutado de cliente, conservá `docs/404.html` igual a `index.html`.

