// Node test: the JS conversation engine (talk_engine.js + py_random.js) must reproduce, turn by turn, conversations
// recorded from the repo's Python heuristic dialog (web/talk.py): reply text, kind, learned topics, revealed secrets
// and the whole state. Fixture: tests/fixtures/talk_fixture.json (python scripts/make_talk_fixture.py).
// Run: node web/static/talk_engine.test.mjs
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { takeTurn, parseCommand, turnSeed } from './talk_engine.js';
import { PyRandom } from './py_random.js';

const here = fileURLToPath(new URL('.', import.meta.url));
const fx = JSON.parse(readFileSync(here + '../../tests/fixtures/talk_fixture.json', 'utf8'));
let fails = 0, checks = 0;
const ok = (cond, msg) => { checks++; if (!cond) { fails++; if (fails < 25) console.error('FAIL', msg); } };
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function check(r, want, label) {
  ok(r.reply === want.reply, `${label}: reply\n  js: ${JSON.stringify(r.reply)}\n  py: ${JSON.stringify(want.reply)}`);
  ok(r.kind === want.kind, `${label}: kind ${r.kind} vs ${want.kind}`);
  ok(same(r.learned, want.learned), `${label}: learned ${r.learned} vs ${want.learned}`);
  ok(same(r.revealed, want.revealed), `${label}: revealed ${r.revealed} vs ${want.revealed}`);
  ok(same(r.state, want.state), `${label}: state\n  js: ${JSON.stringify(r.state)}\n  py: ${JSON.stringify(want.state)}`);
}

let turns = 0;
for (const c of fx.cases) {
  let state = c.start;
  c.turns.forEach((want, i) => {
    const r = takeTurn(fx.data, c.npc, want.message, state);
    check(r, want, `${c.npc} seed ${c.start.seed} turn ${i} ${JSON.stringify(want.message)}`);
    state = want.state;                              // stay on the Python path even after a mismatch
    turns++;
  });
}
let state = fx.journey.length ? { seed: 7, turn: 0, affinity: {}, topics: [], secrets: [], locks: {}, stats: fx.data.default_stats } : null;
fx.journey.forEach((want, i) => {
  const r = takeTurn(fx.data, want.npc, want.message, state);
  check(r, want, `journey ${i} ${want.npc} ${JSON.stringify(want.message)}`);
  state = want.state;
  turns++;
});

// a few unit checks
ok(same(parseCommand('/Persuade  give me a discount '), ['persuade', 'give me a discount']), 'parseCommand');
ok(parseCommand('/persuade') === null, 'parseCommand without argument');
ok(turnSeed(5, 3) === 5003, 'turnSeed');
const r = new PyRandom(0);
ok([r.randint(1, 20), r.randint(1, 20), r.randint(1, 20)].join() === '13,14,2', 'PyRandom(0).randint(1,20) x3 = 13,14,2 (CPython)');

console.log(`talk engine: ${turns} recorded turns, ${checks} checks, ${fails} failures`);
process.exit(fails ? 1 : 0);
