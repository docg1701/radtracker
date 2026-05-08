"""Tests for src.llm_client — v2 OpenRouter API client with mocked HTTP."""

import httpx
import pytest
import respx
from httpx import Response, TimeoutException

from src.llm_client import (
    LLMClient,
    LLMUnavailableError,
    build_rag_context,
    _enrich_stats,
)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OK_JSON = {"choices": [{"message": {"content": "Insight gerado pela IA"}}]}

_ACTIVE_MODS = [
    {"slug": "ressonancia_magnetica", "label": "Ressonância Magnética",
     "price": 35.0, "exams_per_hour": 7.5, "active": 1, "sort_order": 4},
    {"slug": "tc_geral", "label": "TC Geral",
     "price": 25.0, "exams_per_hour": 7.5, "active": 1, "sort_order": 2},
    {"slug": "radiografia", "label": "Radiografia",
     "price": 4.5, "exams_per_hour": 75.0, "active": 1, "sort_order": 8},
]


class TestLlmClientSuccess:
    @respx.mock
    def test_generate_stream_success(self):
        respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                'data: {"choices":[{"delta":{"content":"Insight"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-fake-key", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["Insight"]


class TestLlmClientMissingKey:
    def test_llm_client_missing_key(self):
        with pytest.raises(LLMUnavailableError) as exc:
            LLMClient(None, "test/model")
        assert "não configurada" in str(exc.value)

    def test_llm_client_empty_key(self):
        with pytest.raises(LLMUnavailableError) as exc:
            LLMClient("", "test/model")
        assert "não configurada" in str(exc.value)


class TestLlmClientErrors:
    @respx.mock
    def test_generate_stream_timeout(self):
        respx.post(_OPENROUTER_URL).mock(side_effect=TimeoutException("timeout"))
        llm = LLMClient("sk-fake-key", "test/model")
        with pytest.raises(LLMUnavailableError) as exc:
            list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert "Timeout" in str(exc.value)

    @respx.mock
    def test_generate_stream_connect_error(self):
        respx.post(_OPENROUTER_URL).mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        llm = LLMClient("sk-fake-key", "test/model")
        with pytest.raises(LLMUnavailableError) as exc:
            list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert "conexão" in str(exc.value)

    @respx.mock
    def test_generate_stream_http_500(self):
        respx.post(_OPENROUTER_URL).mock(
            return_value=Response(500, json={"error": "server error"})
        )
        llm = LLMClient("sk-fake-key", "test/model")
        with pytest.raises(LLMUnavailableError) as exc:
            list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert "HTTP 500" in str(exc.value)


class TestEnrichStats:
    def test_enrich_stats_sanitizes_none_wow(self):
        stats = _minimal_stats(wow=None)
        enriched = _enrich_stats(stats, _ACTIVE_MODS)
        assert enriched["wow"] == "sem dados suficientes"

    def test_enrich_stats_includes_brl_formatting(self):
        stats = _minimal_stats()
        enriched = _enrich_stats(stats, _ACTIVE_MODS)
        assert enriched["mtd"] == "R$ 22.500,00"


class TestEnrichStatsMultiMonth:
    def test_total_exames_filters_current_month_only(self):
        stats = _multi_month_stats()
        enriched = _enrich_stats(stats, _ACTIVE_MODS)
        # April: 1*7 RM + 2*7 TC + 10*7 RX = 7+14+70 = 91 total
        breakdown = enriched["modality_breakdown"]
        assert "Ressonância Magnética: 7 exames" in breakdown
        assert "TC Geral: 14 exames" in breakdown
        assert "Radiografia: 70 exames" in breakdown
        assert "896" not in breakdown

    def test_best_day_filters_current_month_only(self):
        stats = _multi_month_stats()
        enriched = _enrich_stats(stats, _ACTIVE_MODS)
        # April best day = any April day; if unfiltered, best would be March
        assert enriched["dia_produtivo"].startswith("2026-04")
        assert "2026-03" not in enriched["dia_produtivo"]

    def test_ticket_medio_uses_current_month_counts(self):
        stats = _multi_month_stats()
        enriched = _enrich_stats(stats, _ACTIVE_MODS)
        # April revenue = 7*35 + 14*25 + 70*4.5 = 910
        # Ticket = 910 / 91 = 10.0
        assert enriched["ticket_medio"] == "R$ 10,00"


# ── Streaming tests ──


def _sse_chunks(*lines: str):
    """Helper: gera bytes de SSE a partir de strings."""
    return Response(200, content="\n".join(lines).encode("utf-8"))


class TestGenerateStream:
    @respx.mock
    def test_generate_stream_yields_tokens(self):
        route = respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                'data: {"choices":[{"delta":{"content":"Olá"}}]}',
                'data: {"choices":[{"delta":{"content":" mundo"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["Olá", " mundo"]
        assert route.called

    @respx.mock
    def test_generate_stream_empty_response(self):
        """SSE válido mas sem nenhum token deve levantar LLMUnavailableError."""
        respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks("data: [DONE]")
        )
        llm = LLMClient("sk-test", "test/model")
        with pytest.raises(LLMUnavailableError) as exc:
            list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert "vazia" in str(exc.value)

    @respx.mock
    def test_generate_stream_http_error(self):
        respx.post(_OPENROUTER_URL).mock(
            return_value=Response(500, json={"error": "boom"})
        )
        llm = LLMClient("sk-test", "test/model")
        with pytest.raises(LLMUnavailableError) as exc:
            list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert "HTTP 500" in str(exc.value)

    @respx.mock
    def test_generate_stream_network_error(self):
        respx.post(_OPENROUTER_URL).mock(side_effect=httpx.ConnectError("connection refused"))
        llm = LLMClient("sk-test", "test/model")
        with pytest.raises(LLMUnavailableError) as exc:
            list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert "conexão" in str(exc.value)

    @respx.mock
    def test_generate_stream_timeout(self):
        respx.post(_OPENROUTER_URL).mock(side_effect=TimeoutException("timeout"))
        llm = LLMClient("sk-test", "test/model")
        with pytest.raises(LLMUnavailableError) as exc:
            list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert "Timeout" in str(exc.value)
        assert "30s" in str(exc.value)

    @respx.mock
    def test_generate_stream_malformed_sse(self):
        """Linhas com JSON inválido ou sem choices são ignoradas; tokens válidos são yield."""
        route = respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                "data: not json",
                'data: {"model":"foo"}',
                'data: {"delta":{"content":"ignored"}}',
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["ok"]
        assert route.called

    @respx.mock
    def test_generate_stream_delta_content_null(self):
        """delta.content = null não deve quebrar nem yield nada."""
        route = respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                'data: {"choices":[{"delta":{"content":null}}]}',
                'data: {"choices":[{"delta":{"content":"fim"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["fim"]
        assert route.called

    @respx.mock
    def test_generate_stream_delta_content_empty_string(self):
        """delta.content = "" (falsy) não deve setar yielded_any nem yield."""
        route = respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                'data: {"choices":[{"delta":{"content":""}}]}',
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["ok"]
        assert route.called

    @respx.mock
    def test_generate_stream_malformed_sse_top_level_array(self):
        """JSON array no lugar de objeto deve disparar AttributeError e ser ignorado."""
        route = respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                "data: []",
                'data: {"choices":[{"delta":{"content":"ok"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["ok"]
        assert route.called

    @respx.mock
    def test_generate_stream_done_with_whitespace(self):
        respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                'data: {"choices":[{"delta":{"content":"fim"}}]}',
                "data:  [DONE]  ",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["fim"]


class TestBuildRagContext:
    def test_build_rag_context_includes_stats(self):
        stats = _minimal_stats()
        ctx = build_rag_context(stats, _ACTIVE_MODS, system_prompt="Teste")
        assert "=== DADOS ATUAIS PARA ANÁLISE ===" in ctx
        assert "R$ 22.500,00" in ctx  # MTD

    def test_build_rag_context_respects_custom_prompt(self):
        stats = _minimal_stats()
        custom = "Você é um especialista em radiologia."
        ctx = build_rag_context(stats, _ACTIVE_MODS, system_prompt=custom)
        assert custom in ctx

    def test_build_rag_context_empty_string_prompt(self):
        """String vazia resulta em system prompt vazio (sem fallback)."""
        stats = _minimal_stats()
        ctx = build_rag_context(stats, _ACTIVE_MODS, system_prompt="")
        assert ctx.startswith("\n\n=== DADOS ATUAIS")


# ── Helpers ──


def _minimal_stats(wow: float | None = 5.0, mom: float | None = None):
    import pandas as pd

    dates = [f"2026-04-{d:02d}" for d in range(1, 14)]
    df = pd.DataFrame({
        "date": dates,
        "ressonancia_magnetica": [2, 3, 1, 0, 4, 2, 3, 1, 5, 2, 3, 4, 2],
        "tc_geral": [1, 0, 2, 1, 0, 3, 2, 1, 0, 2, 1, 3, 2],
        "radiografia": [50, 60, 40, 30, 70, 50, 60, 40, 80, 50, 60, 70, 50],
        "earnings": [
            295.0, 315.0, 195.0, 135.0, 385.0, 325.0,
            305.0, 175.0, 455.0, 295.0, 315.0, 425.0, 295.0,
        ],
        "ma7": [
            295.0, 305.0, 270.0, 235.0, 265.0, 270.0,
            265.0, 240.0, 258.0, 260.0, 270.0, 285.0, 290.0,
        ],
        "ma30": [
            295.0, 305.0, 270.0, 235.0, 265.0, 270.0,
            265.0, 240.0, 258.0, 260.0, 270.0, 285.0, 290.0,
        ],
    })
    return {
        "df": df,
        "year_month": "2026-04",
        "current_month_stats": {
            "mtd_earnings": 22500.0,
            "pct_goal": 50.0,
            "days_worked": 13,
            "total_calendar_days": 30,
            "daily_avg": 1730.77,
            "daily_target_needed": 1730.77,
            "projection_month_end": 45000.0,
            "remaining_calendar_days": 17,
        },
        "wow_change_pct": wow,
        "mom_change_pct": mom,
        "modality_mix_current": {
            "ressonancia_magnetica": 60.0,
            "tc_geral": 25.0,
            "radiografia": 15.0,
        },
        "modality_mix_historical": {
            "2026-01": {"ressonancia_magnetica": 55.0, "tc_geral": 30.0, "radiografia": 15.0},
            "2026-02": {"ressonancia_magnetica": 58.0, "tc_geral": 28.0, "radiografia": 14.0},
            "2026-03": {"ressonancia_magnetica": 60.0, "tc_geral": 25.0, "radiografia": 15.0},
        },
        "consecutive_below_target": 0,
    }


def _multi_month_stats():
    import pandas as pd

    dates = [f"2026-03-{d:02d}" for d in range(1, 8)] + [
        f"2026-04-{d:02d}" for d in range(1, 8)
    ]
    df = pd.DataFrame({
        "date": dates,
        "ressonancia_magnetica": [10] * 7 + [1] * 7,
        "tc_geral": [5] * 7 + [2] * 7,
        "radiografia": [100] * 7 + [10] * 7,
        "earnings": [500.0] * 7 + [100.0] * 7,
        "ma7": [500.0] * 7 + [100.0] * 7,
        "ma30": [500.0] * 7 + [100.0] * 7,
    })
    return {
        "df": df,
        "year_month": "2026-04",
        "current_month_stats": {
            "mtd_earnings": 910.0,
            "pct_goal": 1.6,
            "days_worked": 7,
            "total_calendar_days": 30,
            "daily_avg": 100.0,
            "daily_target_needed": 0.0,
            "projection_month_end": 700.0,
            "remaining_calendar_days": 23,
        },
        "wow_change_pct": None,
        "mom_change_pct": None,
        "modality_mix_current": {
            "ressonancia_magnetica": 35.0,
            "tc_geral": 50.0,
            "radiografia": 15.0,
        },
        "modality_mix_historical": {},
        "consecutive_below_target": 0,
    }
