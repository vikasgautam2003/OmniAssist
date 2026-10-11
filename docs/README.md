# Documents

Generated from the Markdown sources in the project root. Regenerate after any
change to those sources:

```bash
python3 tools/md2pdf.py FILE_GUIDE.md  docs/FILE_GUIDE.pdf  "OmniAssist - File Guide"
python3 tools/md2pdf.py LEARN_SHEET.md docs/LEARN_SHEET.pdf "OmniAssist - Learn Sheet"
python3 tools/md2pdf.py DESIGN_v0.3.md docs/DESIGN_v0.3.pdf "OmniAssist - v0.3 Design"
```

| File | Source | What it is |
|------|--------|------------|
| `FILE_GUIDE.pdf` | `FILE_GUIDE.md` | Every file: what it is, why it exists, where it fits |
| `LEARN_SHEET.pdf` | `LEARN_SHEET.md` | Concepts C1–C90 and decisions D1–D42, with rejected alternatives |
| `DESIGN_v0.3.pdf` | `DESIGN_v0.3.md` | The tool-use framework design, written before any code |

Requires `pymupdf` (already a dev dependency of the PDF tooling, installed with
`pip install pymupdf` if missing).
