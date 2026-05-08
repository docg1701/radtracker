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
from typing import Any

import httpx
import pandas as pd

from src.formatting import fmt_brl


class LLMUnavailableError(Exception):
    """API unreachable: missing key, timeout, or HTTP error from OpenRouter."""


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_RAG_TEMPLATE = """\
=== DADOS ATUAIS PARA ANÁLISE ===
Os dados abaixo são o contexto da conversa. Use-os para responder perguntas.
Quando o usuário pedir "relatório" ou "análise", use TODOS os meses, não
apenas o mês atual.

=== RESUMO DO ANO (YTD) ===
Faturamento acumulado: {ytd_earnings} | Média mensal: {ytd_avg_monthly}
Meses com dados: {ytd_months}

=== DETALHES POR MÊS ===
{monthly_detail}

=== DADOS DIÁRIOS COMPLETOS (todas as modalidades, todos os dias) ===
{full_daily_table}

Produza uma análise completa e detalhada. Use **negrito** para destaques.
Inclua: avaliação do ritmo, tendências de curto e longo prazo, análise
do mix de modalidades, riscos e oportunidades, e recomendações práticas.
Compare os meses entre si.
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
    """Build a rich per-month breakdown + YTD summary + full daily table."""
    df: pd.DataFrame = stats.get("df", pd.DataFrame())
    current_ym = stats.get("year_month") or ""

    MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

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
        daily_avg = mtd / days_worked if days_worked > 0 else 0.0

        # Total exames + per modality
        total_exames_mes = 0
        horas_mes = 0.0
        mod_lines: list[str] = []
        for m in active_modalities:
            slug = m["slug"]
            price = float(m.get("price", 0))
            eph = float(m.get("exams_per_hour", 0))
            count = int(month_df[slug].sum()) if slug in month_df.columns else 0
            total_exames_mes += count
            if eph > 0 and count > 0:
                horas_mes += count / eph
            if count > 0:
                pct = (count * price / mtd * 100) if mtd > 0 else 0.0
                rec_hora = price * eph if eph > 0 else 0.0
                mod_lines.append(
                    f"  {m['label']}: {count} exames, "
                    f"{fmt_brl(count * price)} ({pct:.0f}%), "
                    f"R$ {price:.2f}/exame, "
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

    # ── Public API ──

    def generate_stream(
        self,
        messages: list[dict[str, str]],
    ) -> Generator[str, None, None]:
        """Chama OpenRouter com stream=True e faz yield de tokens.

        Args:
            messages: Lista completa de mensagens (system + user + assistant).
                O chamador é responsável por incluir o system prompt com
                contexto RAG.

        Yields:
            Tokens de texto conforme chegam via SSE.

        Raises:
            LLMUnavailableError: timeout, HTTP/network error, ou rate limit.
        """
        payload = self._build_payload(messages, stream=True)
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
                            content = delta.get("content")
                            if content:
                                yielded_any = True
                                yield content
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
        self, messages: list[dict[str, str]], stream: bool = False,
    ) -> dict[str, Any]:
        """Monta o payload para generate_stream()."""
        return {
            "model": self._model,
            "messages": messages,
            "stream": stream,
            "max_tokens": 800,
            "temperature": 0.3,
        }
