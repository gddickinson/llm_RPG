// Shared bits for the compendium pages: a filter bar wired to a render function, and small formatters.
import { esc, $ } from './core.js';

// fields: [{ id, label, type: 'text'|'select', options: [[value, label]], wide }]; onChange(values) re-renders.
export function filterBar(host, fields, onChange) {
  host.innerHTML = `<div class="filters">${fields.map(f => `<div class="${f.wide ? 'wide' : ''}">
    <label for="f-${f.id}">${esc(f.label)}</label>${f.type === 'select'
      ? `<select id="f-${f.id}">${f.options.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join('')}</select>`
      : `<input id="f-${f.id}" type="search" placeholder="${esc(f.placeholder || '')}">`}</div>`).join('')}</div>`;
  const read = () => Object.fromEntries(fields.map(f => [f.id, $(`#f-${f.id}`, host).value]));
  for (const f of fields) $(`#f-${f.id}`, host).addEventListener('input', () => onChange(read()));
  onChange(read());
}

export const opts = (values, all = 'All') => [['', all], ...values.map(v => [v, v])];
export const uniq = rows => [...new Set(rows.filter(v => v != null && v !== ''))].sort();
export const has = (row, q, keys) => !q || keys.some(k => String(row[k] ?? '').toLowerCase().includes(q.toLowerCase()));
export const stat = (label, v) => v == null || v === '' || v === false ? '' : `<span class="stat">${esc(label)} ${esc(v === true ? '' : v)}</span>`;
