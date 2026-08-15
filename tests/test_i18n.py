"""Tests for the translation catalog and lookup helpers."""

import pytest

from src.i18n import DEFAULT_LANG, LANGUAGES, TRANSLATIONS, t, translate


def test_default_lang_is_english():
    assert DEFAULT_LANG == "en"
    assert LANGUAGES[0] == "en"


def test_catalog_key_parity_all_languages_present():
    for key, langs in TRANSLATIONS.items():
        assert set(langs) == set(LANGUAGES), f"{key}: {sorted(langs)} != {sorted(LANGUAGES)}"
        for lang in LANGUAGES:
            assert langs[lang].strip(), f"{key}[{lang}] is empty"


def test_translate_known_key_en_returns_english():
    assert translate("web.tab.today", "en") == "Today"


def test_translate_known_key_pt_returns_portuguese():
    assert translate("web.tab.today", "pt") == "Hoje"


def test_translate_with_format_placeholders_substitutes_values():
    assert translate("web.sidebar.greeting", "en", name="Galvani") == "Hello, Galvani."
    assert translate("web.sidebar.greeting", "pt", name="Galvani") == "Olá, Galvani."


def test_translate_missing_key_raises_keyerror():
    with pytest.raises(KeyError):
        translate("web.nonexistent", "en")


def test_translate_unknown_lang_raises_keyerror():
    with pytest.raises(KeyError):
        translate("web.tab.today", "fr")


def test_t_defaults_to_english_in_bare_mode():
    assert t("web.tab.today") == "Today"
