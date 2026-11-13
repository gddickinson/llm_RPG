// The game's offline (heuristic) NPC conversation, ported from web/talk.py, which calls the repo's real code:
// HeuristicProvider.generate_npc_dialog, TopicJournal (heard keywords become askable topics), gated secrets and the
// PersuasionSystem dice judge (d20 + stat mod + rapport/10 vs DC 14, degrees of success, day-long lockouts).
// Data (lines, topics, secrets, NPCs) comes from api/talk/data. Every draw is seeded from (seed, turn) with CPython's
// Mersenne Twister, so a turn here gives exactly the reply the Python code gives (talk_engine.test.mjs checks this).
import { PyRandom } from './py_random.js';

const HOSTILE = ['brigand', 'troll', 'monster'];
const LOCKOUT = 24 * 60;

export const turnSeed = (seed, turn) => (((seed * 1000 + turn) % 4294967296) + 4294967296) % 4294967296;
const floorDiv = (a, b) => Math.floor(a / b);
const signed = n => (n >= 0 ? '+' : '') + n;
const clamp = n => Math.max(-100, Math.min(100, n));
const title = s => s.charAt(0).toUpperCase() + s.slice(1);

export function newState(seed = 1, stats = { strength: 14, intelligence: 10, charisma: 12 }) {
  return { seed, turn: 0, affinity: {}, topics: [], secrets: [], locks: {}, stats: { ...stats } };
}

// '/persuade give me a discount' -> ['persuade', 'give me a discount'] (engine/persuasion.parse_command)
export function parseCommand(message) {
  const m = message.trim().match(/^\/(persuade|intimidate|deceive)\s+(.+)$/i);
  return m ? [m[1].toLowerCase(), m[2].trim()] : null;
}

// HeuristicProvider.generate_npc_dialog
export function npcLine(L, npc, playerMessage, rng) {
  const msg = (playerMessage || '').toLowerCase();
  const klass = npc.class;
  const greets = L.greetings[klass] || L.greetings.villager;
  if (L.greet_words.some(g => msg.includes(g))) return rng.choice(greets);
  if (L.trade_words.some(g => msg.includes(g))) return klass === 'merchant' ? L.trade_merchant : L.trade_other;
  if (L.rumor_words.some(g => msg.includes(g))) return rng.choice(L.rumors);
  for (const goal of npc.goals || []) {
    for (const [key, reply] of Object.entries(L.goal_replies)) {
      if (goal.toLowerCase().includes(key.toLowerCase())) return reply;
    }
  }
  return rng.choice(L.generic);
}

class Table {
  constructor(data, npc, state) {
    this.data = data; this.npc = npc;
    this.known = [...state.topics]; this.secretsKnown = [...state.secrets]; this.locks = { ...state.locks };
    this.rel = state.affinity[npc.id] || 0; this.stats = { ...data.default_stats, ...state.stats };
    this.last = null;
  }
  match(text) {
    const low = text.toLowerCase();
    return this.data.topics.filter(t => t.keywords.some(k => low.includes(k))).map(t => t.id);
  }
  event(text) {                                     // MemoryManager.add_event -> TopicJournal.scan
    if (text === this.last) return;
    this.last = text;
    if (text.startsWith('You say to') || text.startsWith('You try to')) return;
    for (const id of this.match(text)) if (!this.known.includes(id)) this.known.push(id);
  }
  topicLines(message) {                             // TopicJournal.heuristic_lines
    const out = [];
    for (const id of this.match(message)) {
      if (!this.known.includes(id)) continue;
      const t = this.data.topics.find(x => x.id === id);
      const line = t.responses[this.npc.id] ?? t.default_response;
      if (line) out.push(line);
    }
    return out;
  }
  secretState() {
    const all = (this.data.secrets[this.npc.id] || []).filter(s => !this.secretsKnown.includes(s.id));
    const met = s => s.other_ok && this.rel >= s.affinity;
    return { unlocked: all.filter(met), locked: all.filter(s => !met(s)).length };
  }
  modify(n) { this.rel = clamp(this.rel + n); }
}

function extras(t, base, message) {                 // DialogSystem._append_quest_prompts (heuristic parts)
  const out = [base];
  if (message) for (const line of t.topicLines(message)) out.push(`  ${line}`);
  const { unlocked, locked } = t.secretState();
  if (unlocked.length) {
    const s = unlocked[0];
    t.secretsKnown.push(s.id);
    t.event(`[Secret] ${t.npc.name}: ${s.text}`);
    out.push(`  (leaning close) ${s.text}`);
  } else if (locked) {
    out.push('  (They seem to be holding something back.)');
  }
  return out.join('\n');
}

function degreeOf(total, dc, d20) {                 // engine/skills.degree_of: 0 crit fail .. 3 crit success
  let deg = total >= dc + 10 ? 3 : total >= dc ? 2 : total <= dc - 10 ? 0 : 1;
  if (d20 === 20) deg = Math.min(deg + 1, 3); else if (d20 === 1) deg = Math.max(deg - 1, 0);
  return deg;
}

function persuade(t, verb, rng) {                   // PersuasionSystem.attempt with the dice judge
  const P = t.data.persuasion, npc = t.npc, key = `${npc.id}:${verb}`;
  if (0 < (t.locks[key] || 0)) {
    return `${npc.name} is in no mood for that again today. (Try something else, or come back tomorrow.)`;
  }
  const stat = P.verbs[verb];
  const mod = floorDiv((t.stats[stat] ?? 10) - 10, 2);
  const relBonus = floorDiv(t.rel, 10);
  const roll = rng.randint(1, 20);
  const total = roll + mod + relBonus;
  const deg = degreeOf(total, P.dc, roll);
  const reason = `(d20 ${roll} ${signed(mod)} ${stat.slice(0, 3).toUpperCase()} ${signed(relBonus)} rapport = ${total} vs DC ${P.dc})`;
  let msg;
  if (deg >= 2) {
    let note = '';
    if (verb === 'persuade') {
      t.modify(8);
      note = ['merchant', 'cleric', 'wizard', 'ranger'].includes(npc.class)
        ? `${npc.name} agrees to better prices today!` : `${npc.name} comes around to your view.`;
    } else if (verb === 'intimidate') { t.modify(-2); note = `${npc.name} backs down, shaken.`; }
    else { t.modify(5); note = `${npc.name} believes you.`; }
    if (deg === 3) { t.modify(8); note += ' A masterstroke — they are genuinely moved.'; }
    msg = `[${title(verb)} SUCCESS] ${reason} ${note}`.trim();
  } else {
    t.modify(P.fail_affinity);
    let lockout = LOCKOUT, tail = `(${npc.name} is annoyed — that approach is spent for today.)`;
    if (deg === 0) { t.modify(-5); lockout *= 2; tail = `(${npc.name} is OFFENDED — don't try that again soon.)`; }
    t.locks[key] = lockout;
    msg = `[${title(verb)} FAILED] ${reason} ${tail}`;
  }
  t.event(msg);
  return msg;
}

// One turn. message '' = greet. Returns { reply, kind, learned, revealed, state } like POST api/talk.
export function takeTurn(data, npcId, message, state) {
  const npc = data.npcs.find(n => n.id === npcId);
  if (!npc) throw new Error(`No NPC ${npcId}`);
  state = { ...newState(), ...state };
  message = (message || '').trim();
  const t = new Table(data, npc, state);
  const before = [...t.known], secretsBefore = [...t.secretsKnown];
  const rng = new PyRandom(turnSeed(state.seed, state.turn));
  const cmd = message ? parseCommand(message) : null;
  if (message.startsWith('/') && !cmd) {
    return { reply: 'Only /persuade, /intimidate and /deceive (with an argument) work here; the other slash commands need the full game.',
      kind: 'note', learned: [], revealed: [], state };
  }
  let reply, kind;
  if (!message) {
    kind = 'greet';
    reply = extras(t, npcLine(data.lines, npc, 'Hello', rng), null);
    t.event(`${npc.name} says: "${reply}"`);
  } else if (cmd) {
    kind = 'check';
    t.event(`You try to ${cmd[0]} ${npc.name}: "${cmd[1]}"`);
    reply = persuade(t, cmd[0], rng);
  } else {
    kind = 'say';
    t.event(`You say to ${npc.name}: "${message}"`);
    reply = extras(t, npcLine(data.lines, npc, message, rng), message);
    t.event(`${npc.name} says: "${reply}"`);
    if (!HOSTILE.includes(npc.class)) t.modify(2);
  }
  const next = { ...state, turn: state.turn + 1, affinity: { ...state.affinity, [npcId]: t.rel },
    topics: t.known, secrets: t.secretsKnown, locks: t.locks };
  const name = id => data.topics.find(x => x.id === id).name;
  return { reply, kind, learned: t.known.filter(id => !before.includes(id)).map(name),
    revealed: t.secretsKnown.filter(id => !secretsBefore.includes(id)), state: next };
}
