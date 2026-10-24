"""Draw harness-overview.svg: python draw_harness_overview.py harness-overview.svg"""
import sys
from xml.sax.saxutils import escape

W, H = 960, 664
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
INK, MUTED, LINE = "#1f2937", "#6b7280", "#374151"
VIOLET, VIOLET_BG = "#6d28d9", "#f5f3ff"
TEAL, TEAL_BG = "#0f766e", "#f0fdfa"
ORANGE, ORANGE_BG = "#c2410c", "#fff7ed"
out = []


def text(x, y, s, size=10.5, color=MUTED, weight="normal", anchor="start", mono=False):
    out.append(f'<text x="{x}" y="{y}" font-family="{MONO if mono else SANS}" font-size="{size}" '
               f'fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(s)}</text>')


def rect(x, y, w, h, fill="#ffffff", stroke="#d1d5db", rx=8, dash=None, width=1, opacity=1):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" '
               f'stroke-width="{width}" stroke-opacity="{opacity}"{d}/>')


def arrow(x1, y1, x2, y2, color=MUTED, label=None, lx=None, ly=None, anchor="middle"):
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.5" '
               f'marker-end="url(#head-{color[1:]})"/>')
    if label:
        text(lx if lx is not None else (x1 + x2) / 2, ly if ly is not None else (y1 + y2) / 2 - 6,
             label, 10.5, color, "bold", anchor)


def card(x, y, w, title, sub, mono_title=True):
    rect(x, y, w, 40, rx=6)
    text(x + 10, y + 17, title, 11, INK, mono=mono_title)
    text(x + 10, y + 32, sub)


# --- title ---
text(W / 2, 30, "mmqc-harness: from a published checklist to one figure's answer", 16, INK, "bold", "middle")
text(W / 2, 48, "the same code runs mmQC's benchmark and the application, so a benchmark score describes production",
     11, MUTED, anchor="middle")

# --- top band: where the checklist comes from ---
top = 72
cols = [(20, "mmQC repository", "develops, benchmarks, publishes", LINE, "#f9fafb"),
        (340, "Langfuse", "the boundary: production only", VIOLET, VIOLET_BG),
        (660, "Application", "e.g. soda-curation", TEAL, TEAL_BG)]
for x, title, sub, color, bg in cols:
    text(x + 140, top + 14, title, 14, color, "bold", "middle")
    text(x + 140, top + 29, sub, anchor="middle")
    rect(x, top + 38, 280, 168, fill=bg, stroke=color, rx=10, opacity=0.45)

x = 32
card(x, top + 50, 256, "fig-checklist/", "skills in versions, contracts")
card(x, top + 98, 256, "version-manifest.yaml", "pins the production version of each")
card(x, top + 146, 256, "publish_langfuse_skills.py", "checks the production rules, publishes")

x = 352
card(x, top + 50, 256, "skills/fig-checklist/<skill>", "one prompt per skill, 13 in all")
card(x, top + 98, 256, "label: production", "one release: the skill set's digest")
card(x, top + 146, 256, "SKILL.md + config", "schema, eval-manifest, model defaults")

x = 672
card(x, top + 50, 256, "mmqc-skills pull", "atomic; verified before it is swapped in")
card(x, top + 98, 256, "skills/fig-checklist/", "local copy + release.json (hashes)")
card(x, top + 146, 256, "mmqc-skills verify | status", "offline check · newer release?")

arrow(301, top + 120, 338, top + 120, VIOLET, "publish", ly=top + 112)
arrow(621, top + 120, 658, top + 120, TEAL, "pull", ly=top + 112)

# --- bottom band: one figure ---
band = 300
rect(20, band, 920, 340, fill="#ffffff", stroke=LINE, rx=12, opacity=0.35)
text(36, band + 22, "per figure", 13, INK, "bold")
text(106, band + 22, "— one session, sharing nothing with any other; run many concurrently", 11, MUTED)

# input
ix, iy = 36, band + 46
rect(ix, iy, 190, 120, fill="#f9fafb", stroke="#d1d5db", rx=8)
text(ix + 12, iy + 20, "figure file + caption", 11, INK, "bold")
text(ix + 12, iy + 38, "TIFF, PDF, EPS, PNG, JPEG, …")
text(ix + 12, iy + 62, "figure_parts", 11, INK, mono=True)
text(ix + 12, iy + 78, "converted once:")
text(ix + 12, iy + 93, "300 dpi · 2,048 px · JPEG 80")
text(ix + 12, iy + 108, "sent as bytes, never re-encoded")

# runtime (ephemeral)
rx_, ry_, rw_, rh_ = 262, band + 40, 428, 280
rect(rx_, ry_, rw_, rh_, fill=ORANGE_BG, stroke=ORANGE, rx=10, dash="6 4", width=1.5)
text(rx_ + 14, ry_ + 20, "ephemeral runtime", 12.5, ORANGE, "bold")
text(rx_ + 14, ry_ + 36, "created per figure under parent, sealed, deleted after — even on failure", 10.5, ORANGE)
rows = [(".claude/skills/", "the entry point's closure, one version each"),
        ("CLAUDE.md", "one tool, nothing to open"),
        ("input/", "staged content; never gold or contracts"),
        ("agent-home/", "the transcript stays inside")]
for i, (name, what) in enumerate(rows):
    y = ry_ + 60 + i * 19
    text(rx_ + 16, y, name, 11, INK, mono=True)
    text(rx_ + 132, y, what)
# session inside the runtime
sx, sy, sw, sh = rx_ + 14, ry_ + 146, rw_ - 28, 120
rect(sx, sy, sw, sh, fill="#ffffff", stroke=ORANGE, rx=8, width=1)
text(sx + 12, sy + 20, "Claude agent session", 12, INK, "bold")
text(sx + 12, sy + 38, "dispatched with the entry point; it calls the other skills itself")
text(sx + 12, sy + 56, "tools: Skill only — no shell, files, network or subagents")
text(sx + 12, sy + 74, "content arrives in the request: caption, then the figure")
text(sx + 12, sy + 92, "answer constrained to the entry point's schema")
text(sx + 12, sy + 108, "model and turn limit from model-defaults.yaml")

# outputs
ox, oy = 726, band + 46
rect(ox, oy, 198, 196, fill=TEAL_BG, stroke=TEAL, rx=8, opacity=0.6)
text(ox + 12, oy + 20, "run_session returns", 11, INK, "bold")
outs = [("answer", "valid per the schema;"), ("", "one row per panel"),
        ("trace", "skills invoked, in order"),
        ("audit", "tool calls, cost, tokens;"), ("", "SHA-256 of each image")]
y = oy + 44
for name, what in outs:
    if name:
        text(ox + 12, y, name, 11, INK, mono=True)
    text(ox + 62, y, what)
    y += 19 if not name else 17
text(ox + 12, oy + 168, "written to artifacts/ too:", 10.5, MUTED)
text(ox + 12, oy + 184, "copy out before teardown", 10.5, MUTED)

# arrows: input -> runtime, runtime -> outputs, local copy -> runtime
arrow(227, iy + 60, 260, iy + 60, LINE)
arrow(691, oy + 98, 724, oy + 98, TEAL)
arrow(676, top + 207, 676, ry_ - 1, TEAL)
text(686, band + 16, "assemble_runtime", 11, TEAL, mono=True)
text(686, band + 31, "copies the closure of skills in", 10.5, TEAL)

defs = "".join(
    f'<marker id="head-{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
    f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
    for c in (MUTED, LINE, VIOLET, TEAL, ORANGE))
label = ("mmqc-harness: mmQC publishes a production checklist to Langfuse; an application pulls a verified local "
         "copy with mmqc-skills; per figure, the figure is converted once, a throwaway runtime holds the closure "
         "of skills and a sealed agent session with only the Skill tool, and run_session returns the validated "
         "answer, the skill trace and an audit with cost and image fingerprints; the runtime is then deleted")
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
       f'aria-label="{escape(label)}">\n<defs>{defs}</defs>\n<rect width="{W}" height="{H}" fill="#ffffff"/>\n'
       + "\n".join(out) + "\n</svg>\n")
open(sys.argv[1], "w").write(svg)
print("written", sys.argv[1])
