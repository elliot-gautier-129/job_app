"""Deterministic Unicode → LaTeX escaping for KB text (pdflatex, Overleaf-safe).

KB text is stored as plain Unicode. Everything that reaches the .tex goes
through escape(), so the model never writes raw LaTeX.
"""
from __future__ import annotations

import unicodedata

_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"$\sim$",
    "^": r"\textasciicircum{}",
    "<": r"\textless{}",
    ">": r"\textgreater{}",
    "|": r"\textbar{}",
    "–": "--",            # – en dash
    "—": "---",           # — em dash
    "∼": r"$\sim$",       # ∼
    "−": r"$-$",          # − minus
    "×": r"$\times$",     # ×
    "→": r"$\rightarrow$",  # →
    "≈": r"$\approx$",    # ≈
    "£": r"\pounds{}",    # £
    "€": r"\texteuro{}",  # €
    "’": "'",             # ’
    "‘": "`",             # ‘
    "“": "``",            # “
    "”": "''",            # ”
    " ": "~",             # non-breaking space
    "…": r"\ldots{}",     # …
    "·": r"\textperiodcentered{}",  # ·
}


def escape(text: str) -> str:
    """Escape plain Unicode text for LaTeX body content.

    Latin letters with accents (é, ü, ç …) pass through: pdflatex reads UTF-8
    by default, on Overleaf too. Any other unmapped non-ASCII character raises
    ValueError rather than producing a .tex that may not compile.
    """
    out = []
    for ch in text:
        if ch in _MAP:
            out.append(_MAP[ch])
        elif ord(ch) < 128:
            out.append(ch)
        elif unicodedata.category(ch).startswith("L") and ord(ch) < 0x250:
            out.append(ch)
        else:
            raise ValueError(f"no LaTeX mapping for character {ch!r} (U+{ord(ch):04X}) in: {text!r}")
    return "".join(out)


def escape_url(url: str) -> str:
    """Escape a URL for the first argument of \\href."""
    return url.replace("\\", "/").replace("%", r"\%").replace("#", r"\#")


def comment(text: str) -> str:
    """A single-line LaTeX comment (never reaches the PDF)."""
    return "% " + " ".join(text.split())
