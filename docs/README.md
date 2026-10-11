# Documents

Generated from the Markdown sources in the project root. Regenerate after any
change to those sources:

```bash
python3 tools/md2pdf.py FILE_GUIDE.md  docs/FILE_GUIDE.pdf  "OmniAssist - File Guide"
python3 tools/md2pdf.py LEARN_SHEET.md docs/LEARN_SHEET.pdf "OmniAssist - Learn Sheet"
```

| File | Source | What it is |
|------|--------|------------|
| `FILE_GUIDE.pdf` | `FILE_GUIDE.md` | Every file: what it is, why it exists, where it fits |
| `LEARN_SHEET.pdf` | `LEARN_SHEET.md` | Concepts C1–C75 and decisions D1–D30, with rejected alternatives |

Requires `pymupdf` (already a dev dependency of the PDF tooling, installed with
`pip install pymupdf` if missing).
