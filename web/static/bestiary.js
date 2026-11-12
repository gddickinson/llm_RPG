// Bestiary: every monster template in data/monsters.json (via api/monsters), filterable.
import { route, app, api, esc, tags, $ } from './core.js';
import { filterBar, opts, has, stat } from './ui.js';

const KINDS = [['', 'All'], ['undead', 'Undead'], ['boss', 'Bosses & apexes'], ['wandering', 'Wandering encounters'],
  ['dungeon', 'Dungeon dwellers'], ['flying', 'Fliers'], ['group', 'Packs & gangs']];

function card(m) {
  const g = m.group ? `${m.group.word || 'group'} of ${m.group.min}-${m.group.max}` : '';
  return `<div class="card"><span class="lvl">L${m.level}</span><h4>${esc(m.name)}</h4>
    <div>${stat('HP', m.hp)}${stat('dmg', m.damage)}${stat('speed', m.speed)}${stat('', g)}${m.undead ? stat('undead:', m.undead) : ''}${m.breath ? stat('breath:', m.breath) : ''}</div>
    <p>${esc(m.description)}</p>
    <div>${tags([m.boss && 'boss', m.flying && 'flies', m.active && m.active !== 'always' && `active by ${m.active}`, ...m.traits].filter(Boolean), 'b')}${tags(m.terrain, 'c')}</div>
    ${m.goals.length ? `<p class="small mute">Goals: ${esc(m.goals.join('; '))}</p>` : ''}
    ${m.preys_on.length ? `<p class="small mute">Preys on: ${esc(m.preys_on.join(', '))}</p>` : ''}
    ${m.drops.length ? `<p class="small mute">Always drops: ${esc(m.drops.join(', '))}</p>` : ''}</div>`;
}

route('bestiary', async () => {
  const rows = await api('/monsters');
  app().innerHTML = `<p class="kicker">Compendium</p><h1 class="glow">Bestiary</h1>
    <p class="lead">${rows.length} monster templates from <code>data/monsters.json</code>. The wilds scale with your party:
    elites and warbands, packs that focus-fire and break when their leader falls, and nemeses that remember you.</p>
    <div id="fb"></div><p class="count" id="n"></p><div class="grid wide" id="list"></div>`;
  filterBar($('#fb'), [
    { id: 'q', label: 'Search', type: 'text', placeholder: 'name, goal, description', wide: true },
    { id: 'kind', label: 'Kind', type: 'select', options: KINDS },
    { id: 'lvl', label: 'Level', type: 'select', options: opts(['1-3', '4-7', '8-12', '13+']) },
  ], f => {
    const [lo, hi] = f.lvl ? (f.lvl.endsWith('+') ? [13, 99] : f.lvl.split('-').map(Number)) : [0, 99];
    const shown = rows.filter(m => has({ ...m, goals: m.goals.join(' ') }, f.q, ['name', 'description', 'goals', 'race'])
      && m.level >= lo && m.level <= hi
      && (!f.kind || (f.kind === 'group' ? m.group : f.kind === 'undead' ? m.undead : m[f.kind])));
    $('#n').textContent = `${shown.length} of ${rows.length}`;
    $('#list').innerHTML = shown.map(card).join('') || '<p class="mute">No monster matches.</p>';
  });
});
