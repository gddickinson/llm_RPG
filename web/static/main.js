// Entry point: registers the page modules (loaded on first visit), sets the mode line, draws the background, starts
// the router.
import { start, route, lazy, app, $, isStatic } from './core.js';
import { background } from './background.js';

const PAGES = {
  'home.js': ['home', 'about'], 'talk.js': ['talk'], 'adventures.js': ['adventures', 'adventure'],
  'world.js': ['world'], 'bestiary.js': ['bestiary'], 'spells.js': ['spells'], 'items.js': ['items'],
};
lazy(Object.fromEntries(Object.entries(PAGES).flatMap(([file, names]) => names.map(n => [n, () => import('./' + file)]))));

route('notfound', () => { app().innerHTML = '<h1>Not found</h1><p><a href="#/">Back to the start</a></p>'; });

$('#mode').textContent = isStatic()
  ? 'static site: NPCs talk through the game\'s offline heuristic code in your browser (no LLM)'
  : 'local app: Python API at /api';
background($('#bg'));
start();
