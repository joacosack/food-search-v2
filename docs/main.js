// Rutas seguras para GitHub Pages y local
// Ejemplo de fetch de datos estáticos desde ./data/data.json
const dataUrl = new URL('./data/data.json', import.meta.url);

async function loadData() {
  const res = await fetch(dataUrl);
  if (!res.ok) throw new Error('No se pudo cargar data.json');
  return res.json();
}

function matchesQuery(item, q) {
  if (!q) return true;
  q = q.toLowerCase();
  return (
    item.name.toLowerCase().includes(q) ||
    item.tags.some(t => t.toLowerCase().includes(q))
  );
}

function render(list) {
  const ul = document.getElementById('results');
  ul.innerHTML = '';
  if (!list.length) {
    ul.innerHTML = '<li>No hay resultados</li>';
    return;
  }
  for (const it of list) {
    const li = document.createElement('li');
    li.textContent = it.name + ' • ' + it.tags.join(', ');
    ul.appendChild(li);
  }
}

async function init() {
  try {
    const data = await loadData();
    render(data);

    const input = document.getElementById('q');
    const btn = document.getElementById('btn');
    const run = () => {
      const q = input.value.trim();
      const filtered = data.filter(x => matchesQuery(x, q));
      render(filtered);
    };
    btn.addEventListener('click', run);
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') run();
    });
  } catch (err) {
    console.error(err);
    const ul = document.getElementById('results');
    ul.innerHTML = '<li>Error cargando datos. Revisar consola.</li>';
  }
}

init();
