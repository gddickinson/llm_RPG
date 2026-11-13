// The five authored adventures (api/adventures): list and one page each with rumor, places, cast, foes, the quest
// chain and the branching finale. Everything is read from the adventure's data file and data/quests.json.
import { route, app, api, esc, tags } from './core.js';

route('adventures', async () => {
  const advs = await api('/adventures');
  app().innerHTML = `<p class="kicker">Questlines</p><h1 class="glow">The built-in adventures</h1>
    <p class="lead">Every new game seeds these authored, multi-act adventures across the world, each with its own cast,
    clues, guarded sites, a named boss and a branching finale that reshapes the world. A rumor points you to each, and
    rival heroes may clear one before you do.</p>
    <div class="grid wide">${advs.map(a => `<a class="card" href="#/adventure/${a.id}"><b>${esc(a.title)}</b>
      <small>${esc(a.theme)} · ${a.quests.length} quests · ${a.areas.length} places</small>
      <span>${esc(a.rumor || a.areas[0]?.legend || '')}</span></a>`).join('')}</div>
    <p class="small mute">New adventures are data: a JSON file (areas, cast, clues, foes, rumor, resolved beat) plus a
    three-line registration via the reusable <code>AdventureSeeder</code>.</p>`;
});

function quest(q, i, cast) {
  const giver = cast.find(c => c.id === q.giver)?.name || q.giver;
  return `<div class="act ${q.finale ? 'finale' : ''}"><h3>Act ${i + 1}: ${esc(q.title)}</h3>
    <p>${esc(q.description)}</p>
    <ul>${q.objectives.map(o => `<li>${esc(o)}</li>`).join('')}</ul>
    <p class="small mute">Given by ${esc(giver)} · reward ${q.gold} gold, ${q.xp} XP</p>
    ${q.choices.length ? `<h3>The finale: choose one</h3>${q.choices.map(c => `<div class="choice"><b>${esc(c.label)}</b>
      <span class="small mute"> (${c.gold ?? 0} gold, ${c.xp ?? 0} XP${c.items.length ? ', ' + esc(c.items.join(', ')) : ''})</span>
      <p class="small">${esc(c.text)}</p></div>`).join('')}` : ''}</div>`;
}

route('adventure', async ([id]) => {
  const a = (await api('/adventures')).find(x => x.id === id);
  if (!a) { app().innerHTML = '<h1>No such adventure</h1><p><a href="#/adventures">All adventures</a></p>'; return; }
  const area = aid => a.areas.find(x => x.id === aid)?.name || aid;
  app().innerHTML = `<p class="kicker"><a href="#/adventures">Adventures</a> · ${esc(a.theme)}</p>
    <h1 class="glow">${esc(a.title)}</h1>
    ${a.rumor ? `<p class="lead">${esc(a.rumor)}</p>` : ''}
    <h2>Places</h2><div class="grid wide">${a.areas.map(x => `<div class="card"><b>${esc(x.name)}</b>
      <small>${esc(x.kind || '')}${x.near ? ` · near ${esc(x.near)}` : ''}</small><span>${esc(x.legend)}</span></div>`).join('')}</div>
    <h2>Cast</h2><div class="grid wide">${a.cast.map(c => `<div class="card"><b>${esc(c.name)}</b>
      <small>${esc(c.race)} ${esc(c.class)}, level ${c.level}${c.quest_giver ? ' · quest giver' : ''}</small>
      <span>${esc(c.description)}</span><div>${tags(c.traits, 'a')}</div></div>`).join('')}</div>
    ${a.foes.length ? `<h2>Foes</h2><div class="scroll"><table><thead><tr><th>Foe</th><th>Level</th><th>Count</th><th>Where</th></tr></thead><tbody>
      ${a.foes.map(f => `<tr><td>${f.boss ? '<b class="rar-legendary">' : ''}${esc(f.name)}${f.boss ? '</b> (boss)' : ''}</td><td>${f.level ?? ''}</td><td>${f.count}</td><td>${esc(area(f.area))}</td></tr>`).join('')}</tbody></table></div>` : ''}
    ${a.clues.length ? `<p><span class="mute">Clue:</span> ${a.clues.map(c => `${esc(c.item)} at ${esc(area(c.area))}`).join('; ')}</p>` : ''}
    <h2>The quest chain</h2>${a.quests.map((q, i) => quest(q, i, a.cast)).join('')}
    ${a.resolved ? `<div class="callout a"><b>When it ends:</b> ${esc(a.resolved)}</div>` : ''}
    <p class="small mute">Source: <code>${esc(a.file)}</code> and <code>data/quests.json</code>. The cast are not in the
    general NPC roster, so they cannot be visited in the Tavern.</p>`;
});
