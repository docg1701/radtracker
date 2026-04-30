"""Tests for src.llm_client — OpenRouter API client with mocked HTTP."""

import pytest
import respx
from httpx import Response, TimeoutException

from src.llm_client import LLMClient, LLMUnavailableError

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OK_JSON = {"choices": [{"message": {"content": "Insight gerado pela IA"}}]}
_DEFAULT_PRICES = {"rm": 35.0, "tc": 25.0, "rx": 4.5}


class TestLlmClientSuccess:
    @respx.mock
    def test_llm_client_success(self):
        respx.post(_OPENROUTER_URL).mock(
            return_value=Response(200, json=_OK_JSON)
        )
        llm = LLMClient("sk-fake-key")
        result = llm.generate(_minimal_stats(), _DEFAULT_PRICES)
        assert result == "Insight gerado pela IA"


class TestLlmClientMissingKey:
    def test_llm_client_missing_key(self):
        with pytest.raises(LLMUnavailableError) as exc:
            LLMClient(None)
        assert "não configurada" in str(exc.value)

    def test_llm_client_empty_key(self):
        with pytest.raises(LLMUnavailableError) as exc:
            LLMClient("")
        assert "não configurada" in str(exc.value)


class TestLlmClientErrors:
    @respx.mock
    def test_llm_client_timeout(self):
        # Simulate timeout by raising inside the mock handler
        respx.post(_OPENROUTER_URL).mock(side_effect=TimeoutException("timeout"))
        llm = LLMClient("sk-fake-key")
        with pytest.raises(LLMUnavailableError) as exc:
            llm.generate(_minimal_stats(), _DEFAULT_PRICES)
        assert "Timeout" in str(exc.value)

    @respx.mock
    def test_llm_client_http_500(self):
        respx.post(_OPENROUTER_URL).mock(
            return_value=Response(500, json={"error": "server error"})
        )
        llm = LLMClient("sk-fake-key")
        with pytest.raises(LLMUnavailableError) as exc:
            llm.generate(_minimal_stats(), _DEFAULT_PRICES)
        assert "HTTP 500" in str(exc.value)

    @respx.mock
    def test_llm_client_http_429(self):
        respx.post(_OPENROUTER_URL).mock(
            return_value=Response(429, json={"error": "rate limited"})
        )
        llm = LLMClient("sk-fake-key")
        with pytest.raises(LLMUnavailableError) as exc:
            llm.generate(_minimal_stats(), _DEFAULT_PRICES)
        assert "HTTP 429" in str(exc.value)

    @respx.mock
    def test_llm_client_http_401(self):
        respx.post(_OPENROUTER_URL).mock(
            return_value=Response(401, json={"error": "unauthorized"})
        )
        llm = LLMClient("sk-fake-key")
        with pytest.raises(LLMUnavailableError) as exc:
            llm.generate(_minimal_stats(), _DEFAULT_PRICES)
        assert "HTTP 401" in str(exc.value)


class TestBuildPrompt:
    def test_build_prompt_sanitizes_none_wow(self):
        llm = LLMClient("sk-fake-key")
        stats = _minimal_stats(wow=None)
        prompt = llm._build_prompt(stats, _DEFAULT_PRICES)
        assert "sem dados suficientes" in prompt
        assert "None" not in prompt

    def test_build_prompt_includes_brl_formatting(self):
        llm = LLMClient("sk-fake-key")
        stats = _minimal_stats()
        prompt = llm._build_prompt(stats, _DEFAULT_PRICES)
        assert "R$ 22.500,00" in prompt


class TestEnrichStatsMultiMonth:
    def test_total_exames_filters_current_month_only(self):
        llm = LLMClient("sk-fake-key")
        stats = _multi_month_stats()
        prompt = llm._build_prompt(stats, _DEFAULT_PRICES)
        # April has 7+14+70 = 91 exams; March has 805 exams.
        # If the filter works, prompt should say 91, not 896.
        assert "Total de exames no mês: 91" in prompt
        assert "Total de exames no mês: 896" not in prompt

    def test_best_day_filters_current_month_only(self):
        llm = LLMClient("sk-fake-key")
        stats = _multi_month_stats()
        prompt = llm._build_prompt(stats, _DEFAULT_PRICES)
        # April best day is 2026-04-01 (first day, all equal).
        # If unfiltered, best day would be a March date with 500 earnings.
        assert "2026-04-01" in prompt
        assert "2026-03-01" not in prompt

    def test_ticket_medio_uses_current_month_counts(self):
        llm = LLMClient("sk-fake-key")
        stats = _multi_month_stats()
        prompt = llm._build_prompt(stats, _DEFAULT_PRICES)
        # April revenue = 7*35 + 14*25 + 70*4.5 = 910
        # Ticket = 910 / 91 = 10.0
        assert "R$ 10,00" in prompt


# ── Helpers ──


def _minimal_stats(wow: float | None = 5.0, mom: float | None = None):
    import pandas as pd
    # Build a minimal DataFrame with enough data for _enrich_stats
    dates = [f"2026-04-{d:02d}" for d in range(1, 14)]
    df = pd.DataFrame({
        "date": dates,
        "rm_count": [2, 3, 1, 0, 4, 2, 3, 1, 5, 2, 3, 4, 2],
        "tc_count": [1, 0, 2, 1, 0, 3, 2, 1, 0, 2, 1, 3, 2],
        "rx_count": [50, 60, 40, 30, 70, 50, 60, 40, 80, 50, 60, 70, 50],
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
        "modality_mix_current": {"rm": 60.0, "tc": 25.0, "rx": 15.0},
        "modality_mix_historical": {
            "2026-01": {"rm": 55.0, "tc": 30.0, "rx": 15.0},
            "2026-02": {"rm": 58.0, "tc": 28.0, "rx": 14.0},
            "2026-03": {"rm": 60.0, "tc": 25.0, "rx": 15.0},
        },
        "consecutive_below_target": 0,
    }


def _multi_month_stats():
    import pandas as pd
    dates = [f"2026-03-{d:02d}" for d in range(1, 8)] + [f"2026-04-{d:02d}" for d in range(1, 8)]
    df = pd.DataFrame({
        "date": dates,
        "rm_count": [10] * 7 + [1] * 7,
        "tc_count": [5] * 7 + [2] * 7,
        "rx_count": [100] * 7 + [10] * 7,
        "earnings": [500.0] * 7 + [100.0] * 7,
        "ma7": [500.0] * 7 + [100.0] * 7,
        "ma30": [500.0] * 7 + [100.0] * 7,
    })
    return {
        "df": df,
        "year_month": "2026-04",
        "current_month_stats": {
            "mtd_earnings": 700.0,
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
        "modality_mix_current": {"rm": 35.0, "tc": 50.0, "rx": 15.0},
        "modality_mix_historical": {},
        "consecutive_below_target": 0,
    }
