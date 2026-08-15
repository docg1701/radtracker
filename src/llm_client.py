"""
LLM client for radtracker — OpenRouter API (configurable model).

Streaming-only client. Constructor takes API key and model slug;
generate_stream() does SSE token-by-token streaming.

Usage:
    llm = LLMClient(api_key, model)
    stream = llm.generate_stream(messages)  # messages already include system prompt
    response = st.write_stream(stream)

    # RAG context injection (for chat UI):
    context = build_rag_context(stats, active_mods, system_prompt)
"""

import json
from collections.abc import Generator
from datetime import date
from typing import Any

import httpx
import pandas as pd

from src.calculations import daily_avg_for_month
from src.formatting import MONTHS, fmt_money, month_name
from src.i18n import translate


class LLMUnavailableError(Exception):
    """API unreachable: missing key, timeout, or HTTP error from OpenRouter."""


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_RAG_TEMPLATES: dict[str, str] = {
    "en": """\
=== CURRENT DATE ===
{today}

=== CURRENT DATA FOR ANALYSIS ===
The data below are facts. Use them to ground your strategies.

=== MONTHLY GOAL AND STATUS ===
Monthly goal: {goal} | Days remaining: {remaining_days}
Current revenue (MTD): {mtd_earnings}
Projection at current pace: {projection_month_end}
Needed per remaining day to hit the goal: {daily_target_needed}

=== YEAR-TO-DATE (YTD) ===
Total revenue: {ytd_earnings} | Monthly average: {ytd_avg_monthly}
Months with data: {ytd_months}

=== MONTHLY DETAIL ===
{monthly_detail}

=== COMPLETE DAILY DATA (all modalities, all days) ===
{full_daily_table}
""",
    "pt": """\
=== DATA ATUAL ===
{today}

=== DADOS ATUAIS PARA ANÁLISE ===
Os dados abaixo são fatos. Use-os para fundamentar suas estratégias.

=== META E SITUAÇÃO DO MÊS ===
Meta mensal: {goal} | Dias restantes: {remaining_days}
Faturamento atual (MTD): {mtd_earnings}
Projeção no ritmo atual: {projection_month_end}
Necessário por dia restante para bater a meta: {daily_target_needed}

=== RESUMO DO ANO (YTD) ===
Faturamento acumulado: {ytd_earnings} | Média mensal: {ytd_avg_monthly}
Meses com dados: {ytd_months}

=== DETALHES POR MÊS ===
{monthly_detail}

=== DADOS DIÁRIOS COMPLETOS (todas as modalidades, todos os dias) ===
{full_daily_table}
""",
}

# RAG context builder output labels, per language.
_WEEKDAYS: dict[str, list[str]] = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday",
           "Friday", "Saturday", "Sunday"],
    "pt": ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
           "Sexta-feira", "Sábado", "Domingo"],
}

_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "revenue": "Revenue",
        "days_worked": "Days worked",
        "daily_avg": "Daily average",
        "ticket": "Avg ticket",
        "hours": "Estimated hours",
        "hours_day": "h/day",
        "rev_hour": "Revenue/h",
        "best_day": "Best day",
        "total_exams": "Total exams",
        "modalities": "Modalities",
        "exams": "exams",
        "exams_h": "e/h",
        "no_monthly": "(no monthly data)",
        "no_daily": "(no daily data)",
        "date_col": "Date",
    },
    "pt": {
        "revenue": "Faturamento",
        "days_worked": "Dias trabalhados",
        "daily_avg": "Média diária",
        "ticket": "Ticket médio",
        "hours": "Horas estimadas",
        "hours_day": "h/dia",
        "rev_hour": "Receita/h",
        "best_day": "Melhor dia",
        "total_exams": "Total exames",
        "modalities": "Modalidades",
        "exams": "exames",
        "exams_h": "e/h",
        "no_monthly": "(sem dados mensais)",
        "no_daily": "(sem dados diários)",
        "date_col": "Data",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Public: RAG context builder (used by chat UI)
# ═══════════════════════════════════════════════════════════════════════════


def build_rag_context(
    stats: dict[str, Any],
    active_mods: list[dict[str, Any]],
    system_prompt: str,
    lang: str = "en",
) -> str:
    """Build the full system prompt with RAG context injected.

    The answer-language instruction is always appended (EN or PT) so custom
    prompts written in the other language still steer the model correctly.
    """
    enriched = _enrich_stats(stats, active_mods, lang)
    rag_block = _RAG_TEMPLATES[lang].format(**enriched)
    instruction = translate("web.llm.answer_instruction", lang)
    return f"{system_prompt}\n\n{instruction}\n\n{rag_block}"


# ═══════════════════════════════════════════════════════════════════════════
# Private: prompt enrichment
# ═══════════════════════════════════════════════════════════════════════════


def _enrich_stats(
    stats: dict[str, Any],
    active_modalities: list[dict[str, Any]],
    lang: str = "en",
) -> dict[str, Any]:
    """Build a rich per-month breakdown + YTD summary + full daily table.

    Extracts goal and projection from current_month_stats so the RAG
    template can surface them to the LLM.
    """
    df: pd.DataFrame = stats.get("df", pd.DataFrame())
    # items_df carries price-vigent revenue (from compute_historical_stats);
    # the per-modality breakdown MUST use it, never the current modalities.price.
    items_df: pd.DataFrame = stats.get("items_df", pd.DataFrame())
    current_ym = stats.get("year_month") or ""
    current_stats = stats.get("current_month_stats", {})

    labels = _LABELS[lang]
    weekdays = _WEEKDAYS[lang]

    # ── YTD ──
    current_year = current_ym[:4] if len(current_ym) >= 4 else ""
    ytd_earnings = 0.0
    ytd_month_count = 0
    if not df.empty and current_year:
        year_df = df[df["date"].str[:4] == current_year]
        ytd_earnings = float(year_df["earnings"].sum())
        ytd_month_count = year_df["date"].str[:7].nunique()
    ytd_avg_monthly = (
        fmt_money(ytd_earnings / ytd_month_count, lang)
        if ytd_month_count > 0 else fmt_money(0.0, lang)
    )

    # ── Per-month detail ──
    months_list = sorted(df["date"].str[:7].unique()) if not df.empty else []
    detail_blocks: list[str] = []

    for ym in months_list:
        month_df = df[df["date"].str[:7] == ym]
        if month_df.empty:
            continue

        mtd = float(month_df["earnings"].sum())
        days_worked = month_df["date"].nunique()
        today = date.today()
        today_str = today.isoformat()
        has_today_data = (
            ym == today_str[:7] and today_str in set(month_df["date"].tolist())
        )
        daily_avg = daily_avg_for_month(mtd, ym, today, has_today_data)

        # Total exames + per modality
        total_exames_mes = 0
        horas_mes = 0.0
        mod_lines: list[str] = []
        for m in active_modalities:
            slug = m["slug"]
            eph = float(m.get("exams_per_hour", 0))
            mi = items_df[
                (items_df["date"].str[:7] == ym)
                & (items_df["modality_slug"] == slug)
            ] if not items_df.empty else pd.DataFrame()
            count = int(mi["count"].sum()) if not mi.empty else 0
            slug_rev = (
                float(mi["revenue"].sum())
                if (not mi.empty and "revenue" in mi.columns) else 0.0
            )
            total_exames_mes += count
            if eph > 0 and count > 0:
                horas_mes += count / eph
            if count > 0:
                pct = (slug_rev / mtd * 100) if mtd > 0 else 0.0
                ticket_exame = slug_rev / count
                rec_hora = ticket_exame * eph if eph > 0 else 0.0
                mod_lines.append(
                    f"  {m['label']}: {count} {labels['exams']}, "
                    f"{fmt_money(slug_rev, lang)} ({pct:.0f}%), "
                    f"ticket $ {ticket_exame:.2f}/{labels['exams']}, "
                    f"{eph:.1f}{labels['exams_h']} ≈ $ {rec_hora:.2f}/h"
                )

        horas_dia = horas_mes / days_worked if days_worked > 0 else 0.0
        rec_hora_mes = mtd / horas_mes if horas_mes > 0 else 0.0
        ticket = (
            fmt_money(mtd / total_exames_mes, lang)
            if total_exames_mes > 0 else fmt_money(0.0, lang)
        )

        # Best day
        best_date = "—"
        best_val = "—"
        if "earnings" in month_df.columns:
            best_idx = month_df["earnings"].idxmax()
            if pd.notna(best_idx):
                best_row = month_df.loc[best_idx]
                best_date = str(best_row.get("date", "—"))
                best_val = fmt_money(float(best_row.get("earnings", 0.0)), lang)

        block = (
            f"--- {month_name(ym, lang).upper()} ---\n"
            f"{labels['revenue']}: {fmt_money(mtd, lang)} | "
            f"{labels['days_worked']}: {days_worked} | "
            f"{labels['daily_avg']}: {fmt_money(daily_avg, lang)} | "
            f"{labels['ticket']}: {ticket}\n"
            f"{labels['hours']}: {horas_mes:.1f}h "
            f"({horas_dia:.1f}{labels['hours_day']}) | "
            f"{labels['rev_hour']}: {fmt_money(rec_hora_mes, lang)}\n"
            f"{labels['best_day']}: {best_date} ({best_val}) | "
            f"{labels['total_exams']}: {total_exames_mes}\n"
        )
        if mod_lines:
            block += f"{labels['modalities']}:\n" + "\n".join(mod_lines) + "\n"
        detail_blocks.append(block)

    monthly_detail = "\n".join(detail_blocks) if detail_blocks else labels["no_monthly"]

    # ── Full daily table ──
    full_daily_table = labels["no_daily"]
    if not df.empty:
        mod_slugs = [m["slug"] for m in active_modalities]
        available_cols = [c for c in mod_slugs if c in df.columns]
        if available_cols:
            daily_rows: list[str] = []
            header_parts = [labels["date_col"]]
            for s in available_cols:
                label = next((m["label"] for m in active_modalities if m["slug"] == s), s)
                abbr = "".join(w[0] for w in label.split() if w[0].isupper()).upper() or label[:3]
                header_parts.append(abbr)
            daily_rows.append(" | ".join(header_parts))
            daily_rows.append("|".join(["-" * len(p) for p in header_parts]))
            for _, row in df.sort_values("date").iterrows():
                date_val = str(row["date"])
                parts = [date_val]
                for s in available_cols:
                    count = int(row.get(s, 0) or 0)
                    parts.append(str(count) if count > 0 else "·")
                daily_rows.append(" | ".join(parts))
            full_daily_table = "\n".join(daily_rows)

    return {
        "today": (
            f"{MONTHS[lang][date.today().month]} {date.today().day}, "
            f"{date.today().year} ({weekdays[date.today().weekday()]})"
            if lang == "en" else
            f"{date.today().day} de {MONTHS[lang][date.today().month]}"
            f" de {date.today().year} ({weekdays[date.today().weekday()]})"
        ),
        "goal": fmt_money(float(current_stats.get("goal", 0)), lang),
        "mtd_earnings": fmt_money(float(current_stats.get("mtd_earnings", 0)), lang),
        "remaining_days": str(current_stats.get("remaining_days", 0)),
        "daily_target_needed": fmt_money(
            float(current_stats.get("daily_target_needed", 0)), lang
        ),
        "projection_month_end": fmt_money(
            float(current_stats.get("projection_month_end", 0)), lang
        ),
        "ytd_earnings": fmt_money(ytd_earnings, lang),
        "ytd_avg_monthly": ytd_avg_monthly,
        "ytd_months": str(ytd_month_count),
        "monthly_detail": monthly_detail,
        "full_daily_table": full_daily_table,
    }


class LLMClient:
    """Stateless wrapper for OpenRouter API with configurable model."""

    def __init__(
        self,
        api_key: str | None,
        model: str,
    ) -> None:
        if not api_key:
            raise LLMUnavailableError("OpenRouter API key not configured")
        if not model.strip():
            raise LLMUnavailableError("LLM model not configured")
        self._api_key = api_key
        self._model = model
        self._reasoning_buffer: list[str] = []

    # ── Public API ──

    @property
    def reasoning(self) -> str | None:
        """Full reasoning text accumulated in the last generate_stream()."""
        joined = "".join(self._reasoning_buffer)
        return joined if joined else None

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        thinking_enabled: bool = True,
        thinking_effort: str | None = None,   # low|medium|high|xhigh
        thinking_budget: int | None = None,   # 1024–32000
        thinking_mode: str = "effort",        # "effort"|"budget"
        temperature: float = 0.3,
    ) -> Generator[tuple[str, str], None, None]:
        """Call OpenRouter with stream=True, yielding (kind, token) tuples.

        Args:
            messages: Full message list (system + user + assistant).
                The caller is responsible for including the system prompt
                with the RAG context.
            thinking_enabled: If False, sends reasoning.enabled=False.
            thinking_effort: Reasoning effort level (low|medium|high|xhigh).
                Only used when thinking_mode="effort".
            thinking_budget: Exact reasoning token budget (1024–32000).
                Only used when thinking_mode="budget".
            thinking_mode: Which one to use ("effort" or "budget").
            temperature: Controls randomness (0.0–2.0).

        Yields:
            Tuples (kind, text) where kind is "reasoning" (model thinking)
            or "content" (visible answer).

        Raises:
            LLMUnavailableError: timeout, HTTP/network error, or rate limit.

        Example:
            >>> llm = LLMClient("sk-test", "model")
            >>> for kind, token in llm.generate_stream(
            ...     messages, thinking_enabled=False, temperature=0.5):
            ...     if kind == "content":
            ...         print(token, end="")
        """
        self._reasoning_buffer = []
        payload = self._build_payload(
            messages,
            thinking_enabled=thinking_enabled,
            thinking_effort=thinking_effort,
            thinking_budget=thinking_budget,
            thinking_mode=thinking_mode,
            temperature=temperature,
        )
        yielded_any = False
        try:
            with httpx.stream(
                "POST",
                _OPENROUTER_URL,
                headers=self._headers(),
                json=payload,
                timeout=30.0,  # 30s for connect + read (vs 15s non-streaming)
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices") or [{}]
                            choice = choices[0] if choices else {}
                            delta = (choice or {}).get("delta") or {}
                            # Accumulate reasoning tokens from the delta.
                            # DeepSeek V4 via OpenRouter uses "reasoning_content" in the native
                            # format; other providers (Anthropic, Qwen, Gemini) use "reasoning"
                            # as normalized by OpenRouter. Both are handled model-agnostically.
                            reasoning_token = (
                                delta.get("reasoning_content")
                                or delta.get("reasoning", "")
                            )
                            if reasoning_token:
                                self._reasoning_buffer.append(reasoning_token)
                                yield ("reasoning", reasoning_token)
                            content = delta.get("content")
                            if content:
                                yielded_any = True
                                yield ("content", content)
                        except (
                            json.JSONDecodeError,
                            KeyError,
                            IndexError,
                            AttributeError,
                            TypeError,
                        ):
                            continue  # ignora linhas malformadas
        except httpx.TimeoutException:
            raise LLMUnavailableError(
                "OpenRouter call timed out (30s)",
            ) from None
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailableError(
                f"OpenRouter HTTP {exc.response.status_code}",
            ) from exc
        except httpx.HTTPError as exc:
            # Captura ConnectError, NetworkError, etc.
            raise LLMUnavailableError(
                f"OpenRouter connection error: {exc}",
            ) from exc
        except Exception as exc:
            raise LLMUnavailableError(str(exc)) from exc

        if not yielded_any:
            raise LLMUnavailableError("Empty response from the model")

    # ── Private helpers ──

    def _headers(self) -> dict[str, str]:
        """Return Authorization + Content-Type headers for OpenRouter."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self, messages: list[dict[str, str]],
        thinking_enabled: bool = True,
        thinking_effort: str | None = None,
        thinking_budget: int | None = None,
        thinking_mode: str = "effort",
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Build the payload for generate_stream() per the OpenRouter spec.

        Args:
            messages: Lista de mensagens no formato OpenAI.
            thinking_enabled: Se False, envia reasoning.enabled=False.
            thinking_effort: Effort level (low|medium|high|xhigh).
            thinking_budget: Exact token budget (1024–32000).
            thinking_mode: Which one to use ("effort" or "budget").
            temperature: Controls randomness (0.0–2.0).

        Returns:
            Dict with the JSON payload for OpenRouter.

        Note:
            max_tokens is NOT sent — each model decides its own output cap.
            thinking_mode decide se usa effort ou budget.

        Example:
            >>> llm = LLMClient("sk-test", "model")
            >>> p = llm._build_payload([], thinking_mode="effort", thinking_effort="xhigh")
            >>> p["reasoning"]
            {'effort': 'xhigh'}
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        }

        if not thinking_enabled:
            payload["reasoning"] = {"enabled": False}
        elif thinking_mode == "budget" and thinking_budget:
            payload["reasoning"] = {"max_tokens": thinking_budget}
        elif thinking_mode == "effort" and thinking_effort:
            payload["reasoning"] = {"effort": thinking_effort}
        # else: no reasoning key → model default behavior

        return payload
