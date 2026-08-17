"""
Chat IA tab — RAG-powered conversational assistant with OpenRouter streaming.

Entry point: render_chat_tab(conn).
Uses build_rag_context() to inject historical stats into the system prompt,
then streams token-by-token via LLMClient.generate_stream() + st.write_stream().
"""

from datetime import date
from typing import Any

import streamlit as st

from src.i18n import t
from src.llm_client import LLMClient, LLMUnavailableError, build_rag_context
from src.text_sanitize import sanitize_text, sanitize_token
from src.ui.common import get_historical_stats, render_empty_state
from src.ui.settings import ensure_settings

_MAX_MESSAGE_PAIRS = 15  # system + 15 user/assistant pairs (30 messages)
_REASONING_STATUS_MAX_CHARS = 80  # truncates the reasoning snippet (one status line)

_SUGGESTION_KEYS = (
    "web.chat.sugg.q1",
    "web.chat.sugg.q2",
    "web.chat.sugg.q3",
    "web.chat.sugg.q4",
    "web.chat.sugg.q5",
)


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
        render_empty_state(
            ":material/smart_toy:",
            t("web.chat.need_api_key"),
            title=t("web.tab.chat"),
            caption=t("web.chat.get_key"),
        )
        return

    if not active_mods:
        render_empty_state(
            ":material/smart_toy:",
            t("web.chat.need_modalities"),
            title=t("web.tab.chat"),
        )
        return

    if not st.session_state.get("user_name", "").strip():
        render_empty_state(
            ":material/smart_toy:",
            t("web.chat.need_name"),
            title=t("web.tab.chat"),
        )
        return

    if not (goal > 0.0):
        render_empty_state(
            ":material/smart_toy:",
            t("web.chat.need_goal"),
            title=t("web.tab.chat"),
        )
        return

    if not (llm_prompt or "").strip():
        render_empty_state(
            ":material/smart_toy:",
            t("web.chat.need_prompt"),
            title=t("web.tab.chat"),
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
                st.subheader(t("web.tab.chat"))
                st.markdown(t("web.chat.intro"))
                if st.button(
                    f":material/psychology: {t('web.chat.start')}",
                    type="primary",
                    key="chat_start",
                ):
                    _trigger_initial_report(
                        conn, year_month, goal, active_mods, llm_prompt,
                        st.session_state.get("lang", "en"),
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
        t("web.chat.input_ph"), key="chat_input_main"
    )
    if user_input:
        st.session_state.messages.append(
            {"role": "user", "content": user_input}
        )
        st.rerun()

    # Suggestion chips (only after initial report)
    if len(st.session_state.messages) >= 2:
        _render_suggestion_chips()

    if st.button(
        f":material/refresh: {t('web.chat.new')}",
        type="secondary",
        key="chat_new",
    ):
        st.session_state.messages = []
        st.cache_data.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Initial report trigger
# ---------------------------------------------------------------------------


def _trigger_initial_report(
    conn: Any,
    year_month: str,
    goal: float,
    active_mods: list[dict[str, Any]],
    llm_prompt: str,
    lang: str,
) -> None:
    """Compute stats, build RAG context, queue initial report prompt."""
    stats = get_historical_stats(conn, year_month, goal, active_mods)
    system_prompt = build_rag_context(stats, active_mods, llm_prompt, lang)
    st.session_state.messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": t("web.chat.initial_report")},
    ]


# ---------------------------------------------------------------------------
# Streaming dispatcher
# ---------------------------------------------------------------------------


def _stream_response(api_key: str, llm_model: str) -> None:
    """Stream assistant response for the pending user message.

    Trims history to _MAX_MESSAGE_PAIRS before sending, shows live reasoning
    tokens as a status indicator while the model thinks, passes content tokens
    to st.write_stream for progressive rendering, appends the complete
    response to st.session_state.messages when done.
    """
    _trim_history()
    with st.chat_message("assistant"):
        status_ph = st.empty()      # reasoning / status
        llm = LLMClient(api_key, model=llm_model)
        raw_stream = llm.generate_stream(
            st.session_state.messages,
            thinking_enabled=st.session_state.get("thinking_enabled", True),
            thinking_effort=st.session_state.get("thinking_effort"),
            thinking_budget=st.session_state.get("thinking_budget"),
            thinking_mode=st.session_state.get("thinking_mode", "effort"),
            temperature=st.session_state.get("temperature", 0.3),
        )

        reasoning_acc = ""   # acumula p/ snippet no status

        def content_stream():
            """Wrapper: reasoning → side effect, content → pass through."""
            nonlocal reasoning_acc
            for token_type, token in raw_stream:
                if token_type == "reasoning":
                    reasoning_acc += token
                    # Show the last complete sentence (up to 45 chars)
                    last_period = reasoning_acc.rfind(". ")
                    if last_period > 0:
                        sentence = reasoning_acc[last_period + 2:]
                    else:
                        sentence = reasoning_acc
                    snippet = sentence[:_REASONING_STATUS_MAX_CHARS]
                    # Remove quebras de linha literais do reasoning_content
                    snippet = snippet.replace("\n", " ")
                    if len(sentence) > _REASONING_STATUS_MAX_CHARS:
                        snippet = snippet.rstrip() + "…"
                    if snippet:
                        status_ph.status(
                            f":material/psychology: {snippet}",
                            expanded=False,
                        )
                else:  # "content"
                    status_ph.empty()  # limpa reasoning
                    yield sanitize_token(token)

        safe_stream = content_stream()

        try:
            response = st.write_stream(safe_stream)
        except LLMUnavailableError:
            status_ph.empty()
            response = (
                f":material/error: {t('web.chat.error.unavailable')}"
            )
            st.error(response)
        except Exception as exc:
            status_ph.empty()
            response = (
                f":material/error: {t('web.chat.error.unexpected', detail=exc)}"
            )
            st.error(response)
        # Apply full-string sanitization before storing (handles token-boundary issues)
        clean_response = sanitize_text(str(response))
        st.session_state.messages.append(
            {"role": "assistant", "content": clean_response}
        )


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


def _render_suggestion_chips() -> None:
    """Render follow-up question pills below the conversation."""
    selected = st.pills(
        t("web.chat.suggestions_label"),
        [t(key) for key in _SUGGESTION_KEYS],
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
