"""
Chat IA tab — RAG-powered conversational assistant with OpenRouter streaming.

Entry point: render_chat_tab(conn).
Uses build_rag_context() to inject historical stats into the system prompt,
then streams token-by-token via LLMClient.generate_stream() + st.write_stream().
"""

from datetime import date
from typing import Any

import streamlit as st

from src.calculations import compute_historical_stats
from src.llm_client import LLMClient, LLMUnavailableError, build_rag_context
from src.text_sanitize import sanitize_text, sanitize_token
from src.ui.settings import ensure_settings

_MAX_MESSAGE_PAIRS = 15  # system + 15 user/assistant pairs (30 mensagens)

_SUGGESTIONS = [
    "Qual dia foi mais produtivo?",
    "Minha média é consistente?",
    "Como está o mix de modalidades?",
    "Qual a projeção para fechar o mês?",
    "Compare esta semana com a anterior",
]


@st.fragment
def render_chat_tab(conn: Any) -> None:
    """Render the complete Chat IA tab with streaming and RAG context."""
    # ── Pastel avatar colours ──
    st.html("""
    <style>
        [data-testid="stChatMessageAvatarAssistant"] {
            background-color: #34D399 !important;
        }
        [data-testid="stChatMessageAvatarUser"] {
            background-color: #60A5FA !important;
        }
    </style>
    """)

    today = date.today()
    year_month = today.isoformat()[:7]

    ensure_settings(conn)
    api_key: str = st.session_state.get("api_key", "")
    llm_model: str = st.session_state.get("llm_model", "")
    llm_prompt: str = st.session_state.get("llm_prompt", "")
    active_mods: list[dict[str, Any]] = st.session_state.active_modalities
    goal: float = st.session_state.goal
    user_name: str = st.session_state.get("user_name", "")

    # Substitute {user_name} placeholder in the prompt
    if llm_prompt and "{user_name}" in llm_prompt:
        llm_prompt = llm_prompt.replace("{user_name}", user_name)

    if not api_key:
        _render_chat_empty_state(
            "Configure sua **chave API OpenRouter** na aba "
            ":material/settings: **Configuração** para ativar "
            "o chat com inteligência artificial.",
            caption="[Obter chave gratuita no OpenRouter](https://openrouter.ai/keys)",
        )
        return

    if not active_mods:
        _render_chat_empty_state(
            "Nenhuma modalidade ativa. Configure na aba "
            ":material/settings: **Configuração**."
        )
        return

    if not st.session_state.get("user_name", "").strip():
        _render_chat_empty_state(
            "Configure seu **nome** na aba "
            ":material/settings: **Configuração**."
        )
        return

    if not (goal > 0.0):
        _render_chat_empty_state(
            "Configure a **meta mensal** na aba "
            ":material/settings: **Configuração**."
        )
        return

    if not (llm_prompt or "").strip():
        _render_chat_empty_state(
            "Configure o **prompt da IA** na aba "
            ":material/settings: **Configuração**."
        )
        return

    # Initialize message history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # First open: show initiate button
    if not st.session_state.messages:
        _, col, _ = st.columns([1, 2, 1])
        with col:
            with st.container(border=True):
                st.markdown(
                    ":material/smart_toy:", text_alignment="center"
                )
                st.subheader("Chat com IA")
                st.markdown(
                    "O assistente analisa seus dados de produção "
                    "e responde perguntas em português."
                )
                if st.button(
                    ":material/psychology: Iniciar análise",
                    type="primary",
                    key="chat_start",
                ):
                    _trigger_initial_report(
                        conn, year_month, goal, active_mods, llm_prompt
                    )
                    st.rerun()
        return

    # Render existing messages (skip system message in UI)
    for msg in st.session_state.messages:
        if msg["role"] == "system":
            continue
        with st.chat_message(msg["role"]):
            content = msg["content"]
            if msg["role"] == "assistant":
                content = sanitize_text(content)
            st.markdown(content)

    # Dispatcher: pending user message needs assistant reply
    pending = (
        st.session_state.messages
        and st.session_state.messages[-1]["role"] == "user"
    )
    if pending:
        _stream_response(api_key, llm_model)
        st.rerun()

    # Chat input
    user_input = st.chat_input(
        "Pergunte algo sobre seus dados...", key="chat_input_main"
    )
    if user_input:
        st.session_state.messages.append(
            {"role": "user", "content": user_input}
        )
        st.rerun()

    # Suggestion chips (only after initial report)
    if len(st.session_state.messages) >= 2:
        _render_suggestion_chips()

    # Action buttons
    _render_action_buttons()


# ---------------------------------------------------------------------------
# Empty state helper
# ---------------------------------------------------------------------------

def _render_chat_empty_state(message: str, caption: str | None = None) -> None:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.container(border=True):
            st.markdown(":material/smart_toy:", text_alignment="center")
            st.subheader("Chat com IA")
            st.markdown(message)
            if caption:
                st.caption(caption)


# ---------------------------------------------------------------------------
# Cache key
# ---------------------------------------------------------------------------

def _build_historical_cache_key(
    year_month: str, goal: float, active_mods: list[dict[str, Any]]
) -> str:
    import json

    parts = {
        "ym": year_month,
        "goal": goal,
        "mods": [(m["slug"], m["price"], m["exams_per_hour"]) for m in active_mods],
    }
    return json.dumps(parts, sort_keys=True)


# ---------------------------------------------------------------------------
# Initial report trigger
# ---------------------------------------------------------------------------


def _trigger_initial_report(
    conn: Any,
    year_month: str,
    goal: float,
    active_mods: list[dict[str, Any]],
    llm_prompt: str,
) -> None:
    """Compute stats, build RAG context, queue initial report prompt."""
    cache_key = _build_historical_cache_key(year_month, goal, active_mods)
    cached = st.session_state.get("historical_cache")

    if cached is None or cached.get("key") != cache_key:
        with st.spinner("Analisando dados históricos..."):
            stats = compute_historical_stats(conn, year_month, goal, active_mods)
        st.session_state.historical_cache = {"key": cache_key, "stats": stats}
    else:
        stats = cached["stats"]

    system_prompt = build_rag_context(stats, active_mods, llm_prompt)
    st.session_state.messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Gere um relatório completo da minha produtividade."},
    ]


# ---------------------------------------------------------------------------
# Streaming dispatcher
# ---------------------------------------------------------------------------


def _stream_response(api_key: str, llm_model: str) -> None:
    """Stream assistant response for the pending user message.

    Trims history to _MAX_MESSAGE_PAIRS before sending, shows a processing
    indicator while waiting for the first token, appends the complete
    response to st.session_state.messages when done.
    """
    _trim_history()
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.status(
            ":material/psychology: Processando...", expanded=False
        )
        llm = LLMClient(api_key, model=llm_model)
        stream = llm.generate_stream(
            st.session_state.messages,
            thinking_enabled=st.session_state.get("thinking_enabled", True),
            thinking_effort=st.session_state.get("thinking_effort"),
            thinking_budget=st.session_state.get("thinking_budget"),
            temperature=st.session_state.get("temperature", 0.3),
        )
        safe_stream = (sanitize_token(token) for token in stream)
        try:
            response = st.write_stream(safe_stream)
            placeholder.empty()
        except LLMUnavailableError:
            placeholder.empty()
            response = (
                ":material/error: Não foi possível gerar a resposta. "
                "Verifique sua conexão ou chave de API."
            )
            st.error(response)
        except Exception as exc:
            placeholder.empty()
            response = (
                ":material/error: Erro inesperado ao gerar a resposta. "
                f"Detalhes: {exc}"
            )
            st.error(response)
        # Apply full-string sanitization before storing (handles token-boundary issues)
        clean_response = sanitize_text(response)
        msg: dict[str, Any] = {"role": "assistant", "content": clean_response}
        reasoning = llm.reasoning
        if reasoning:
            msg["reasoning"] = reasoning
        st.session_state.messages.append(msg)


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


def _render_suggestion_chips() -> None:
    """Render follow-up question pills below the conversation."""
    selected = st.pills(
        "Sugestões de perguntas:",
        _SUGGESTIONS,
        label_visibility="collapsed",
        key="chat_suggestions",
    )
    if selected:
        st.session_state.messages.append(
            {"role": "user", "content": selected}
        )
        st.session_state.pop("chat_suggestions", None)
        st.rerun()


# ---------------------------------------------------------------------------
# Action buttons
# ---------------------------------------------------------------------------


def _render_action_buttons() -> None:
    """Render Novo chat button."""
    if st.button(
        ":material/refresh: Novo chat",
        type="secondary",
        key="chat_new",
    ):
        st.session_state.messages = []
        st.session_state.pop("historical_cache", None)
        st.rerun()


# ---------------------------------------------------------------------------
# History management
# ---------------------------------------------------------------------------


def _trim_history() -> None:
    """Keep only system message + last N user/assistant pairs.

    Called before each LLM call to prevent token overflow.
    Preserves the system message (index 0) and trims older
    user/assistant pairs beyond _MAX_MESSAGE_PAIRS.
    """
    messages = st.session_state.messages
    if not messages or messages[0].get("role") != "system":
        return
    max_len = 1 + _MAX_MESSAGE_PAIRS * 2
    if len(messages) <= max_len:
        return
    system_msg = messages[0]
    user_assistant = [m for m in messages[1:] if m["role"] != "system"]
    kept = user_assistant[-(_MAX_MESSAGE_PAIRS * 2):]
    st.session_state.messages = [system_msg] + kept
