"""Registro das chamadas internas dos especialistas no histórico da API."""

from typing import Any

from google.adk.tools import ToolContext

from residencial_aurora.storage.sessions import append_event


def record_tool_event(
    tool_context: ToolContext,
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Persiste chamada e resultado permitido sem depender de eventos aninhados do Runner."""
    session_id = tool_context.state.get("api_session_id")
    if not session_id:
        return
    append_event(
        str(session_id),
        {
            "type": "tool",
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
        },
    )
