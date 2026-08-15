"""Unit tests for src.text_sanitize."""

from src.text_sanitize import sanitize_text, sanitize_token


class TestSanitizeToken:
    """Tests for sanitize_token() — streaming processor."""

    def test_collapses_thin_space_and_escapes_currency(self) -> None:
        assert sanitize_token("R$\u202f45.000") == r"R\$ 45.000"

    def test_collapses_nbsp(self) -> None:
        assert sanitize_token("valor\u00a0total") == "valor total"

    def test_strips_legacy_double_without_r_prefix(self) -> None:
        # \\$ → $, then bare $ before digit is currency → \$
        assert sanitize_token(r"Valor: \\$ 100") == r"Valor: \$ 100"

    def test_strips_legacy_with_r_prefix(self) -> None:
        # \\$ → $, then $ after R → \$
        assert sanitize_token(r"R\\$ 100") == r"R\$ 100"

    def test_does_not_convert_latex_brackets(self) -> None:
        assert sanitize_token(r"\( x^2 \)") == r"\( x^2 \)"
        assert sanitize_token(r"\[ x^2 \]") == r"\[ x^2 \]"

    def test_preserves_math_dollar(self) -> None:
        assert sanitize_token("$x=2$") == "$x=2$"

    def test_escapes_currency_no_space(self) -> None:
        assert sanitize_token("R$129") == r"R\$129"

    def test_escapes_standalone_dollar_before_digit(self) -> None:
        # Bare $ before a digit is currency now (no R prefix needed).
        assert sanitize_token("$50") == r"\$50"


class TestSanitizeText:
    """Tests for sanitize_text()."""

    # whitespace

    def test_collapses_thin_space(self) -> None:
        assert sanitize_text("R$\u202f45.000") == r"R\$ 45.000"

    def test_collapses_nbsp(self) -> None:
        assert sanitize_text("valor\u00a0total") == "valor total"

    # currency escape (R$ prefix only)

    def test_escapes_currency_with_space(self) -> None:
        assert sanitize_text("R$ 45.000,00") == r"R\$ 45.000,00"

    def test_escapes_currency_without_space(self) -> None:
        assert sanitize_text("R$129.513") == r"R\$129.513"

    def test_escapes_standalone_dollar_before_digit(self) -> None:
        # Bare $ before a digit is currency; math pairs are protected separately.
        assert sanitize_text("$50") == r"\$50"

    def test_escapes_us_formatted_currency(self) -> None:
        assert sanitize_text("$1,250.00") == r"\$1,250.00"

    def test_escapes_multiple_currencies_in_one_line(self) -> None:
        assert sanitize_text("$12.12 vs $8.14") == r"\$12.12 vs \$8.14"

    # math preservation

    def test_preserves_math_dollar(self) -> None:
        assert sanitize_text("$x^2$") == "$x^2$"
        assert sanitize_text(r"$\frac{a}{b}$") == r"$\frac{a}{b}$"

    def test_preserves_native_display_math(self) -> None:
        assert sanitize_text(r"$$\sum x$$") == r"$$\sum x$$"

    def test_preserves_math_formula_with_digits(self) -> None:
        assert sanitize_text(r"$25\times4 = 100$") == r"$25\times4 = 100$"

    def test_mixed_currency_and_math(self) -> None:
        assert sanitize_text(
            r"Faturamento R$ 100 e formula $f(x)=2x$"
        ) == r"Faturamento R\$ 100 e formula $f(x)=2x$"

    def test_multiple_currencies_in_text(self) -> None:
        assert sanitize_text(r"R$ 12,12 vs R$ 8,14") == r"R\$ 12,12 vs R\$ 8,14"

    def test_currency_idempotent(self) -> None:
        first = sanitize_text("R$ 100")
        second = sanitize_text(first)
        assert first == second

    # LaTeX bracket conversion

    def test_converts_display_math_brackets(self) -> None:
        assert sanitize_text(r"\[ x^2 \]") == r"$$ x^2 $$"

    def test_converts_inline_math_parens(self) -> None:
        assert sanitize_text(r"\( x^2 \)") == r"$ x^2 $"

    def test_converts_display_math_with_content(self) -> None:
        assert sanitize_text(
            r"Calculo: \[ \frac{a}{b} = 2 \] fim."
        ) == r"Calculo: $$ \frac{a}{b} = 2 $$ fim."

    def test_does_not_touch_regular_brackets(self) -> None:
        assert sanitize_text("[note] and (paren)") == "[note] and (paren)"

    def test_handles_multiple_math_blocks(self) -> None:
        assert sanitize_text(r"\[a\] e \(b\)") == r"$$a$$ e $b$"

    # legacy double-escape

    def test_strips_legacy_with_r_prefix(self) -> None:
        assert sanitize_text(r"Valor: R\\$ 100") == r"Valor: R\$ 100"

    def test_strips_legacy_without_r_prefix(self) -> None:
        assert sanitize_text(r"Valor: \\$ 100") == r"Valor: \$ 100"

    def test_legacy_without_r_prefix_unchanged(self) -> None:
        assert sanitize_text(r"Custa \\$50") == r"Custa \$50"

    def test_single_backslash_dollar_passes_through(self) -> None:
        result = sanitize_text(r"R\$ 100")
        assert r"\$" in result

    # normal text

    def test_preserves_normal_text(self) -> None:
        original = "Ola, Dr. Fulano. Tudo bem?"
        assert sanitize_text(original) == original

    def test_preserves_markdown_formatting(self) -> None:
        original = "**negrito** e *italico* e `codigo`"
        assert sanitize_text(original) == original

    # unmatched delimiter fallback

    def test_unmatched_open_fallback(self) -> None:
        assert sanitize_text(r"valor \(x") == "valor (x"

    def test_unmatched_close_fallback(self) -> None:
        assert sanitize_text(r"fim\)") == "fim)"

    def test_unmatched_display_fallback(self) -> None:
        assert sanitize_text(r"nota \[") == "nota ["
        assert sanitize_text(r"fim \]") == "fim ]"

    # non-crossing pairs

    def test_two_separate_pairs(self) -> None:
        assert sanitize_text(r"\(a\) and \(b\)") == "$a$ and $b$"

    def test_lazy_matching_displays(self) -> None:
        assert sanitize_text(r"\[a\] b \[c\]") == "$$a$$ b $$c$$"

    def test_idempotent(self) -> None:
        original = r"\[a\] e \(b\) e resto"
        first = sanitize_text(original)
        second = sanitize_text(first)
        assert first == second

    # edge cases

    def test_empty_string(self) -> None:
        assert sanitize_text("") == ""

    def test_only_whitespace(self) -> None:
        assert sanitize_text("   ") == "   "

    def test_only_thin_space(self) -> None:
        assert sanitize_text("\u202f") == " "

    def test_mixed_legacy_and_latex(self) -> None:
        assert sanitize_text(r"Ganhou R\\$ 100 com \( x^2 \)") == (
            r"Ganhou R\$ 100 com $ x^2 $"
        )

    def test_mixed_legacy_no_r_prefix(self) -> None:
        assert sanitize_text(r"Total: \\$ 50 e \(z\)") == r"Total: \$ 50 e $z$"

    def test_normalizes_escaped_opener_inside_math_pair(self) -> None:
        # Token-level escape of a complete math pair is normalized back.
        assert sanitize_text(r"\$25\times4 = 100$") == r"$25\times4 = 100$"
