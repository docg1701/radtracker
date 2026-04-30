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

from src.formatting import fmt_brl


class LLMUnavailableError(Exception):
    """API unreachable: missing key, timeout, or HTTP error from OpenRouter."""


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL = "openai/gpt-oss-120b:free"

SYSTEM_PROMPT = (
    "Você é um assistente pessoal de produtividade para um médico "
    "radiologista chamado Galvani. "
    "Analise os dados de produção abaixo e gere um parágrafo de insights "
    "em português, com tom amigável e direto. Use os números reais. "
    "Dê sugestões acionáveis."
)


_USER_PROMPT_TEMPLATE = """\
Dados:
- Faturamento no mês (MTD): {mtd}
- Percentual da meta: {pct:.0f}%
- Dias trabalhados: {dias_trabalhados} de {total_dias} dias úteis
- Média diária: {media_diaria}
- Meta diária necessária: {meta_diaria}
- Projeção de fechamento: {projecao}
- Variação semana a semana: {wow}
- Variação mês a mês: {mom}
- Mix atual: RM {mix_rm:.1f}%, TC {mix_tc:.1f}%, RX {mix_rx:.1f}%
- Dias consecutivos abaixo da meta: {consecutivos}

Responda APENAS com o texto do insight, sem introduções, sem "Aqui está sua análise:".
Use **negrito** para destaques. Máximo 3 parágrafos."""


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
            "max_tokens": 600,
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
        """Sanitize stats, interpolate into the Portuguese prompt template.

        None-safe: wow/mom that are None become "sem dados suficientes".
        """
        current = stats.get("current_month_stats", {})
        mix = stats.get("modality_mix_current", {})

        mtd = current.get("mtd_earnings", 0.0)
        pct = current.get("pct_goal", 0.0)
        days_worked = current.get("days_worked", 0)
        total_days = current.get("total_calendar_days", 0)
        daily_avg = current.get("daily_avg", 0.0)

        remaining_needed = max(0.0, current.get("daily_target_needed", 0.0))
        projection = current.get("projection_month_end", 0.0)

        wow = stats.get("wow_change_pct")
        mom = stats.get("mom_change_pct")
        consecutive = stats.get("consecutive_below_target", 0)

        # ── None sanitization (avoids "None%" in the prompt) ──
        wow_str = f"{wow:+.1f}%" if wow is not None else "sem dados suficientes"
        mom_str = f"{mom:+.1f}%" if mom is not None else "sem dados suficientes"

        return _USER_PROMPT_TEMPLATE.format(
            mtd=fmt_brl(mtd),
            pct=pct,
            dias_trabalhados=days_worked,
            total_dias=total_days,
            media_diaria=fmt_brl(daily_avg),
            meta_diaria=fmt_brl(remaining_needed),
            projecao=fmt_brl(projection),
            wow=wow_str,
            mom=mom_str,
            mix_rm=mix.get("rm", 0.0),
            mix_tc=mix.get("tc", 0.0),
            mix_rx=mix.get("rx", 0.0),
            consecutivos=consecutive,
        )
