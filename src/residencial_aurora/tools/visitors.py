"""Adapters ADK de visitantes baseados na identidade confiável da sessão."""

from google.adk.tools import ToolContext

from residencial_aurora.domain.visitors import list_visitors, request_visitor_authorization
from residencial_aurora.tools.reservations import _trusted_session
from residencial_aurora.tools.audit import record_tool_event


def listar_visitantes_autorizados(tool_context: ToolContext) -> dict[str, object]:
    apartment, _ = _trusted_session(tool_context)
    result = {"autorizacoes": list_visitors(apartment)}
    record_tool_event(tool_context, "listar_visitantes_autorizados", {}, result)
    return result


def solicitar_autorizacao_visitante(
    nome: str, data: str, tool_context: ToolContext
) -> dict[str, object]:
    apartment, session_id = _trusted_session(tool_context)
    result = request_visitor_authorization(apartment, session_id, nome, data)
    confirmation = result.get("confirmation")
    if isinstance(confirmation, dict):
        confirmation.pop("apartamento", None)
    record_tool_event(
        tool_context,
        "solicitar_autorizacao_visitante",
        {"nome": nome, "data": data},
        result,
    )
    return result
