"""Tool ADK de consulta lexical ao regulamento."""

from google.adk.tools import ToolContext

from residencial_aurora.domain.regulation import search_regulation
from residencial_aurora.tools.audit import record_tool_event


def consultar_regulamento(pergunta: str, tool_context: ToolContext) -> dict[str, object]:
    """Retorna somente os artigos mais pertinentes à pergunta."""
    result = search_regulation(pergunta)
    record_tool_event(tool_context, "consultar_regulamento", {"pergunta": pergunta}, result)
    return result
