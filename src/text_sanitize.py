"""
Text sanitization for safe `st.markdown` rendering.

Normalises whitespace anomalies, converts LLM-typical LaTeX delimiters
to Streamlit-compatible forms, and strips legacy escape artifacts.
"""

import re

_LATEX_DISPLAY_OPEN_RE = re.compile(r"\\\[")
_LATEX_DISPLAY_CLOSE_RE = re.compile(r"\\\]")
_LATEX_INLINE_OPEN_RE = re.compile(r"\\\(")
_LATEX_INLINE_CLOSE_RE = re.compile(r"\\\)")


def sanitize_text(text: str) -> str:
    """Normalize *text* for safe `st.markdown` rendering.

    * Collapses thin-space (``U+202F``) and NBSP (``U+00A0``) to
      regular space — prevents accidental LaTeX-trigger when a
      whitespace character after ``$`` is not recognised as a
      word-break (e.g. ``R$\\u202f45.000``).
    * Converts ``\\\\(…\\\\)`` → ``$…$`` and ``\\\\[…\\\\]`` →
      ``$$…$$`` because Streamlit's markdown parser only accepts the
      ``$`` / ``$$`` syntax, not the raw LaTeX bracket forms.
    * Strips any legacy ``\\\\$`` double-escape left over from
      pre‑v1.5.3 sessions.
    """
    text = text.replace("\u202f", " ").replace("\u00a0", " ")
    text = _LATEX_DISPLAY_OPEN_RE.sub("$$", text)
    text = _LATEX_DISPLAY_CLOSE_RE.sub("$$", text)
    text = _LATEX_INLINE_OPEN_RE.sub("$", text)
    text = _LATEX_INLINE_CLOSE_RE.sub("$", text)
    text = text.replace("\\\\$", "$")
    return text
