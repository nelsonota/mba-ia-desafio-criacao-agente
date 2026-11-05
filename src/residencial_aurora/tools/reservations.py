"""Adapters ADK para o domínio de reservas; identidade vem do estado da sessão."""

from google.adk.tools import ToolContext

from residencial_aurora.domain.reservations import (
    cancel_reservation,
    check_availability,
    create_paid_reservation,
    list_reservations,
)
from residencial_aurora.tools.audit import record_tool_event


def _trusted_session(tool_context: ToolContext) -> tuple[str, str]:
    apartment = tool_context.state.get("trusted_apartment")
    session_id = tool_context.state.get("api_session_id")
    if not apartment or not session_id:
        raise RuntimeError("Contexto confiável de sessão ausente.")
    return str(apartment), str(session_id)


def listar_reservas(tool_context: ToolContext) -> dict[str, object]:
    apartment, _ = _trusted_session(tool_context)
    result = {"reservas": list_reservations(apartment)}
    record_tool_event(tool_context, "listar_reservas", {}, result)
    return result


def consultar_disponibilidade(area: str, data: str, tool_context: ToolContext) -> dict[str, object]:
    result = check_availability(area, data)
    record_tool_event(tool_context, "consultar_disponibilidade", {"area": area, "data": data}, result)
    return result


def solicitar_reserva(area: str, data: str, tool_context: ToolContext) -> dict[str, object]:
    apartment, session_id = _trusted_session(tool_context)
    result = create_paid_reservation(apartment, session_id, area, data)
    confirmation = result.get("confirmation")
    if isinstance(confirmation, dict):
        confirmation.pop("apartamento", None)
    record_tool_event(tool_context, "solicitar_reserva", {"area": area, "data": data}, result)
    return result


def cancelar_reserva(area: str, data: str, tool_context: ToolContext) -> dict[str, object]:
    apartment, _ = _trusted_session(tool_context)
    result = cancel_reservation(apartment, area, data)
    record_tool_event(tool_context, "cancelar_reserva", {"area": area, "data": data}, result)
    return result
