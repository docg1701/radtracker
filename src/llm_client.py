"""
LLM client for radtracker — OpenRouter API (configurable model).

Stateless wrapper. Constructor takes API key and model slug;
generate() takes stats dict + active_modalities and returns
Portuguese markdown insight text.
generate_stream() does SSE token-by-token streaming.

Usage:
    try:
        llm = LLMClient(api_key, model)
        insight = llm.generate(stats, active_modalities)
    except LLMUnavailableError:
        insight = generate_rule_insights(stats)  # fallback

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

_SYSTEM_PROMPT = (
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

=== VOLUME DE EXAMES (por modalidade) ===
{modality_breakdown}

=== DESTAQUES DO MÊS ===
- Dia mais produtivo: {dia_produtivo} com {valor_dia_produtivo}
- Média de exames por dia: {media_exames_dia:.0f}
- Ticket médio por exame: {ticket_medio}

Produza uma análise completa e detalhada. Use **negrito** para destaques.
Inclua: avaliação do ritmo, tendências de curto e longo prazo, análise
do mix de modalidades, riscos e oportunidades, e recomendações práticas."""


# ═══════════════════════════════════════════════════════════════════════════
# Public: RAG context builder (used by chat UI)
# ═══════════════════════════════════════════════════════════════════════════


def build_rag_context(
    stats: dict[str, Any],
    active_mods: list[dict[str, Any]],
    system_prompt: str | None = None,
) -> str:
    """Monta o system prompt com dados estruturados dos stats para RAG.

    Args:
        stats: Dict de compute_historical_stats().
        active_mods: Lista de modalidades ativas.
        system_prompt: Prompt personalizado do usuário (settings).
                       Se None ou string vazia, usa o prompt padrão
                       (_SYSTEM_PROMPT).

    Returns:
        String completa do system prompt com contexto RAG injetado.
    """
    enriched = _enrich_stats(stats, active_mods)
    user_prompt = _USER_PROMPT_TEMPLATE.format(**enriched)
    prompt = system_prompt or _SYSTEM_PROMPT
    return f"""{prompt}

=== DADOS ATUAIS PARA ANÁLISE ===
Os dados abaixo são o contexto da conversa. Use-os para responder perguntas.
Quando o usuário pedir "relatório", gere uma análise completa com esses dados.

{user_prompt}
"""


# ═══════════════════════════════════════════════════════════════════════════
# Private: prompt enrichment
# ═══════════════════════════════════════════════════════════════════════════


def _enrich_stats(
    stats: dict[str, Any],
    active_modalities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Extract scalar metrics from stats + modality data for the prompt."""
    df: pd.DataFrame = stats.get("df", pd.DataFrame())
    current = stats.get("current_month_stats", {})
    mix = stats.get("modality_mix_current", {})

    # ── MA7 / MA30 latest ──
    ma7_val = 0.0
    ma30_val = 0.0
    if not df.empty and "ma7" in df.columns and "ma30" in df.columns:
        last_row = df.iloc[-1]
        raw_ma7 = last_row.get("ma7", 0.0)
        raw_ma30 = last_row.get("ma30", 0.0)
        ma7_val = float(raw_ma7) if pd.notna(raw_ma7) else 0.0
        ma30_val = float(raw_ma30) if pd.notna(raw_ma30) else 0.0

    # ── Acceleration trend ──
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

    # ── Total exam counts per modality (current month) ──
    total_exames = 0
    modality_lines: list[str] = []
    current_ym = stats.get("year_month") or ""
    for m in active_modalities:
        slug = m["slug"]
        count_col = slug
        count = 0
        if not df.empty and count_col in df.columns:
            month_df = df[df["date"].str[:7] == current_ym]
            count = int(month_df[count_col].sum()) if not month_df.empty else 0
        total_exames += count
        mix_pct = mix.get(slug, 0.0)
        modality_lines.append(
            f"- {m['label']}: {count} exames ({mix_pct:.1f}% da receita)"
        )
    modality_breakdown = "\n".join(modality_lines)

    # ── Best day ──
    dia_produtivo = "—"
    valor_dia_produtivo = "—"
    if not df.empty and "earnings" in df.columns:
        month_df = df[df["date"].str[:7] == current_ym]
        if not month_df.empty:
            best_idx = month_df["earnings"].idxmax()
            if pd.notna(best_idx):
                best_row = month_df.loc[best_idx]
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
    mtd = current.get("mtd_earnings", 0.0)
    ticket_medio = fmt_brl(mtd / total_exames) if total_exames > 0 else "R$ 0,00"

    return {
        "mtd": fmt_brl(mtd),
        "pct": current.get("pct_goal", 0.0),
        "meta_mensal": fmt_brl(mtd / max(current.get("pct_goal", 1.0), 0.01) * 100
                                if current.get("pct_goal", 0) > 0 else 0),
        "dias_trabalhados": days_worked,
        "total_dias": current.get("total_calendar_days", 0),
        "dias_restantes": current.get("remaining_calendar_days", 0),
        "media_diaria": fmt_brl(current.get("daily_avg", 0.0)),
        "meta_diaria": fmt_brl(max(0.0, current.get("daily_target_needed", 0.0))),
        "projecao": fmt_brl(current.get("projection_month_end", 0.0)),
        "consecutivos": stats.get("consecutive_below_target", 0),
        "wow": f"{stats.get('wow_change_pct'):+.1f}%"
               if stats.get("wow_change_pct") is not None else "sem dados suficientes",
        "mom": f"{stats.get('mom_change_pct'):+.1f}%"
               if stats.get("mom_change_pct") is not None else "sem dados suficientes",
        "ma7": fmt_brl(ma7_val),
        "ma30": fmt_brl(ma30_val),
        "media_historica": media_historica,
        "tendencia": tendencia,
        "modality_breakdown": modality_breakdown,
        "dia_produtivo": dia_produtivo,
        "valor_dia_produtivo": valor_dia_produtivo,
        "media_exames_dia": media_exames_dia,
        "ticket_medio": ticket_medio,
    }


class LLMClient:
    """Stateless wrapper for OpenRouter API with configurable model."""

    def __init__(
        self,
        api_key: str | None,
        model: str = "openai/gpt-oss-120b:free",
        prompt: str | None = None,
    ) -> None:
        if not api_key:
            raise LLMUnavailableError("API key não configurada")
        self._api_key = api_key
        self._model = model
        self._prompt = prompt or _SYSTEM_PROMPT

    # ── Public API ──

    def generate(
        self,
        stats: dict[str, Any],
        active_modalities: list[dict[str, Any]],
    ) -> str:
        """Call the configured model via OpenRouter and return Portuguese insight.

        Args:
            stats: Dict from compute_historical_stats().
            active_modalities: List of active modality dicts.

        Returns:
            Markdown-formatted Portuguese insight text.

        Raises:
            LLMUnavailableError: timeout, HTTP error, or rate limit.
        """
        user_prompt = self._build_prompt(stats, active_modalities)
        messages = [
            {"role": "system", "content": self._prompt},
            {"role": "user", "content": user_prompt},
        ]
        payload = self._build_payload(messages)
        try:
            response = httpx.post(
                _OPENROUTER_URL,
                headers=self._headers(),
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
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(
                f"Erro de conexão com OpenRouter: {exc}"
            ) from exc
        except Exception as exc:
            raise LLMUnavailableError(str(exc)) from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailableError(
                f"Resposta inesperada da API: {exc}"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMUnavailableError("Resposta vazia ou bloqueada pelo modelo")
        return content

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
        """Monta o payload comum para generate() e generate_stream()."""
        return {
            "model": self._model,
            "messages": messages,
            "stream": stream,
            "max_tokens": 800,
            "temperature": 0.3,
        }

    def _build_prompt(
        self,
        stats: dict[str, Any],
        active_modalities: list[dict[str, Any]],
    ) -> str:
        """Enrich stats with DataFrame-derived metrics and interpolate template."""
        enriched = _enrich_stats(stats, active_modalities)
        return _USER_PROMPT_TEMPLATE.format(**enriched)
