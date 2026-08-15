"""
Text sanitization for safe `st.markdown` rendering.

Normalises whitespace anomalies, converts LLM-typical LaTeX delimiters
to Streamlit-compatible forms (paired matching only), escapes
currency-pattern dollar signs, and strips legacy escape artifacts.

Architecture
------------
* ``sanitize_token`` — light-weight, per-chunk processor for streaming.
  Collapses whitespace, strips legacy ``\\\\$``, and escapes
  currency-pattern ``$`` (e.g. ``$ 100``, ``$50``).

* ``sanitize_text`` — full-string processor called *after* streaming
  completes, and again on history re-render (idempotent).  Protects
  genuine math pairs (``$x^2$``, ``$\\frac{a}{b}$``, ``$25\\times4 = 100$``)
  before escaping currency ``$``, then converts ``\\\\(…\\\\)`` → ``$…$``
  and ``\\\\[…\\\\]`` → ``$$…$$``, then strips backslashes from any
  remaining unmatched delimiters.
"""

import re

# ── Math-pair protection (runs before currency escape) ──
# Opener may carry a leading backslash left by a sanitize_token escape —
# a confirmed pair is normalized back to plain $...$.
# Letter/backslash opener: $x^2$, $\frac{a}{b}$, $f(x)=2x$.
_LETTER_PAIR_RE = re.compile(r"\\?\$([A-Za-z\\][\s\S]*?)\$")
# Digit opener with a LaTeX command inside: $25\times4 = 100$.
_DIGIT_PAIR_RE = re.compile(r"\\?\$(\d[\s\S]*?\\[\s\S]*?)\$")

# ── Currency-pattern dollar sign ──
# Unescaped $ followed by optional whitespace then digit: $50, $ 100, R$ 100.
# Math is already protected by the pair pass; $x^2$ never matches ($ is
# followed by a letter, not a digit).
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


def _protect_math_pairs(text: str) -> str:
    """Replace genuine math pairs with a sentinel so the currency rule skips them."""
    text = _LETTER_PAIR_RE.sub(lambda m: f"\x00{m.group(1)}\x00", text)
    return _DIGIT_PAIR_RE.sub(lambda m: f"\x00{m.group(1)}\x00", text)


def _restore_math_pairs(text: str) -> str:
    """Restore sentinel-protected math pairs to plain $...$."""
    return text.replace("\x00", "$")


def sanitize_token(token: str) -> str:
    """Minimal per-token processing for **streaming**.

    * Collapses thin-space (``U+202F``) and NBSP (``U+00A0``) to
      regular space.
    * Strips legacy ``\\\\$`` double-escape.
    * Escapes currency-pattern ``$`` so ``$50`` doesn't trigger
      accidental math mode during live streaming.

    Math-pair detection needs the full string; an opener escaped here
    (e.g. ``$25\\times…`` split across chunks) is normalized back by
    ``sanitize_text`` when the pair arrives complete.
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
    3. Protect genuine math pairs (letter/backslash/digit-with-command
       openers) with a sentinel — currency ``$`` never survives this pass
       as part of a pair.
    4. Escape currency-pattern ``$`` (``$50``, ``$ 100``, ``R$ 100``).
    5. Restore math pairs to ``$…$``.
    6. Convert paired ``\\\\[…\\\\]`` → ``$$…$$`` (added after escaping,
       so they stay math).
    6. Convert paired ``\\\\(…\\\\)`` → ``$…$``.
    7. Strip backslashes from any remaining unmatched delimiters.

    All steps are idempotent — calling *sanitize_text* twice yields the
    same result.
    """
    # 1 – whitespace
    text = text.replace("\u202f", " ").replace("\u00a0", " ")

    # 2 – legacy double-escaped dollars (before math conversion)
    text = text.replace("\\\\$", "$")

    # 3 – protect math pairs (normalizes token-level escapes inside pairs)
    text = _protect_math_pairs(text)

    # 4 – escape currency-pattern $ (pairs already protected)
    text = _CURRENCY_DOLLAR_RE.sub(r"\\$", text)

    # 5 – restore math pairs to plain $...$
    text = _restore_math_pairs(text)

    # 6 – paired display math
    text = _DISPLAY_PAIR_RE.sub(lambda m: f"$${m.group(1)}$$", text)

    # 6 – paired inline math
    text = _INLINE_PAIR_RE.sub(lambda m: f"${m.group(1)}$", text)

    # 7 – strip backslashes from unmatched openers / closers
    text = _UNPAIRED_OPEN_RE.sub("", text)
    text = _UNPAIRED_CLOSE_RE.sub("", text)

    return text
