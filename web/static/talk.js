// The Tavern: talk to a preset NPC. Each turn goes to POST api/talk (web/talk.py, the game's own heuristic dialog,
// topic journal, secrets and persuasion code) or, on the static site, to the identical JS port in talk_engine.js.
// The conversation state (rapport per NPC, heard topics, secrets learned, locked verbs) lives in this page and is sent
// with every turn.
import { route, app, api, esc, tags, isStatic, $ } from './core.js';
import { newState } from './talk_engine.js';

const ORIGIN = { oakvale: 'Oakvale', riverside: 'Riverside Hamlet', stonepine: 'Stonepine camp',
  bloodstone_castle: 'Bloodstone Castle', hostiles: 'The east road (hostile)' };
let S = null;                       // { data, npc, state, log: {npcId: [...]}, mode }

const rel = n => n >= 80 ? 'close friend' : n >= 60 ? 'friend' : n >= 30 ? 'friendly' : n >= 10 ? 'warm'
  : n > -10 ? 'neutral' : n > -30 ? 'cool' : 'hostile';

function meter(n) {
  const w = Math.abs(n) / 2;
  return `<div class="meter" role="img" aria-label="rapport ${n}"><i class="${n < 0 ? 'neg' : ''}" style="${n < 0 ? `left:${50 - w}%` : 'left:50%'};width:${w}%"></i></div>`;
}

function npcPanel() {
  const n = S.npc, aff = S.state.affinity[n.id] || 0;
  const p = n.personality || {};
  return `<h2 style="margin-top:0">${esc(n.name)}</h2>
    <p class="mute small">${esc(n.race)} ${esc(n.class)}, level ${n.level} · ${esc(ORIGIN[n.origin] || n.origin)}</p>
    <p>${esc(n.description)}</p>
    ${p.traits ? `<div>${tags(p.traits, 'a')}</div>` : ''}
    ${n.likes?.length ? `<p class="small"><span class="mute">Likes:</span> ${esc(n.likes.join(', '))}</p>` : ''}
    ${n.goals?.length ? `<p class="small"><span class="mute">Goals:</span> ${esc(n.goals.join('; '))}</p>` : ''}
    <label>Rapport <b>${aff}</b> (${rel(aff)})</label>${meter(aff)}
    <p class="small mute">${n.secret_count ? `Holds ${n.secret_count} secret${n.secret_count > 1 ? 's' : ''}.` : 'No secrets on record.'}
    ${n.topics.length ? ` Has their own answer about: ${esc(n.topics.join(', '))}.` : ''}</p>`;
}

function journal() {
  const known = S.data.topics.filter(t => S.state.topics.includes(t.id));
  return `<h3>Topic journal (${known.length}/${S.data.topics.length})</h3>
    ${known.length ? `<div class="chips">${known.map(t => `<button class="alt" data-ask="${esc(t.name)}" title="${esc(t.hint)}">Ask: ${esc(t.name)}</button>`).join('')}</div>`
    : '<p class="small mute">Nothing heard yet. Topics are learned by HEARING them (ask for news, earn a secret); naming one yourself does not teach it.</p>'}
    ${S.state.secrets.length ? `<p class="small mute">Secrets learned: ${S.state.secrets.length}</p>` : ''}`;
}

function bubble(m) {
  if (m.you) return `<div class="msg you"><span class="who">You</span>${esc(m.text)}</div>`;
  const cls = m.kind === 'check' ? 'check' : m.kind === 'note' ? 'note' : 'npc';
  const extra = m.learned?.length ? `<span class="learn">New topic${m.learned.length > 1 ? 's' : ''}: ${esc(m.learned.join(', '))}</span>` : '';
  return `<div class="msg ${cls}">${cls === 'note' ? '' : `<span class="who">${esc(S.npc.name)}${m.provider && m.provider !== 'heuristic' ? ` · ${esc(m.provider)}` : ''}</span>`}${esc(m.text)}${extra ? '<br>' + extra : ''}</div>`;
}

function draw() {
  $('#npcpanel').innerHTML = npcPanel();
  $('#journal').innerHTML = journal();
  const chat = $('#chat');
  const log = S.log[S.npc.id] || [];
  chat.innerHTML = log.length ? log.map(bubble).join('') : '<p class="mute small">Say hello, ask for news, or try a social check.</p>';
  chat.scrollTop = chat.scrollHeight;
}

async function say(message) {
  const npc = S.npc;
  const log = S.log[npc.id] = S.log[npc.id] || [];
  if (message) log.push({ you: true, text: message });
  else log.push({ you: true, text: '(you greet them)' });
  const r = await api('/talk', { body: { npc: npc.id, message, state: S.state } });
  S.state = r.state;
  log.push({ text: r.reply, kind: r.kind, learned: r.learned, provider: r.provider });
  draw();
}

function pick(id) {
  S.npc = S.data.npcs.find(n => n.id === id) || S.data.npcs[0];
  $('#npcsel').value = S.npc.id;
  draw();
}

route('talk', async (args, query) => {
  const [data, mode] = await Promise.all([api('/talk/data'), api('/talk/mode')]);
  if (!S) S = { data, state: newState(1, data.default_stats), log: {}, npc: null };
  S.data = data;
  const groups = {};
  for (const n of data.npcs) (groups[n.origin] = groups[n.origin] || []).push(n);
  const llm = mode.provider !== 'heuristic';
  app().innerHTML = `<div id="tavern">
  <p class="kicker">The Tavern</p><h1 class="glow">Talk to the townsfolk</h1>
  <p class="lead">Every reply comes from the game's offline <b>heuristic</b> NPC mind, the default the game ships
  with${llm ? `, except the spoken line, which this local server sends to <b>${esc(mode.provider)}</b>` : ' (no LLM)'}.
  Lines are templates chosen by class, keywords and goals; authored topic answers, trust-gated secrets and dice-rolled
  social checks come from <code>data/*.json</code> and the game's code.${isStatic() ? ' On this static site the same code runs in your browser.' : ''}</p>
  <div class="side">
    <div>
      <div class="panel">
        <label for="npcsel">Who do you approach?</label>
        <select id="npcsel">${Object.entries(groups).map(([o, ns]) => `<optgroup label="${esc(ORIGIN[o] || o)}">${ns.map(n => `<option value="${n.id}">${esc(n.name)} (${esc(n.class)})</option>`).join('')}</optgroup>`).join('')}</select>
        <div id="npcpanel" style="margin-top:12px"></div>
      </div>
      <div class="panel">
        <h3 style="margin-top:0">Your hero</h3>
        <p class="small mute">Social checks roll d20 + your stat modifier + rapport/10 against DC 14.</p>
        <div class="row">${['charisma', 'strength', 'intelligence'].map(s => `<div><label for="st-${s}">${s.slice(0, 3).toUpperCase()} (${s === 'charisma' ? 'persuade' : s === 'strength' ? 'intimidate' : 'deceive'})</label>
          <input id="st-${s}" type="number" min="3" max="20" value="${S.state.stats[s]}"></div>`).join('')}</div>
        <div class="row"><div><label for="seed">Dice seed</label><input id="seed" type="number" min="0" max="999999" value="${S.state.seed}"></div>
          <div><button class="alt" id="reset">New conversation</button></div></div>
      </div>
    </div>
    <div>
      <div id="chat" class="chat" aria-live="polite"></div>
      <div class="chips">
        <button id="greet">Greet</button>
        <button class="alt" data-say="Any news or rumors?">Any news?</button>
        <button class="alt" data-say="What wares do you sell?">Trade</button>
        <button class="alt" data-say="Do you know of any trouble on the road?">Trouble?</button>
        <button class="alt" data-cmd="/persuade ">/persuade</button>
        <button class="alt" data-cmd="/intimidate ">/intimidate</button>
        <button class="alt" data-cmd="/deceive ">/deceive</button>
      </div>
      <form class="sayrow" id="sayform"><label for="say" class="sr">Say</label>
        <input id="say" maxlength="300" placeholder="Say something, or /persuade &lt;your argument&gt;" autocomplete="off">
        <button type="submit">Say</button></form>
      <div id="journal" class="panel"></div>
    </div>
  </div></div>`;
  const input = $('#say');
  const run = async msg => { try { await say(msg); } catch (e) { (S.log[S.npc.id] ||= []).push({ text: e.message, kind: 'note' }); draw(); } };
  $('#npcsel').onchange = e => pick(e.target.value);
  $('#greet').onclick = () => run('');
  $('#sayform').onsubmit = e => { e.preventDefault(); const v = input.value.trim(); if (v) { input.value = ''; run(v); } };
  $('#tavern').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.say) run(b.dataset.say);
    if (b.dataset.ask) run(`Tell me about ${b.dataset.ask}.`);
    if (b.dataset.cmd) { input.value = b.dataset.cmd; input.focus(); }
  });
  for (const s of ['charisma', 'strength', 'intelligence']) {
    $(`#st-${s}`).onchange = e => { S.state.stats[s] = Math.max(3, Math.min(20, +e.target.value || 10)); };
  }
  $('#reset').onclick = () => {
    const seed = Math.max(0, Math.min(999999, +$('#seed').value || 0));
    S.state = newState(seed, S.state.stats); S.log = {}; draw();
  };
  pick(query.npc || S.npc?.id || 'tavernkeeper_01');
});
