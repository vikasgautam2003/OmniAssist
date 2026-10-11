# -*- coding: utf-8 -*-
"""Markdown -> PDF via PyMuPDF's Story engine.

Handles headings, paragraphs, bullets, fenced code and tables -- enough for the
project's own documents. Deliberately not a general Markdown implementation.
"""
import html as _html
import re
import sys

import pymupdf

SRC, OUT, TITLE = sys.argv[1], sys.argv[2], sys.argv[3]


EMOJI = re.compile("[\U0001F000-\U0001FAFF\uFE0F\u2728\u2705\u274C\u2B50]")


def inline(text: str) -> str:
    text = EMOJI.sub("", text).strip()
    t = _html.escape(text)
    # NOTE: ~~strikethrough~~ is left as literal tildes on purpose. Removing
    # the markers narrows a table cell enough that PyMuPDF's table layout
    # stops converging and place() never returns False.
    t = re.sub(r"`([^`]+)`", r"<span class='c'>\1</span>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)([^*]+?)\*(?!\*)", r"<i>\1</i>", t)
    return t


blocks: list[str] = []
buf: list[str] = []
items: list[str] = []
rows: list[list[str]] = []
code: list[str] = []
in_code = False


def flush() -> None:
    global rows
    if buf:
        blocks.append("<p>%s</p>" % inline(" ".join(buf)))
        buf.clear()
    if items:
        blocks.append("<ul>%s</ul>" % "".join(f"<li>{i}</li>" for i in items))
        items.clear()
    if rows:
        head, body = rows[0], rows[1:]
        th = "".join(f"<th>{inline(c)}</th>" for c in head)
        tb = "".join(
            "<tr>%s</tr>" % "".join(f"<td>{inline(c)}</td>" for c in r) for r in body
        )
        blocks.append(f"<table><tr>{th}</tr>{tb}</table>")
        rows = []


for raw in open(SRC, encoding="utf-8").read().splitlines():
    line = raw.rstrip()
    s = line.strip()

    if s.startswith("```"):
        if in_code:
            body = "<br/>".join(
                _html.escape(c).replace(" ", "&nbsp;") for c in code
            )
            blocks.append(f"<p class='pre'>{body}</p>")
            code.clear()
        else:
            flush()
        in_code = not in_code
        continue
    if in_code:
        code.append(line)
        continue

    if not s:
        flush()
    elif s.startswith("#### "):
        flush(); blocks.append(f"<h4>{inline(s[5:])}</h4>")
    elif s.startswith("### "):
        flush(); blocks.append(f"<h3>{inline(s[4:])}</h3>")
    elif s.startswith("## "):
        flush(); blocks.append(f"<h2>{inline(s[3:])}</h2>")
    elif s.startswith("# "):
        flush(); blocks.append(f"<h1>{inline(s[2:])}</h1>")
    elif s == "---":
        flush()
    elif s.startswith("|") and s.endswith("|"):
        if buf or items:
            flush()
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue
        rows.append(cells)
    elif re.match(r"^[-*]\s+", s):
        if buf:
            flush()
        items.append(inline(re.sub(r"^[-*]\s+", "", s)))
    elif items and raw.startswith("  "):
        items[-1] += " " + inline(s)
    else:
        if items or rows:
            flush()
        buf.append(s)
flush()

CSS = """
body  { font-family: serif; font-size: 10.5px; color: #16181d; }
h1    { font-size: 21px; text-align: center; margin-bottom: 1px; }
h2    { font-size: 15px; color: #8a1419; margin-top: 17px; margin-bottom: 2px; }
h3    { font-size: 11.5px; color: #1d3f73; margin-top: 12px; margin-bottom: 1px; }
h4    { font-size: 11px; color: #1d3f73; margin-top: 10px; margin-bottom: 1px; }
p     { line-height: 1.5; margin-top: 0px; margin-bottom: 7px; }
.pre  { font-family: monospace; font-size: 8.5px; line-height: 1.25;
        color: #333333; margin-bottom: 8px; }
.c    { font-family: monospace; font-size: 9.5px; }
ul    { margin-top: 0px; margin-bottom: 7px; }
li    { line-height: 1.45; margin-bottom: 3px; }
table { width: 100%; margin-bottom: 9px; }
th    { font-size: 9.5px; text-align: left; background-color: #eeeeee;
        border: 1px solid #cccccc; }
td    { font-size: 9.5px; border: 1px solid #cccccc; }
"""

PAGE = pymupdf.paper_rect("a4")
M = 50
FRAME = PAGE + (M, M, -M, -(M + 14))

MAX_PAGES = 200

story = pymupdf.Story(html=f"<body>{''.join(blocks)}</body>", user_css=CSS)
writer = pymupdf.DocumentWriter(OUT)
pages = 0
while True:
    dev = writer.begin_page(PAGE)
    more, filled = story.place(FRAME)
    story.draw(dev)
    writer.end_page()
    pages += 1
    if not more:
        break
    if pages >= MAX_PAGES:
        raise RuntimeError(
            f"stopped at {MAX_PAGES} pages: a block does not fit the frame"
        )
writer.close()

doc = pymupdf.open(OUT)
for i, page in enumerate(doc, 1):
    page.insert_text((M, PAGE.height - M + 12), TITLE, fontsize=7.5,
                     fontname="helv", color=(0.55, 0.55, 0.55))
    page.insert_text((PAGE.width - M - 34, PAGE.height - M + 12),
                     f"{i} / {len(doc)}", fontsize=7.5, fontname="helv",
                     color=(0.55, 0.55, 0.55))
doc.save(OUT, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
print(f"{OUT}  ({len(doc)} pages)")
