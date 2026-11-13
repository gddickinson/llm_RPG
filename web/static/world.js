// World: one generated game world (api/world, the combined New Game map built by the game's own worldgen), drawn on a
// canvas with its named places and people. The local app can generate other seeds (api/world/<seed>).
import { route, app, api, esc, isStatic, needsServer, $ } from './core.js';

const COL = { g: '#2f4a2a', f: '#1d3a22', m: '#6b6470', w: '#1f4f8a', r: '#a08a5c', b: '#8a5a44', c: '#120f16',
  s: '#3b4a33', a: '#7a7a36', u: '#5e5650', x: '#3a2a22', d: '#b79c66' };
const NAMES = { g: 'grass', f: 'forest', m: 'mountain', w: 'water', r: 'road', b: 'building / wall', a: 'farmland',
  d: 'bridge', c: 'cave', s: 'swamp', u: 'rubble', x: 'scorched' };
const MARK = { adventure: '#ff4d6d', lair: '#ff8a3d', tribe_camp: '#ff8a3d', waystone: '#5ff2ff', castle: '#ffc857',
  town: '#ffc857', village: '#ffe9a8', guildhall: '#a58bff', deepdelve_mouth: '#c6c6c6', temple: '#fff3c4', cathedral: '#fff3c4' };
const LAYERS = [['adventure', 'Adventure sites'], ['lair', 'Lairs & camps'], ['waystone', 'Waystones'],
  ['settle', 'Towns & halls'], ['people', 'People'], ['buildings', 'Every building']];

function draw(cv, w, on) {
  const S = 4, ctx = cv.getContext('2d');
  cv.width = w.width * S; cv.height = w.height * S;
  const img = ctx.createImageData(w.width, w.height);
  for (let i = 0; i < w.terrain.length; i++) {
    const c = COL[w.terrain[i]] || '#000';
    img.data.set([parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16), 255], i * 4);
  }
  const off = document.createElement('canvas'); off.width = w.width; off.height = w.height;
  off.getContext('2d').putImageData(img, 0, 0);
  ctx.imageSmoothingEnabled = false; ctx.drawImage(off, 0, 0, cv.width, cv.height);
  if (on.people) for (const [x, y, k] of w.people) {
    ctx.fillStyle = k === 1 ? '#ff4d6d' : k === 2 ? '#c9b48a' : '#e8e3ff';
    ctx.fillRect(x * S + 1, y * S + 1, 2, 2);
  }
  for (const p of shown(w, on)) {
    const cx = (p.x + p.w / 2) * S, cy = (p.y + p.h / 2) * S;
    ctx.strokeStyle = MARK[p.kind] || '#ddd'; ctx.lineWidth = 2;
    if (MARK[p.kind]) { ctx.beginPath(); ctx.arc(cx, cy, 6, 0, 6.283); ctx.stroke(); }
    else ctx.strokeRect(p.x * S, p.y * S, p.w * S, p.h * S);
  }
  const [sx, sy] = w.spawn;
  ctx.fillStyle = '#ffc857'; ctx.beginPath(); ctx.arc(sx * S + 2, sy * S + 2, 5, 0, 6.283); ctx.fill();
}

function shown(w, on) {
  return w.places.filter(p => (on.adventure && p.kind === 'adventure') || (on.lair && ['lair', 'tribe_camp', 'deepdelve_mouth'].includes(p.kind))
    || (on.waystone && p.kind === 'waystone') || (on.settle && ['castle', 'town', 'village', 'guildhall', 'cathedral'].includes(p.kind))
    || (on.buildings && !MARK[p.kind]));
}

route('world', async (args, query) => {
  const seed = query.seed && !isStatic() ? +query.seed : null;
  app().innerHTML = `<p class="kicker">Worldgen</p><h1 class="glow">A generated world</h1>
    <p class="lead">The map the game builds for a New Game: one ${'240 x 170'} world entered at walled Oakvale, with its
    farming villages, Bloodstone Castle in a far corner, lairs, tribe camps, guild halls, waystones and the five
    adventures. Generated headless by the repo's own <code>GameEngine</code>; hover for place names.</p>
    <p class="mute" id="wstat">Generating... (the first world takes about 10 seconds on the local app)</p>`;
  const w = await api(seed != null ? `/world/${seed}` : '/world');
  const on = { adventure: true, lair: true, waystone: true, settle: true, people: false, buildings: false };
  app().innerHTML = `<p class="kicker">Worldgen</p><h1 class="glow">A generated world</h1>
    <p class="lead">The map the game builds for a New Game: one ${w.width} x ${w.height} world entered at walled Oakvale
    (gold dot: where the hero wakes), with its farming villages, Bloodstone Castle in a far corner, lairs, tribe camps,
    guild halls, waystones and the five adventures. Generated headless by the repo's own <code>GameEngine</code>
    (seed ${w.seed}); hover or tap for place names.</p>
    <div class="tiles"><div class="tile"><b>${w.counts.places}</b><span>named places</span></div>
      <div class="tile"><b>${w.counts.people}</b><span>people &amp; creatures</span></div>
      <div class="tile"><b>${w.counts.hostile}</b><span>hostile</span></div></div>
    <div class="legend" id="layers">${LAYERS.map(([k, l]) => `<label><input type="checkbox" data-k="${k}" ${on[k] ? 'checked' : ''}> ${l}</label>`).join('')}</div>
    <div class="mapwrap"><canvas id="map" role="img" aria-label="Map of the generated world"></canvas><div class="tip" id="tip"></div></div>
    <div class="legend">${Object.entries(NAMES).map(([k, n]) => `<span style="--c:${COL[k]}">${n}</span>`).join('')}</div>
    <div class="row"><div><label for="seed">Another seed</label><input id="seed" type="number" min="0" max="999999" value="${w.seed}"></div>
      <div><button id="gen">Generate</button></div></div>
    ${isStatic() ? needsServer('Generating a world for another seed') : '<p class="small mute">The same seed always builds the same world.</p>'}`;
  const cv = $('#map'), tip = $('#tip');
  draw(cv, w, on);
  $('#layers').onchange = e => { on[e.target.dataset.k] = e.target.checked; draw(cv, w, on); };
  $('#gen').onclick = () => { if (isStatic()) return; location.hash = `#/world?seed=${+$('#seed').value || 0}`; };
  if (isStatic()) $('#gen').disabled = true;
  cv.addEventListener('pointermove', e => {
    const r = cv.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width * w.width, y = (e.clientY - r.top) / r.height * w.height;
    let best = null, bd = 9;
    for (const p of w.places) {
      const d = Math.hypot(p.x + p.w / 2 - x, p.y + p.h / 2 - y);
      if (d < bd) { bd = d; best = p; }
    }
    if (!best) { tip.style.display = 'none'; return; }
    tip.innerHTML = `<b>${esc(best.name)}</b><br><span class="small mute">${esc(best.kind.replace(/_/g, ' '))}</span>${best.description ? `<br><span class="small">${esc(best.description)}</span>` : ''}`;
    tip.style.display = 'block';
    const left = Math.min(e.clientX - r.left + 14, r.width - 290);
    tip.style.left = Math.max(0, left) + 'px'; tip.style.top = (e.clientY - r.top + 14) + 'px';
  });
  cv.addEventListener('pointerleave', () => { tip.style.display = 'none'; });
});
