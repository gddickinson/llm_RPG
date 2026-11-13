// Armoury & items: every item in data/items/*.json (api/items) and the crafting recipes (api/recipes).
import { route, app, api, esc, $ } from './core.js';
import { filterBar, opts, uniq, has } from './ui.js';

const RAR = ['common', 'uncommon', 'rare', 'epic', 'legendary'];

function row(i) {
  const b = Object.entries(i.bonuses).map(([k, v]) => `${k} ${v > 0 ? '+' : ''}${v}`).join(', ');
  const power = [i.damage != null && `dmg ${i.damage}${i.damage_kind ? ' ' + i.damage_kind : ''}`, i.armor != null && `AC ${i.armor}`,
    i.heal != null && `heals ${i.heal}`, i.spell && `casts ${i.spell.replace(/_/g, ' ')}`, i.charges && `${i.charges} charges`,
    i.two_handed && 'two-handed', b].filter(Boolean).join(' · ');
  return `<tr><td><b class="rar-${esc(i.rarity)}">${esc(i.name)}</b><br><span class="small mute">${esc(i.description)}</span></td>
    <td>${esc(i.type)}</td><td class="rar-${esc(i.rarity)}">${esc(i.rarity)}</td><td class="mono">${esc(power)}</td><td class="mono">${i.value ?? ''}</td></tr>`;
}

route('items', async () => {
  const [rows, recipes] = await Promise.all([api('/items'), api('/recipes')]);
  app().innerHTML = `<p class="kicker">Compendium</p><h1 class="glow">Armoury &amp; items</h1>
    <p class="lead">${rows.length} items from <code>data/items/*.json</code>. In the game, power comes from gear and
    companions more than from XP: weapons and armour are crafted, looted, repaired and enchanted.</p>
    <div id="fb"></div><p class="count" id="n"></p>
    <div class="scroll"><table><thead><tr><th>Item</th><th>Type</th><th>Rarity</th><th>Power</th><th>Value</th></tr></thead><tbody id="list"></tbody></table></div>
    <h2>Crafting recipes</h2>
    <p class="mute">${recipes.length} recipes from <code>data/recipes.json</code> (press K in the game).</p>
    <div class="scroll"><table><thead><tr><th>Makes</th><th>From</th><th>Skill</th><th>Station</th><th>Gold</th></tr></thead><tbody>
    ${recipes.map(r => `<tr><td><b>${esc(r.output)}</b></td><td>${r.ingredients.map(g => `${g.qty} x ${esc(g.name)}`).join(', ')}</td>
      <td>${esc(r.skill || '')}${r.min_skill ? ` ${r.min_skill}+` : ''}</td><td>${esc(r.station || '')}</td><td class="mono">${r.gold}</td></tr>`).join('')}
    </tbody></table></div>`;
  filterBar($('#fb'), [
    { id: 'q', label: 'Search', type: 'text', placeholder: 'name or description', wide: true },
    { id: 'type', label: 'Type', type: 'select', options: opts(uniq(rows.map(i => i.type))) },
    { id: 'rar', label: 'Rarity', type: 'select', options: opts(RAR) },
  ], f => {
    const shown = rows.filter(i => has(i, f.q, ['name', 'description']) && (!f.type || i.type === f.type) && (!f.rar || i.rarity === f.rar));
    $('#n').textContent = `${shown.length} of ${rows.length}`;
    $('#list').innerHTML = shown.map(row).join('') || '<tr><td colspan="5" class="mute">No item matches.</td></tr>';
  });
});
