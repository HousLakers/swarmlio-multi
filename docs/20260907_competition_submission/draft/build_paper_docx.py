#!/usr/bin/env python3
"""Build a reviewable Word version of paper_draft_v2 with embedded figures.

The source manuscript and figure assets are left untouched.  A temporary
Markdown view replaces SVG links with the companion PNG files so Word readers
without SVG support still receive every figure.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAPER_DIR = ROOT / "docs/20260907_competition_submission"
DRAFT = PAPER_DIR / "draft/paper_draft_v2.md"
OUT = PAPER_DIR / "draft/paper_draft_v2.docx"

source = DRAFT.read_text(encoding="utf-8")
# PNG is the compatibility path for Word.  The SVG/PDF files remain available
# in figures/v2 for publication layout and vector export.
source = re.sub(r"(figures/v2/fig[^)]+)\.svg", r"\1.png", source)
source = source.replace("../figures/v2/", str(PAPER_DIR / "figures/v2") + "/")

md = DRAFT.parent / ".paper_draft_v2_word.md"
md.write_text(source, encoding="utf-8")
try:
    cmd = [
        "pandoc", str(md),
        "--from", "gfm+tex_math_dollars",
        "--to", "docx",
        "--standalone",
        "--toc", "--toc-depth=2",
        "--wrap=none",
        "--resource-path", str(DRAFT.parent),
        "--resource-path", str(PAPER_DIR / "figures/v2"),
        "--metadata", "lang=zh-CN",
        "--metadata", "title=面向国产算力的多无人机具身智能感知与弹性探索系统",
        "--output", str(OUT),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)
finally:
    md.unlink(missing_ok=True)

print(OUT)
