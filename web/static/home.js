// Home (hero, real content counts, cards to each page) and About (what it is, how to run it, what the web leaves out).
import { route, app, api, esc, isStatic } from './core.js';

const CARDS = [
  ['talk', 'The Tavern', 'Talk to the townsfolk of Oakvale, Riverside and Bloodstone. Their minds run on the game\'s own offline heuristic code: topics you hear become askable, trust unlocks secrets, and /persuade rolls the dice.'],
  ['adventures', 'The five adventures', 'Each authored questline: its rumor, places, cast, foes, the quest chain and the branching three-way finale.'],
  ['world', 'A generated world', 'The 240 x 170 combined map the game builds for a New Game: walled Oakvale, farms, Bloodstone Castle, lairs and waystones.'],
  ['bestiary', 'Bestiary', 'Every monster template: level, HP, natural damage, speed, pack behaviour, undead nature and goals.'],
  ['spells', 'Spellbook', 'Every spell by school and tier: mana, range, damage or healing, who can learn it, which ones reshape the world.'],
  ['items', 'Armoury & items', 'Weapons, armour, scrolls, wands, relics and reagents, plus the crafting recipes.'],
];

route('home', async () => {
  const { counts: c } = await api('/info');
  app().innerHTML = `
  <section class="hero">
    <p class="kicker">A D&amp;D-style role-playing game</p>
    <h1 class="glow">LLM-RPG</h1>
    <p class="lead">A living-world RPG with LLM-powered NPCs and heroes that adventure on their own. The desktop game
    runs fully offline (a heuristic AI keeps the world alive) and plugs into Ollama, Claude or OpenAI for richer NPC
    minds. This site shows its content and lets you talk to its NPCs through the same offline code.</p>
    <a class="btn" href="#/talk">Enter the tavern</a><a class="btn alt" href="#/adventures">The adventures</a>
  </section>
  <div class="tiles">
    <a class="tile" href="#/talk"><b>${c.npcs}</b><span>named NPCs</span></a>
    <a class="tile" href="#/bestiary"><b>${c.monsters}</b><span>monster templates</span></a>
    <a class="tile" href="#/spells"><b>${c.spells}</b><span>spells in ${c.schools} schools</span></a>
    <a class="tile" href="#/items"><b>${c.items}</b><span>items</span></a>
    <a class="tile" href="#/adventures"><b>${c.adventures}</b><span>authored adventures</span></a>
    <a class="tile" href="#/adventures"><b>${c.quests}</b><span>authored quests</span></a>
  </div>
  <div class="grid wide">${CARDS.map(([r, t, d]) => `<a class="card" href="#/${r}"><b>${esc(t)}</b><span>${esc(d)}</span></a>`).join('')}</div>
  <div class="callout a"><b>No LLM here.</b> On this ${isStatic() ? 'static site' : 'local app'} every NPC reply comes
  from the game's rule-based <code>heuristic</code> provider, which is the game's default. All counts and content come
  from the repository's <code>data/*.json</code>.</div>`;
});

route('about', () => {
  app().innerHTML = `
  <h1>About</h1>
  <p class="lead">LLM-RPG is George Dickinson's introduction to building a role-playing game with an LLM: a working,
  playable reference where content lives in <code>data/*.json</code> and every LLM feature is mirrored by an offline
  heuristic.</p>
  <h2>Run the game</h2>
  <pre>pip install -r requirements.txt
python main.py                 # Pygame GUI, heuristic AI (no LLM needed)
python main.py --tutorial      # start on Tutorial Island
python main.py --ui terminal   # text UI
python main.py --provider ollama   # or anthropic / openai</pre>
  <h2>Run this web app</h2>
  <pre>pip install -r requirements-web.txt
python run_web.py              # http://127.0.0.1:8200</pre>
  <p>The local app adds generating worlds for any seed. To let an LLM speak the NPC lines in the tavern, start it
  with <code>LLM_RPG_WEB_PROVIDER=ollama</code> (or <code>anthropic</code>/<code>openai</code>, plus the game's
  <code>requirements.txt</code>); keys stay in the server's environment. Persuasion checks always use the dice.</p>
  <h2>What the web shows, and what it leaves out</h2>
  <p>Shown: NPC conversation (heuristic dialog, the topic journal, gated secrets, social checks), the content
  compendium, the five adventures, and a snapshot of a generated world. Left out: the playable game itself (movement,
  combat, the turn pipeline, the Pygame and isometric renderers), the tactical battle layer and colosseum, crafting and
  shops as actions, the Dungeon Master layer, autoplay heroes and networked play. Those need the desktop game.</p>
  <h2>How the tavern works</h2>
  <p>Each turn goes through the repo's <code>HeuristicProvider</code>, <code>TopicJournal</code>,
  <code>secrets</code> and <code>PersuasionSystem</code> (<code>web/talk.py</code>). The static site runs a JavaScript
  port of that turn (<code>talk_engine.js</code>) with CPython's random generator, and a test replays hundreds of
  recorded Python turns to check every reply matches. Quest offers, gossip and deed comments need a live world and
  are not part of the web conversation.</p>
  <h2>Credits</h2>
  <p>Game, design and content: George Dickinson (<a href="https://github.com/gddickinson/llm_RPG">gddickinson/llm_RPG</a>,
  MIT licence). ROADMAP.md notes the development plan drew on game-design research into Old School RuneScape, Stardew Valley, Caves of Qud, Kenshi and
  shipped LLM-NPC games.</p>`;
});
