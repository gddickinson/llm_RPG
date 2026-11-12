// Spellbook: every spell in data/spells.json (via api/spells), by school and tier.
import { route, app, api, esc, tags, $ } from './core.js';
import { filterBar, opts, uniq, has, stat } from './ui.js';

const TIER = { 1: '(novice)', 2: '', 3: '', 4: '', 5: '(master)' };   // engine/spells.py: tier 1 (novice) .. 5 (master)

function card(s) {
  const req = s.requires ? Object.entries(s.requires).map(([k, v]) => `${k.replace('_', ' ')} ${v}`).join(', ') : '';
  return `<div class="card"><span class="lvl">T${s.tier}</span><h4>${esc(s.name)}</h4>
    <div>${stat('mana', s.mana)}${stat('range', s.range)}${stat('dmg', s.damage)}${stat('heal', s.heal)}${stat('area', s.area)}${s.status ? stat(s.status, s.duration ? `${s.duration}t` : '') : ''}</div>
    <p>${esc(s.description)}</p>
    <div>${tags([s.school], 'a')}${tags([s.world && 'reshapes the world', s.concentration && 'concentration', s.shapeshift && 'shapeshift'].filter(Boolean), 'b')}${tags(s.classes, 'c')}</div>
    ${req ? `<p class="small mute">Requires: ${esc(req)}</p>` : ''}</div>`;
}

route('spells', async () => {
  const rows = await api('/spells');
  const classes = uniq(rows.flatMap(s => s.classes));
  app().innerHTML = `<p class="kicker">Compendium</p><h1 class="glow">Spellbook</h1>
    <p class="lead">${rows.length} spells across ${uniq(rows.map(s => s.school)).length} schools and five tiers, from
    <code>data/spells.json</code>. A new caster starts with novice spells of their class; higher tiers come with levels or
    from tomes and trainers.</p>
    <div id="fb"></div><p class="count" id="n"></p><div class="grid wide" id="list"></div>`;
  filterBar($('#fb'), [
    { id: 'q', label: 'Search', type: 'text', placeholder: 'name or effect', wide: true },
    { id: 'school', label: 'School', type: 'select', options: opts(uniq(rows.map(s => s.school))) },
    { id: 'tier', label: 'Tier', type: 'select', options: [['', 'All'], ...Object.entries(TIER).map(([k, v]) => [k, `${k} ${v}`])] },
    { id: 'cls', label: 'Class', type: 'select', options: opts(classes) },
  ], f => {
    const shown = rows.filter(s => has(s, f.q, ['name', 'description', 'status'])
      && (!f.school || s.school === f.school) && (!f.tier || String(s.tier) === f.tier) && (!f.cls || s.classes.includes(f.cls)));
    $('#n').textContent = `${shown.length} of ${rows.length}`;
    $('#list').innerHTML = shown.map(card).join('') || '<p class="mute">No spell matches.</p>';
  });
});
