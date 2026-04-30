"""
LLM client for radtracker — OpenRouter API (GPT-OSS 120B, free tier).

Stateless wrapper. Constructor takes API key; generate() takes stats dict
and returns Portuguese markdown insight text.

Usage:
    try:
        llm = LLMClient(api_key)
        insight = llm.generate(stats)
    except LLMUnavailableError:
        insight = generate_rule_insights(stats)  # fallback
"""

from typing import Any

import httpx
import pandas as pd

from src.formatting import fmt_brl


class LLMUnavailableError(Exception):
    """API unreachable: missing key, timeout, or HTTP error from OpenRouter."""


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL = "openai/gpt-oss-120b:free"

SYSTEM_PROMPT = (
    "Você é um assistente pessoal de produtividade para um médico "
    "radiologista chamado Galvani. "
    "Analise os dados de produção abaixo e produza uma análise completa "
    "e detalhada em português, com tom amigável, direto e profissional. "
    "Use os números reais. Analise tendências, sazonalidade, composição "
    "do mix de modalidades, ritmo de trabalho, projeções e riscos. "
    "Seja analítico e profundo. Dê sugestões acionáveis e específicas, "
    "cite valores exatos e compare com períodos anteriores."
)


_USER_PROMPT_TEMPLATE = """\
Dados completos da produção:

=== META E RITMO ===
- Faturamento no mês (MTD): {mtd}
- Percentual da meta: {pct:.0f}%
- Meta mensal: {meta_mensal}
- Dias trabalhados: {dias_trabalhados} de {total_dias} dias no mês
- Dias restantes: {dias_restantes}
- Média diária atual: {media_diaria}
- Meta diária necessária (para bater a meta): {meta_diaria}
- Projeção de fechamento do mês: {projecao}
- Dias consecutivos abaixo da meta diária: {consecutivos}

=== TENDÊNCIAS ===
- Variação vs semana anterior (WoW): {wow}
- Variação vs mês anterior (MoM): {mom}
- Média móvel 7 dias (último valor): {ma7}
- Média móvel 30 dias (último valor): {ma30}
- Média histórica mensal (todos os meses): {media_historica}
- Tendência de aceleração/desaceleração: {tendencia}

=== VOLUME DE EXAMES ===
- Total de exames no mês: {total_exames}
- RM: {total_rm} exames ({mix_rm:.1f}% da receita)
- TC: {total_tc} exames ({mix_tc:.1f}% da receita)
- RX: {total_rx} exames ({mix_rx:.1f}% da receita)

=== DESTAQUES DO MÊS ===
- Dia mais produtivo: {dia_produtivo} com {valor_dia_produtivo}
- Média de exames por dia: {media_exames_dia:.0f}
- Ticket médio por exame: {ticket_medio}

Produza uma análise completa e detalhada. Use **negrito** para destaques.
Inclua: avaliação do ritmo, tendências de curto e longo prazo, análise
do mix de modalidades, riscos e oportunidades, e recomendações práticas."""


def _enrich_stats(stats: dict[str, Any], prices: dict[str, float]) -> dict[str, Any]:
    """Extract scalar metrics from the stats DataFrame for the prompt.

    Computes: MA7/MA30 latest, total exam counts, best day, historical
    monthly average, acceleration trend, ticket médio.

    Args:
        stats: Dict from compute_historical_stats().
        prices: Prices dict for computing ticket médio.

    Returns:
        Flat dict of scalar values safe for string interpolation.
    """
    df: pd.DataFrame = stats.get("df", pd.DataFrame())
    current = stats.get("current_month_stats", {})
    mix = stats.get("modality_mix_current", {})

    # ── MA7 / MA30 latest ──
    ma7_val = 0.0
    ma30_val = 0.0
    if not df.empty and "ma7" in df.columns and "ma30" in df.columns:
        last_row = df.iloc[-1]
        ma7_val = float(last_row.get("ma7", 0.0) or 0.0)
        ma30_val = float(last_row.get("ma30", 0.0) or 0.0)

    # ── Acceleration trend: compare last 7 days MA7 change ──
    tendencia = "estável"
    if not df.empty and len(df) >= 14:
        recent = df["ma7"].iloc[-1] if pd.notna(df["ma7"].iloc[-1]) else 0.0
        prior = df["ma7"].iloc[-8] if pd.notna(df["ma7"].iloc[-8]) else 0.0
        if prior > 0 and recent > 0:
            delta = (recent - prior) / prior * 100
            if delta > 5:
                tendencia = f"acelerando (+{delta:.0f}% na última semana)"
            elif delta < -5:
                tendencia = f"desacelerando ({delta:.0f}% na última semana)"

    # ── Total exam counts ──
    total_rm = total_tc = total_rx = 0
    if not df.empty:
        total_rm = int(df["rm_count"].sum())
        total_tc = int(df["tc_count"].sum())
        total_rx = int(df["rx_count"].sum())
    total_exames = total_rm + total_tc + total_rx

    # ── Best day ──
    dia_produtivo = "—"
    valor_dia_produtivo = "—"
    if not df.empty and "earnings" in df.columns:
        best_idx = df["earnings"].idxmax()
        if pd.notna(best_idx):
            best_row = df.loc[best_idx]
            dia_produtivo = str(best_row.get("date", "—"))
            valor_dia_produtivo = fmt_brl(float(best_row.get("earnings", 0.0)))

    # ── Historical monthly average ──
    media_historica = "R$ 0,00"
    if not df.empty and len(df) >= 30:
        total_earnings = float(df["earnings"].sum())
        unique_months = df["date"].str[:7].nunique()
        if unique_months > 0:
            media_historica = fmt_brl(total_earnings / unique_months)

    # ── Average exams per day ──
    days_worked = current.get("days_worked", 0)
    media_exames_dia = total_exames / days_worked if days_worked > 0 else 0.0

    # ── Ticket médio ──
    rm_rev = float(total_rm) * prices.get("rm", 35.0)
    tc_rev = float(total_tc) * prices.get("tc", 25.0)
    rx_rev = float(total_rx) * prices.get("rx", 4.5)
    total_rev = rm_rev + tc_rev + rx_rev
    ticket_medio = fmt_brl(total_rev / total_exames) if total_exames > 0 else "R$ 0,00"

    return {
        # Meta e ritmo
        "mtd": fmt_brl(current.get("mtd_earnings", 0.0)),
        "pct": current.get("pct_goal", 0.0),
        "meta_mensal": fmt_brl(stats.get("current_month_stats", {}).get("mtd_earnings", 0.0)
                                / max(current.get("pct_goal", 1.0), 0.01) * 100),
        "dias_trabalhados": days_worked,
        "total_dias": current.get("total_calendar_days", 0),
        "dias_restantes": current.get("remaining_calendar_days", 0),
        "media_diaria": fmt_brl(current.get("daily_avg", 0.0)),
        "meta_diaria": fmt_brl(max(0.0, current.get("daily_target_needed", 0.0))),
        "projecao": fmt_brl(current.get("projection_month_end", 0.0)),
        "consecutivos": stats.get("consecutive_below_target", 0),
        # Tendências
        "wow": f"{stats.get('wow_change_pct'):+.1f}%"
               if stats.get("wow_change_pct") is not None else "sem dados suficientes",
        "mom": f"{stats.get('mom_change_pct'):+.1f}%"
               if stats.get("mom_change_pct") is not None else "sem dados suficientes",
        "ma7": fmt_brl(ma7_val),
        "ma30": fmt_brl(ma30_val),
        "media_historica": media_historica,
        "tendencia": tendencia,
        # Volume
        "total_exames": total_exames,
        "total_rm": total_rm,
        "total_tc": total_tc,
        "total_rx": total_rx,
        "mix_rm": mix.get("rm", 0.0),
        "mix_tc": mix.get("tc", 0.0),
        "mix_rx": mix.get("rx", 0.0),
        # Destaques
        "dia_produtivo": dia_produtivo,
        "valor_dia_produtivo": valor_dia_produtivo,
        "media_exames_dia": media_exames_dia,
        "ticket_medio": ticket_medio,
    }


class LLMClient:
    """Stateless wrapper for OpenRouter free tier (GPT-OSS 120B)."""

    def __init__(self, api_key: str | None) -> None:
        if not api_key:
            raise LLMUnavailableError("API key não configurada")
        self._api_key = api_key

    def generate(self, stats: dict[str, Any]) -> str:
        """Call GPT-OSS 120B via OpenRouter and return Portuguese insight.

        Args:
            stats: Dict from compute_historical_stats() (same shape used by
                   generate_rule_insights).

        Returns:
            Markdown-formatted Portuguese insight text.

        Raises:
            LLMUnavailableError: timeout (>15s), HTTP error, or rate limit.
        """
        user_prompt = self._build_prompt(stats)
        payload = {
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 800,
            "temperature": 0.3,
        }
        try:
            response = httpx.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15.0,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException:
            raise LLMUnavailableError("Timeout ao chamar OpenRouter (15s)") from None
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailableError(
                f"OpenRouter HTTP {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise LLMUnavailableError(str(exc)) from exc

        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_prompt(self, stats: dict[str, Any]) -> str:
        """Enrich stats with DataFrame-derived metrics and interpolate template."""
        # Extract prices from the current_month_stats calculation context
        # The stats dict doesn't directly carry prices, but we can infer them
        # from the modality_mix_current and raw counts.
        current = stats.get("current_month_stats", {})
        goal = current.get("mtd_earnings", 0.0) / max(current.get("pct_goal", 1.0), 0.01) * 100

        prices: dict[str, float] = {"rm": 35.0, "tc": 25.0, "rx": 4.5}
        enriched = _enrich_stats(stats, prices)

        # Fix meta_mensal (overwrite the rough calc)
        enriched["meta_mensal"] = fmt_brl(goal)

        return _USER_PROMPT_TEMPLATE.format(**enriched)
