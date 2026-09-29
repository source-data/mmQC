"""Draw the exp-02 and exp-03 arrangement diagrams as standalone SVGs.

    python experiments/draw_arrangements.py

Writes `arrangements.svg` into each experiment's directory. Boxes are skills, the
coloured blocks the instructions each carries, arrows are Skill invocations.
"""
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parents[1]

INK, MUTED, FRAME, BG = "#1f2328", "#59636e", "#8c959f", "#ffffff"
BLOCK = {  # fill, text
    "A": ("#dbe9fb", "#0b4a8b"),
    "B": ("#fde7cf", "#8a4b00"),
    "C": ("#d7f0dc", "#1a6b2d"),
    "D": ("#ece2fb", "#5b2c9a"),
}
BOX_W, BOX_H = 150, 76
FONT = "font-family='-apple-system, Segoe UI, Helvetica, Arial, sans-serif'"


class Svg:
    def __init__(self, width, height, title):
        self.w, self.h = width, height
        self.parts = [
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
            f"viewBox='0 0 {width} {height}' {FONT}>",
            f"<title>{escape(title)}</title>",
            "<defs><marker id='arrow' viewBox='0 0 10 10' refX='9' refY='5' "
            "markerWidth='7' markerHeight='7' orient='auto-start-reverse'>"
            f"<path d='M0,0 L10,5 L0,10 z' fill='{MUTED}'/></marker></defs>",
            f"<rect width='{width}' height='{height}' fill='{BG}'/>",
        ]

    def text(self, x, y, s, size=12, weight="normal", fill=INK, anchor="middle", style=""):
        self.parts.append(
            f"<text x='{x}' y='{y}' font-size='{size}' font-weight='{weight}' "
            f"fill='{fill}' text-anchor='{anchor}' {style}>{escape(s)}</text>"
        )

    def skill(self, x, y, name, version, blocks, kind=None):
        """A skill box: name, version, and the blocks of instructions it carries."""
        fill, stroke = ("#faf7ff", BLOCK["D"][1]) if kind == "D" else ("#f6f8fa", FRAME)
        self.parts.append(
            f"<rect x='{x}' y='{y}' width='{BOX_W}' height='{BOX_H}' rx='8' "
            f"fill='{fill}' stroke='{stroke}' stroke-width='1.2'/>"
        )
        cx = x + BOX_W / 2
        self.text(cx, y + 18, name, size=11.5, weight="600")
        self.text(cx, y + 32, version, size=10, fill=MUTED)
        pw, gap = 34, 6
        total = len(blocks) * pw + (len(blocks) - 1) * gap
        px = cx - total / 2
        for b in blocks:
            f, t = BLOCK[b[0]]
            self.parts.append(
                f"<rect x='{px}' y='{y + 42}' width='{pw}' height='22' rx='5' fill='{f}'/>"
            )
            self.text(px + pw / 2, y + 57, b, size=12, weight="700", fill=t)
            px += pw + gap
        return (cx, y, y + BOX_H)

    def arrow(self, a, b):
        """Caller a invokes callee b: from the bottom of a to the top of b."""
        (ax, _, ay), (bx, by, _) = a, b
        self.parts.append(
            f"<path d='M{ax},{ay} C{ax},{(ay + by) / 2} {bx},{(ay + by) / 2} {bx},{by - 2}' "
            f"fill='none' stroke='{MUTED}' stroke-width='1.4' marker-end='url(#arrow)'/>"
        )

    def frame(self, x, y, w, h, label="one session"):
        self.parts.append(
            f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='12' fill='none' "
            f"stroke='{FRAME}' stroke-width='1' stroke-dasharray='5 4'/>"
        )
        self.text(x + 10, y + 14, label, size=10, fill=MUTED, anchor="start")

    def legend(self, y, extra=()):
        x = 24
        items = [("A", "panel identification"), ("B", "panel classification"),
                 ("C", "the check itself"), *extra]
        for b, label in items:
            f, t = BLOCK[b]
            self.parts.append(f"<rect x='{x}' y='{y - 13}' width='26' height='18' rx='4' fill='{f}'/>")
            self.text(x + 13, y + 1, b, size=11, weight="700", fill=t)
            self.text(x + 33, y, label, size=11.5, fill=INK, anchor="start")
            x += 40 + 7.2 * len(label)
        self.parts.append(
            f"<path d='M{x},{y - 4} L{x + 34},{y - 4}' stroke='{MUTED}' stroke-width='1.4' "
            f"marker-end='url(#arrow)'/>"
        )
        self.text(x + 42, y, "invokes (Skill tool, named in prose)", size=11.5, anchor="start")

    def save(self, path):
        self.parts.append("</svg>")
        Path(path).write_text("\n".join(self.parts) + "\n", encoding="utf-8")
        print("wrote", path)


# --------------------------------------------------------------------------
# exp-02: four arrangements of one check, one session each.
# --------------------------------------------------------------------------
s = Svg(1000, 560, "exp-02 — four arrangements of one check")
s.text(24, 30, "exp-02 — delegation depth: the same instructions, spread over 1, 2 or 3 skills",
       size=16, weight="700", anchor="start")
s.text(24, 50, "One session per example per check. Each check below is micrograph-scale-bar, "
       "individual-data-points or error-bars-defined; the arm directory is in brackets.",
       size=11.5, fill=MUTED, anchor="start")

cols = [
    ("A|B|C", "monolith — baseline", "pinned",
     [("<check>", "v1", ["A", "B", "C"])],
     "classify-panels, identify-panels, 2 other checks", None),
    ("A ← B|C", "identification split off", "<check>@v2",
     [("<check>", "v2", ["B", "C"]), ("identify-panels", "v1", ["A"])],
     "classify-panels, 2 other checks", "classify-panels invoked 11/570"),
    ("A|B ← C", "the check split off", "<check>@v3",
     [("<check>", "v3", ["C"]), ("classify-panels", "v1", ["A", "B"])],
     "identify-panels, 2 other checks", "identify-panels invoked 40/570"),
    ("A ← B ← C", "both split, as a chain", "classify-panels@v2-<check>@v3",
     [("<check>", "v3", ["C"]), ("classify-panels", "v2", ["B"]),
      ("identify-panels", "v1", ["A"])],
     "2 other checks", None),
]
for i, (label, sub, arm, chain, idle, stray) in enumerate(cols):
    x0 = 20 + i * 245
    cx = x0 + 112
    s.text(cx, 88, label, size=15, weight="700")
    s.text(cx, 105, sub, size=11, fill=MUTED)
    s.text(cx, 120, f"[{arm}]", size=9.5, fill=MUTED)
    s.frame(x0, 132, 225, 332)
    prev = None
    for j, (name, ver, blocks) in enumerate(chain):
        box = s.skill(cx - BOX_W / 2, 158 + j * 100, name, ver, blocks)
        if prev:
            s.arrow(prev, box)
        prev = box
    # What whole-checklist assembly also put in the session.
    s.text(cx, 482, "also in the session, never named:", size=10, fill=MUTED)
    s.text(cx, 497, idle, size=10, fill=MUTED, style="font-style='italic'")
    if stray:
        s.text(cx, 513, stray, size=10, weight="600", fill="#9a3412")

s.legend(532, ())
s.text(24, 552, "exp-02 ran with whole-checklist assembly: every skill of the checklist was in "
       "every session. Closure assembly, the default since exp-03, removes the grey line.",
       size=10.5, fill=MUTED, anchor="start")
s.save(REPO / "experiments/exp-02-delegation-depth/arrangements.svg")


# --------------------------------------------------------------------------
# exp-03: two arrangements x (per check, fan-out).
# --------------------------------------------------------------------------
CHECKS = ["micrograph-scale-bar", "individual-data-points", "error-bars-defined"]
s = Svg(1020, 830, "exp-03 — per-check dispatch against fan-out through D")
s.text(24, 30, "exp-03 — checklist entry: each check alone, or all three through one entry skill D",
       size=16, weight="700", anchor="start")
s.text(24, 50, "Each dashed frame is one session, and holds exactly the skills drawn in it "
       "(closure assembly). Each row compares its two columns, per check.",
       size=11.5, fill=MUTED, anchor="start")
s.text(262, 84, "per check — the control", size=14, weight="700")
s.text(262, 101, "3 sessions per figure", size=11, fill=MUTED)
s.text(772, 84, "fan-out — through D", size=14, weight="700")
s.text(772, 101, "1 session per figure  [do-fig-checklist]", size=11, fill=MUTED)
s.parts.append(f"<line x1='510' y1='75' x2='510' y2='790' stroke='#d0d7de' stroke-width='1'/>")

LX = [26, 188, 350]          # left column box x
RX = [540, 697, 854]         # right column box x


def row_title(y, label, sub, left_arm, right_arm):
    s.text(24, y, label, size=14, weight="700", anchor="start")
    s.text(24, y + 17, sub, size=11, fill=MUTED, anchor="start")
    s.text(262, y + 38, f"arm: {left_arm}", size=10, fill=MUTED)
    s.text(772, y + 38, f"arm: {right_arm}", size=10, fill=MUTED)


# Row 1: A|B|C_i -- the checks are monoliths.
row_title(128, "A|B|C_i", "each check carries A, B and its own C", "pinned", "pinned")
for x, name in zip(LX, CHECKS):
    s.frame(x - 4, 270, BOX_W + 8, BOX_H + 30)
    s.skill(x, 290, name, "v1", ["A", "B", "C"])
s.frame(RX[0] - 8, 176, RX[2] + BOX_W - RX[0] + 16, 202)
d = s.skill(697, 188, "do-fig-checklist", "v1  ·  D", ["D"], kind="D")
for x, name in zip(RX, CHECKS):
    s.arrow(d, s.skill(x, 290, name, "v1", ["A", "B", "C"]))
s.text(516, 334, "vs", size=13, weight="700", fill=MUTED)

# Row 2: A|B <- C_i -- each check calls classify-panels.
row_title(412, "A|B ← C_i", "each check carries only C, and calls classify-panels for A and B",
          "<check>@v3", "all three checks @v3")
for x, name in zip(LX, CHECKS):
    s.frame(x - 4, 556, BOX_W + 8, 220)
    c = s.skill(x, 576, name, "v3", ["C"])
    s.arrow(c, s.skill(x, 686, "classify-panels", "v1", ["A", "B"]))
s.frame(RX[0] - 8, 460, RX[2] + BOX_W - RX[0] + 16, 316)
d = s.skill(697, 472, "do-fig-checklist", "v1  ·  D", ["D"], kind="D")
cp = (772, 686, 686 + BOX_H)
checks = [s.skill(x, 576, name, "v3", ["C"]) for x, name in zip(RX, CHECKS)]
s.skill(697, 686, "classify-panels", "v1", ["A", "B"])
for c in checks:
    s.arrow(d, c)
    s.arrow(c, cp)
s.text(516, 666, "vs", size=13, weight="700", fill=MUTED)

s.legend(812, (("D", "entry skill"),))
s.save(REPO / "experiments/exp-03-checklist-entry/arrangements.svg")
