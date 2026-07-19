"""GAP.7 the cold-open prologue overlay — a quiet full-screen framing
before the first step. Thin pygame draw over `engine.intro.intro_text`.
"""

import pygame


def _font(size, bold=False):
    try:
        if not pygame.font.get_init():
            pygame.font.init()
        return pygame.font.SysFont("georgia,times,serif", size, bold=bold)
    except Exception:
        return None


def draw_intro(gui):
    screen = gui.screen
    W, H = screen.get_size()
    screen.fill((8, 8, 12))
    # a soft vignette frame
    pygame.draw.rect(screen, (28, 26, 38),
                     pygame.Rect(40, 40, W - 80, H - 80), border_radius=10)
    pygame.draw.rect(screen, (90, 84, 120),
                     pygame.Rect(40, 40, W - 80, H - 80), 1, border_radius=10)

    try:
        from engine.intro import intro_text
        title, lines = intro_text(gui.engine)
    except Exception:
        title, lines = ("A New Tale", ["Your journey begins."])

    tf = _font(34, bold=True)
    bf = _font(19)
    sf = _font(15)
    if tf is not None:
        t = tf.render(title, True, (235, 220, 160))
        screen.blit(t, ((W - t.get_width()) // 2, 92))
        pygame.draw.line(screen, (110, 100, 140),
                         (W // 2 - 160, 140), (W // 2 + 160, 140), 1)

    if bf is not None:
        y = 176
        maxw = W - 220
        for line in lines:
            if not line:
                y += 14
                continue
            for seg in _wrap(line, bf, maxw):
                r = bf.render(seg, True, (214, 214, 222))
                screen.blit(r, ((W - r.get_width()) // 2, y))
                y += bf.get_height() + 4

    if sf is not None:
        prompt = "Press any key to begin"
        r = sf.render(prompt, True, (170, 170, 190))
        screen.blit(r, ((W - r.get_width()) // 2, H - 88))


def _wrap(text, font, maxw):
    words = text.split(" ")
    out, cur = [], ""
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
