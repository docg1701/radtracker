"""Unit tests for src.text_sanitize."""

from src.text_sanitize import sanitize_text


class TestSanitizeText:
    """Tests for sanitize_text()."""

    # ── whitespace ──

    def test_collapses_thin_space(self) -> None:
        assert sanitize_text("R$\u202f45.000") == "R$ 45.000"

    def test_collapses_nbsp(self) -> None:
        assert sanitize_text("valor\u00a0total") == "valor total"

    def test_preserves_regular_spaces(self) -> None:
        assert sanitize_text("R$ 45.000,00") == "R$ 45.000,00"

    # ── LaTeX bracket → $/$$ conversion ──

    def test_converts_display_math_brackets(self) -> None:
        assert sanitize_text(r"\[ x^2 \]") == r"$$ x^2 $$"

    def test_converts_inline_math_parens(self) -> None:
        assert sanitize_text(r"\( x^2 \)") == r"$ x^2 $"

    def test_converts_display_math_with_content(self) -> None:
        assert sanitize_text(
            r"Cálculo: \[ \frac{a}{b} = 2 \] fim."
        ) == r"Cálculo: $$ \frac{a}{b} = 2 $$ fim."

    def test_does_not_touch_regular_brackets(self) -> None:
        assert sanitize_text("[note] and (paren)") == "[note] and (paren)"

    def test_handles_multiple_math_blocks(self) -> None:
        assert sanitize_text(r"\[a\] e \(b\)") == r"$$a$$ e $b$"

    # ── legacy double-escape stripping ──

    def test_strips_legacy_double_escaped_dollar(self) -> None:
        # Simulates stored content from old double-escaped sessions
        assert sanitize_text(r"Valor: \\$ 100") == "Valor: $ 100"

    def test_single_backslash_dollar_passes_through(self) -> None:
        # \$ from old safe_stream is valid markdown — renders as $
        # sanitize_text preserves it (no double-escape to clean)
        result = sanitize_text(r"R\$ 100")
        # The backslash remains — st.markdown will render it as literal $
        assert r"\$" in result

    # ── preserves normal text ──

    def test_preserves_normal_text(self) -> None:
        original = "Olá, Dr. Fulano. Tudo bem?"
        assert sanitize_text(original) == original

    def test_preserves_markdown_formatting(self) -> None:
        original = "**negrito** e *itálico* e `código`"
        assert sanitize_text(original) == original

    def test_preserves_dollar_sign_followed_by_space(self) -> None:
        # Currency pattern: $ followed by space — not math
        assert sanitize_text("Custa $ 50") == "Custa $ 50"

    # ── edge cases ──

    def test_empty_string(self) -> None:
        assert sanitize_text("") == ""

    def test_only_whitespace(self) -> None:
        assert sanitize_text("   ") == "   "

    def test_only_thin_space(self) -> None:
        assert sanitize_text("\u202f") == " "

    def test_mixed_escape_and_math(self) -> None:
        # Legacy double-escaped \\$ alongside real LaTeX brackets
        assert sanitize_text(r"Ganhou \\$ 100 com \( x^2 \)") == (
            r"Ganhou $ 100 com $ x^2 $"
        )
