"""T4.3 the VICTORY screen — the campaign's missing payoff.

Winning fired one `[Legend]` line and play just carried on. This shows a
full-screen ENDING (the chronicle of the age you wrote) with a real
choice: begin New Game+ (carry your legend into a harsher world), keep
playing this won realm, or lay the story to rest. Thin pygame draw over
`engine.campaign.summary`.
"""

import pygame


def _font(size, bold=False):
    try:
        if not pygame.font.get_init():
            pygame.font.init()
        return pygame.font.SysFont("georgia,times,serif", size, bold=bold)
    except Exception:
        return None


def draw_victory(gui) -> None:
    screen = gui.screen
    W, H = screen.get_size()
    screen.fill((10, 9, 14))
    pygame.draw.rect(screen, (30, 26, 20),
                     pygame.Rect(36, 36, W - 72, H - 72), border_radius=10)
    pygame.draw.rect(screen, (200, 170, 90),
                     pygame.Rect(36, 36, W - 72, H - 72), 2, border_radius=10)

    tf = _font(38, bold=True)
    bf = _font(18)
    of = _font(20, bold=True)
    if tf is not None:
        t = tf.render("VICTORY", True, (240, 210, 120))
        screen.blit(t, ((W - t.get_width()) // 2, 66))

    try:
        from engine.campaign import summary
        lines = summary(gui.engine)
    except Exception:
        lines = ["The Elder Wyrm is slain. The age is won."]

    if bf is not None:
        y = 128
        maxw = W - 200
        for line in lines[:16]:
            if not line or "THE SHADOW LIFTS" in line:
                y += 10
                continue
            for seg in _wrap(line, bf, maxw):
                r = bf.render(seg, True, (216, 214, 206))
                screen.blit(r, ((W - r.get_width()) // 2, y))
                y += bf.get_height() + 3

    if of is not None:
        opts = [("[N]  Begin New Game+", (150, 220, 150)),
                ("[C]  Keep playing this realm", (200, 200, 210)),
                ("[Esc]  Lay the story to rest", (200, 160, 160))]
        oy = H - 140
        for text, col in opts:
            r = of.render(text, True, col)
            screen.blit(r, ((W - r.get_width()) // 2, oy))
            oy += 30


def _wrap(text, font, maxw):
    words, out, cur = text.split(" "), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if font.size(trial)[0] <= maxw:
            cur = trial
        else:
            if cur:
                out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out or [text]
