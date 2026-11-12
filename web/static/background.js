// Subtle drifting embers behind the pages (off under prefers-reduced-motion). Purely decorative.
import { rng } from './core.js';

export function background(canvas) {
  if (!canvas || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const ctx = canvas.getContext('2d'), r = rng(20);
  let w = 0, h = 0;
  const resize = () => { w = canvas.width = innerWidth; h = canvas.height = innerHeight; };
  resize(); addEventListener('resize', resize);
  const motes = Array.from({ length: 46 }, () => ({ x: r(), y: r(), v: 0.0004 + r() * 0.0009, s: 0.6 + r() * 1.8, p: r() * 6.28 }));
  const tick = t => {
    ctx.clearRect(0, 0, w, h);
    for (const m of motes) {
      m.y -= m.v; if (m.y < -0.02) { m.y = 1.02; m.x = r(); }
      const x = (m.x + 0.01 * Math.sin(t / 1400 + m.p)) * w, y = m.y * h;
      ctx.fillStyle = `rgba(255,${150 + (m.s * 30 | 0)},80,${0.25 + 0.25 * Math.sin(t / 700 + m.p) ** 2})`;
      ctx.beginPath(); ctx.arc(x, y, m.s, 0, 6.283); ctx.fill();
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
