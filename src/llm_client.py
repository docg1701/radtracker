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
from src.formatting import fmt_brl


class LLMUnavailableError(Exception):
    """API unreachable: missing key, timeout, or HTTP error from OpenRouter."""


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_RAG_TEMPLATE = """\
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
"""


# ═══════════════════════════════════════════════════════════════════════════
# Public: RAG context builder (used by chat UI)
# ═══════════════════════════════════════════════════════════════════════════


def build_rag_context(
    stats: dict[str, Any],
    active_mods: list[dict[str, Any]],
    system_prompt: str,
) -> str:
    """Build the full system prompt with RAG context injected."""
    enriched = _enrich_stats(stats, active_mods)
    rag_block = _RAG_TEMPLATE.format(**enriched)
    return f"{system_prompt}\n\n{rag_block}"


# ═══════════════════════════════════════════════════════════════════════════
# Private: prompt enrichment
# ═══════════════════════════════════════════════════════════════════════════


def _enrich_stats(
    stats: dict[str, Any],
    active_modalities: list[dict[str, Any]],
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

    MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
              "Sexta-feira", "Sábado", "Domingo"]

    def _month_name(ym: str) -> str:
        try:
            m = int(ym[5:7])
            return MESES[m] if 1 <= m <= 12 else ym
        except (IndexError, ValueError):
            return ym

    # ── YTD ──
    current_year = current_ym[:4] if len(current_ym) >= 4 else ""
    ytd_earnings = 0.0
    ytd_month_count = 0
    if not df.empty and current_year:
        year_df = df[df["date"].str[:4] == current_year]
        ytd_earnings = float(year_df["earnings"].sum())
        ytd_month_count = year_df["date"].str[:7].nunique()
    ytd_avg_monthly = fmt_brl(ytd_earnings / ytd_month_count) if ytd_month_count > 0 else "R$ 0,00"

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
                    f"  {m['label']}: {count} exames, "
                    f"{fmt_brl(slug_rev)} ({pct:.0f}%), "
                    f"ticket R$ {ticket_exame:.2f}/exame, "
                    f"{eph:.1f}e/h ≈ R$ {rec_hora:.2f}/h"
                )

        horas_dia = horas_mes / days_worked if days_worked > 0 else 0.0
        rec_hora_mes = mtd / horas_mes if horas_mes > 0 else 0.0
        ticket = fmt_brl(mtd / total_exames_mes) if total_exames_mes > 0 else "R$ 0,00"

        # Best day
        best_date = "—"
        best_val = "—"
        if "earnings" in month_df.columns:
            best_idx = month_df["earnings"].idxmax()
            if pd.notna(best_idx):
                best_row = month_df.loc[best_idx]
                best_date = str(best_row.get("date", "—"))
                best_val = fmt_brl(float(best_row.get("earnings", 0.0)))

        block = (
            f"--- {_month_name(ym).upper()} ---\n"
            f"Faturamento: {fmt_brl(mtd)} | "
            f"Dias trabalhados: {days_worked} | "
            f"Média diária: {fmt_brl(daily_avg)} | "
            f"Ticket médio: {ticket}\n"
            f"Horas estimadas: {horas_mes:.1f}h "
            f"({horas_dia:.1f}h/dia) | "
            f"Receita/h: {fmt_brl(rec_hora_mes)}\n"
            f"Melhor dia: {best_date} ({best_val}) | "
            f"Total exames: {total_exames_mes}\n"
        )
        if mod_lines:
            block += "Modalidades:\n" + "\n".join(mod_lines) + "\n"
        detail_blocks.append(block)

    monthly_detail = "\n".join(detail_blocks) if detail_blocks else "(sem dados mensais)"

    # ── Full daily table ──
    full_daily_table = "(sem dados diários)"
    if not df.empty:
        mod_slugs = [m["slug"] for m in active_modalities]
        available_cols = [c for c in mod_slugs if c in df.columns]
        if available_cols:
            daily_rows: list[str] = []
            header_parts = ["Data"]
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
            f"{date.today().day} de {MESES[date.today().month]}"
            f" de {date.today().year} ({SEMANA[date.today().weekday()]})"
        ),
        "goal": fmt_brl(float(current_stats.get("goal", 0))),
        "mtd_earnings": fmt_brl(float(current_stats.get("mtd_earnings", 0))),
        "remaining_days": str(current_stats.get("remaining_days", 0)),
        "daily_target_needed": fmt_brl(float(current_stats.get("daily_target_needed", 0))),
        "projection_month_end": fmt_brl(float(current_stats.get("projection_month_end", 0))),
        "ytd_earnings": fmt_brl(ytd_earnings),
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
            raise LLMUnavailableError("API key não configurada")
        if not model.strip():
            raise LLMUnavailableError("Modelo LLM não configurado")
        self._api_key = api_key
        self._model = model
        self._reasoning_buffer: list[str] = []

    # ── Public API ──

    @property
    def reasoning(self) -> str | None:
        """Texto completo do reasoning acumulado no último generate_stream()."""
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
        """Chama OpenRouter com stream=True e faz yield de tuplas (tipo, token).

        Args:
            messages: Lista completa de mensagens (system + user + assistant).
                O chamador é responsável por incluir o system prompt com
                contexto RAG.
            thinking_enabled: Se False, envia reasoning.enabled=False.
            thinking_effort: Nível de esforço do reasoning (low|medium|high|xhigh).
                Só usado quando thinking_mode="effort".
            thinking_budget: Orçamento exato de tokens de reasoning (1024–32000).
                Só usado quando thinking_mode="budget".
            thinking_mode: Qual usar ("effort" ou "budget").
            temperature: Controla aleatoriedade (0.0–2.0).

        Yields:
            Tuplas (tipo, texto) onde tipo é "reasoning" (pensamento do modelo)
            ou "content" (resposta visível).

        Raises:
            LLMUnavailableError: timeout, HTTP/network error, ou rate limit.

        Example:
            >>> llm = LLMClient("sk-test", "model")
            >>> for tipo, token in llm.generate_stream(
            ...     messages, thinking_enabled=False, temperature=0.5):
            ...     if tipo == "content":
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
                timeout=30.0,  # 30s para connect + read (vs 15s do não-streaming)
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
                "Timeout ao chamar OpenRouter (30s)",
            ) from None
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailableError(
                f"OpenRouter HTTP {exc.response.status_code}",
            ) from exc
        except httpx.HTTPError as exc:
            # Captura ConnectError, NetworkError, etc.
            raise LLMUnavailableError(
                f"Erro de conexão com OpenRouter: {exc}",
            ) from exc
        except Exception as exc:
            raise LLMUnavailableError(str(exc)) from exc

        if not yielded_any:
            raise LLMUnavailableError("Resposta vazia do modelo")

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
        """Monta o payload para generate_stream() seguindo especificação OpenRouter.

        Args:
            messages: Lista de mensagens no formato OpenAI.
            thinking_enabled: Se False, envia reasoning.enabled=False.
            thinking_effort: Nível de esforço (low|medium|high|xhigh).
            thinking_budget: Orçamento exato de tokens (1024–32000).
            thinking_mode: Qual usar ("effort" ou "budget").
            temperature: Controla aleatoriedade (0.0–2.0).

        Returns:
            Dicionário com o payload JSON para OpenRouter.

        Note:
            max_tokens NÃO é enviado — cada modelo decide seu próprio teto de output.
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
