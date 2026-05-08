"""
Text sanitization for safe `st.markdown` rendering.

Normalises whitespace anomalies, converts LLM-typical LaTeX delimiters
to Streamlit-compatible forms (paired matching only), escapes
currency-pattern dollar signs, and strips legacy escape artifacts.

Architecture
------------
* ``sanitize_token`` — light-weight, per-chunk processor for streaming.
  Collapses whitespace, strips legacy ``\\\\$``, and escapes
  currency-pattern ``$`` (e.g. ``R$ 100``, ``$50``).

* ``sanitize_text`` — full-string processor called *after* streaming
  completes, and again on history re-render (idempotent).  Converts
  paired ``\\\\(…\\\\)`` → ``$…$`` and ``\\\\[…\\\\]`` → ``$$…$$``,
  escapes currency-pattern ``$``, then strips backslashes from any
  remaining unmatched delimiters.
"""

import re

# ── Currency-pattern dollar sign ──
# $ not preceded by \\, followed by optional whitespace then digit.
# Matches: R$ 100, R$100, $50 — always currency, never math.
# Preserves: $x^2$, $\frac{a}{b}$ — $ followed by letter/command.
_CURRENCY_DOLLAR_RE = re.compile(r"(?<!\\)\$(?=\s*\d)")

# ── Paired-delimiter patterns (lazy + DOTALL so they don't cross pairs) ──
# \[...\]  →  $$...$$
_DISPLAY_PAIR_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)

# \(...\)  →  $...$
_INLINE_PAIR_RE = re.compile(r"\\\((.*?)\\\)", re.DOTALL)

# After pairs are consumed: strip leading backslash from unmatched
# openers / closers so they become plain brackets.
_UNPAIRED_OPEN_RE = re.compile(r"\\(?=[\[\(])")
_UNPAIRED_CLOSE_RE = re.compile(r"\\(?=[\]\)])")


def sanitize_token(token: str) -> str:
    """Minimal per-token processing for **streaming**.

    * Collapses thin-space (``U+202F``) and NBSP (``U+00A0``) to
      regular space.
    * Strips legacy ``\\\\$`` double-escape.
    * Escapes currency-pattern ``$`` so ``R$100`` doesn't trigger
      accidental math mode during live streaming.

    Does **not** convert ``\\\\(…\\\\)`` or ``\\\\[…\\\\]`` — paired
    delimiters require the full string.
    """
    token = token.replace("\u202f", " ").replace("\u00a0", " ")
    token = token.replace("\\\\$", "$")
    token = _CURRENCY_DOLLAR_RE.sub(r"\\$", token)
    return token


def sanitize_text(text: str) -> str:
    """Normalize *text* for safe `st.markdown` rendering.

    Processing order (each step operates on the output of the previous):

    1. Collapse thin-space / NBSP.
    2. Strip legacy ``\\\\$`` double-escape.
    3. Escape currency-pattern ``$`` (must run **before** math
       conversion so intentional ``$x^2$`` is not touched).
    4. Convert paired ``\\\\[…\\\\]`` → ``$$…$$``.
    5. Convert paired ``\\\\(…\\\\)`` → ``$…$``.
    6. Strip backslashes from any remaining unmatched delimiters.

    All steps are idempotent — calling *sanitize_text* twice yields the
    same result.
    """
    # 1 – whitespace
    text = text.replace("\u202f", " ").replace("\u00a0", " ")

    # 2 – legacy double-escaped dollars (before math conversion)
    text = text.replace("\\\\$", "$")

    # 3 – escape currency-pattern $ (before math; $x^2$ is safe)
    text = _CURRENCY_DOLLAR_RE.sub(r"\\$", text)

    # 4 – paired display math
    text = _DISPLAY_PAIR_RE.sub(lambda m: f"$${m.group(1)}$$", text)

    # 5 – paired inline math
    text = _INLINE_PAIR_RE.sub(lambda m: f"${m.group(1)}$", text)

    # 6 – strip backslashes from unmatched openers / closers
    text = _UNPAIRED_OPEN_RE.sub("", text)
    text = _UNPAIRED_CLOSE_RE.sub("", text)

    return text
