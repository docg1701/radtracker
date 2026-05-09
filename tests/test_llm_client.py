"""Tests for src.llm_client — v2 OpenRouter API client with mocked HTTP."""

import httpx
import pytest
import respx
from httpx import Response, TimeoutException

from src.llm_client import (
    LLMClient,
    LLMUnavailableError,
    _enrich_stats,
    build_rag_context,
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
    def test_enrich_stats_has_required_keys(self):
        stats = _minimal_stats()
        enriched = _enrich_stats(stats, _ACTIVE_MODS)
        for key in ["ytd_earnings", "ytd_avg_monthly", "ytd_months",
                     "monthly_detail", "full_daily_table"]:
            assert key in enriched, f"Missing key: {key}"

    def test_enrich_stats_monthly_detail_contains_brl(self):
        stats = _minimal_stats()
        enriched = _enrich_stats(stats, _ACTIVE_MODS)
        detail = enriched["monthly_detail"]
        assert "R$" in detail
        assert "ABRIL" in detail.upper() or "2026-04" in detail


class TestEnrichStatsMultiMonth:
    def test_monthly_detail_separates_months(self):
        stats = _multi_month_stats()
        enriched = _enrich_stats(stats, _ACTIVE_MODS)
        detail = enriched["monthly_detail"]
        # Each month gets its own block
        assert "--- MARÇO ---" in detail.upper() or "--- 2026-03 ---" in detail
        assert "--- ABRIL ---" in detail.upper() or "--- 2026-04 ---" in detail

    def test_full_daily_table_includes_all_days(self):
        stats = _multi_month_stats()
        enriched = _enrich_stats(stats, _ACTIVE_MODS)
        table = enriched["full_daily_table"]
        assert "2026-03" in table
        assert "2026-04" in table

    def test_monthly_detail_has_per_modality_breakdown(self):
        stats = _multi_month_stats()
        enriched = _enrich_stats(stats, _ACTIVE_MODS)
        detail = enriched["monthly_detail"]
        # Should mention modality labels
        for m in _ACTIVE_MODS:
            assert m["label"] in detail, f"Missing modality: {m['label']}"


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

    @respx.mock
    def test_generate_stream_captures_reasoning_content(self):
        """reasoning_content tokens (DeepSeek native) are accumulated in buffer."""
        route = respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                'data: {"choices":[{"delta":{"reasoning_content":"Pensando...","content":null}}]}',
                'data: {"choices":[{"delta":{"content":"Resposta"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["Resposta"]  # content tokens unchanged
        assert llm.reasoning == "Pensando..."
        assert route.called

    @respx.mock
    def test_generate_stream_captures_reasoning_field(self):
        """reasoning tokens (OpenRouter normalized) are accumulated in buffer."""
        route = respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                'data: {"choices":[{"delta":{"reasoning":"Thinking...","content":null}}]}',
                'data: {"choices":[{"delta":{"content":"Answer"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["Answer"]
        assert llm.reasoning == "Thinking..."
        assert route.called

    @respx.mock
    def test_generate_stream_reasoning_and_content_same_delta(self):
        """When delta has both reasoning_content and content, both are captured."""
        route = respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                'data: {"choices":[{"delta":{"reasoning_content":"Think","content":"Out"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["Out"]
        assert llm.reasoning == "Think"
        assert route.called

    @respx.mock
    def test_generate_stream_reasoning_none_when_no_tokens(self):
        """reasoning property returns None when model doesn't emit reasoning."""
        route = respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                'data: {"choices":[{"delta":{"content":"Plain"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        tokens = list(llm.generate_stream([{"role": "user", "content": "Oi"}]))
        assert tokens == ["Plain"]
        assert llm.reasoning is None
        assert route.called

    @respx.mock
    def test_generate_stream_reasoning_buffer_resets(self):
        """Each generate_stream() call gets a fresh reasoning buffer."""
        route = respx.post(_OPENROUTER_URL).mock(
            return_value=_sse_chunks(
                'data: {"choices":[{"delta":{"reasoning_content":"First"}}]}',
                'data: {"choices":[{"delta":{"content":"A"}}]}',
                "data: [DONE]",
            )
        )
        llm = LLMClient("sk-test", "test/model")
        list(llm.generate_stream([{"role": "user", "content": "Q1"}]))
        assert llm.reasoning == "First"

        route.return_value = _sse_chunks(
            'data: {"choices":[{"delta":{"content":"B"}}]}',
            "data: [DONE]",
        )
        list(llm.generate_stream([{"role": "user", "content": "Q2"}]))
        assert llm.reasoning is None  # second call has no reasoning


class TestBuildPayload:
    """Tests for _build_payload() reasoning parameter construction."""

    def test_build_payload_no_max_tokens_sent(self):
        """max_tokens is never sent — model uses its own default."""
        llm = LLMClient("sk-test", "test/model")
        payload = llm._build_payload([], stream=False)
        assert "max_tokens" not in payload

    def test_build_payload_reasoning_omitted_by_default(self):
        """With thinking enabled and no effort/budget, no reasoning key."""
        llm = LLMClient("sk-test", "test/model")
        payload = llm._build_payload(
            [], stream=False, thinking_enabled=True,
        )
        assert "reasoning" not in payload

    def test_build_payload_reasoning_disabled(self):
        llm = LLMClient("sk-test", "test/model")
        payload = llm._build_payload(
            [], stream=False, thinking_enabled=False,
        )
        assert payload["reasoning"] == {"enabled": False}
        assert "max_tokens" not in payload

    def test_build_payload_reasoning_effort(self):
        llm = LLMClient("sk-test", "test/model")
        payload = llm._build_payload(
            [], stream=False,
            thinking_enabled=True, thinking_effort="xhigh",
        )
        assert payload["reasoning"] == {"effort": "xhigh"}
        assert "max_tokens" not in payload

    def test_build_payload_reasoning_budget(self):
        llm = LLMClient("sk-test", "test/model")
        payload = llm._build_payload(
            [], stream=False,
            thinking_enabled=True, thinking_budget=32000,
        )
        assert payload["reasoning"] == {"max_tokens": 32000}
        assert "max_tokens" not in payload


class TestBuildRagContext:
    def test_build_rag_context_includes_template_sections(self):
        stats = _minimal_stats()
        ctx = build_rag_context(stats, _ACTIVE_MODS, system_prompt="Teste")
        assert "=== DADOS ATUAIS PARA ANÁLISE ===" in ctx
        assert "=== RESUMO DO ANO (YTD) ===" in ctx
        assert "=== DETALHES POR MÊS ===" in ctx
        assert "=== DADOS DIÁRIOS COMPLETOS (todas as modalidades, todos os dias) ===" in ctx
        assert "R$ 3.915,00" in ctx  # MTD computed from df earnings

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
