// Static-site data layer: answers api(path, body) from the JSON exported by scripts/build_static.py. A conversation
// turn (POST /talk) is played in the browser by talk_engine.js, the exact JS port of web/talk.py (the game's offline
// heuristic dialog). Generating new worlds (/world/<seed>) needs the Python server.
import { takeTurn } from './talk_engine.js';

const files = new Map();
async function file(rel) {
  if (!files.has(rel)) {
    files.set(rel, fetch('api/' + rel + '.json').then(r => { if (!r.ok) throw new Error(`${r.status} ${rel}`); return r.json(); }));
  }
  return files.get(rel);
}

export async function staticApi(path, body) {
  const clean = path.split('?')[0].replace(/^\/+|\/+$/g, '');
  if (clean === 'talk' && body) {
    const out = takeTurn(await file('talk/data'), body.npc, body.message || '', body.state || {});
    return { ...out, provider: 'heuristic' };
  }
  if (clean === 'talk/mode') return { provider: 'heuristic' };
  if (/^world\/\d+$/.test(clean)) throw new Error('Generating a new world needs the local app (Python server).');
  return file(clean);
}
