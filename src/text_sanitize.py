"""
Text sanitization for safe `st.markdown` rendering.

Normalises whitespace anomalies, converts LLM-typical LaTeX delimiters
to Streamlit-compatible forms (paired matching only), and strips legacy
escape artifacts.

Architecture
------------
* ``sanitize_token`` — light-weight, per-chunk processor for streaming.
  Only collapses whitespace and strips legacy ``\\\\$`` escapes.
  Never touches LaTeX delimiters — those require paired matching and
  must run on the complete string.

* ``sanitize_text`` — full-string processor called *after* streaming
  completes, and again on history re-render (idempotent).  Converts
  paired ``\\\\(…\\\\)`` → ``$…$`` and ``\\\\[…\\\\]`` → ``$$…$$``,
  then strips backslashes from any remaining unmatched delimiters.
"""

import re

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
      regular space, preventing accidental LaTeX trigger (e.g.,
      ``R$\\u202f45.000``).
    * Strips legacy ``\\\\$`` double-escape left over from
      pre‑v1.5.3 sessions.

    This function deliberately does **not** convert ``\\\\(…\\\\)`` or
    ``\\\\[…\\\\]`` — paired delimiters cannot be reliably matched
    across token boundaries.  Use :func:`sanitize_text` on the full
    accumulated string after streaming.
    """
    token = token.replace("\u202f", " ").replace("\u00a0", " ")
    token = token.replace("\\\\$", "$")
    return token


def sanitize_text(text: str) -> str:
    """Normalize *text* for safe `st.markdown` rendering.

    Processing order (each step operates on the output of the previous):

    1. Collapse thin-space / NBSP.
    2. Strip legacy ``\\\\$`` double-escape (must run **before** math
       conversion so it doesn't interfere with newly-created ``$``).
    3. Convert paired ``\\\\[…\\\\]`` → ``$$…$$``.
    4. Convert paired ``\\\\(…\\\\)`` → ``$…$``.
    5. Strip backslashes from any remaining unmatched ``\\\\(``,
       ``\\\\[``, ``\\\\)``, ``\\\\]`` — they become plain brackets.

    All steps are idempotent — calling *sanitize_text* twice yields the
    same result.
    """
    # 1 – whitespace
    text = text.replace("\u202f", " ").replace("\u00a0", " ")

    # 2 – legacy double-escaped dollars (before math conversion)
    text = text.replace("\\\\$", "$")

    # 3 – paired display math
    text = _DISPLAY_PAIR_RE.sub(lambda m: f"$${m.group(1)}$$", text)

    # 4 – paired inline math
    text = _INLINE_PAIR_RE.sub(lambda m: f"${m.group(1)}$", text)

    # 5 – strip backslashes from unmatched openers / closers
    text = _UNPAIRED_OPEN_RE.sub("", text)
    text = _UNPAIRED_CLOSE_RE.sub("", text)

    return text
