"""API HTTP JSON para sessões e conversas do Residencial Aurora."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, field_validator

from residencial_aurora.agents import APP_NAME, root_agent
from residencial_aurora.config import settings
from residencial_aurora.domain.confirmations import consume_confirmation
from residencial_aurora.domain.reservations import list_reservations_for_verification
from residencial_aurora.domain.visitors import list_visitors
from residencial_aurora.storage import ensure_initial_data
from residencial_aurora.storage.database import connect
from residencial_aurora.storage.sessions import (
    append_event,
    create_session as store_session,
    get_session,
    list_events,
    list_pending_confirmations,
)


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    apartamento: str = Field(min_length=1)

    @field_validator("apartamento")
    @classmethod
    def normalize_apartment(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("apartamento não pode ficar vazio")
        return normalized


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    texto: str = Field(min_length=1)


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    confirmado: bool


def _adk_database_url(path: Path) -> str:
    absolute = path.resolve().as_posix()
    return f"sqlite+aiosqlite:///{absolute}"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ensure_initial_data()
    session_service = DatabaseSessionService(db_url=_adk_database_url(settings.database_path))
    app.state.session_service = session_service
    app.state.runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=session_service)
    app.state.session_locks = {}
    yield


app = FastAPI(
    title="Assistente do Residencial Aurora",
    description="API de sessões e conversas para o desafio Full Cycle.",
    version="0.1.0",
    lifespan=lifespan,
)


def _require_session(session_id: str) -> dict[str, str]:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"errorCode": "SESSION_NOT_FOUND"})
    return session


async def _run_message(request: Request, session: dict[str, str], text: str) -> dict[str, Any]:
    if not settings.google_api_key:
        raise HTTPException(
            status_code=503,
            detail={"errorCode": "MODEL_CREDENTIALS_MISSING", "message": "Configure GOOGLE_API_KEY no ambiente."},
        )

    session_id = session["session_id"]
    lock = request.app.state.session_locks.setdefault(session_id, asyncio.Lock())
    async with lock:
        response_text = ""
        async for event in request.app.state.runner.run_async(
            user_id=session_id,
            session_id=session["adk_session_id"],
            new_message=types.Content(role="user", parts=[types.Part(text=text)]),
            state_delta={"trusted_apartment": session["apartamento"], "api_session_id": session_id},
        ):
            event_payload = event.model_dump(mode="json", exclude_none=True)
            append_event(session_id, event_payload)
            if event.is_final_response() and event.content and event.content.parts:
                response_text = "".join(part.text or "" for part in event.content.parts)
        return {"resposta": response_text, "confirmacoes_pendentes": list_pending_confirmations(session_id)}


@app.post("/sessoes", status_code=status.HTTP_201_CREATED)
async def create_session(body: CreateSessionRequest, request: Request) -> dict[str, str]:
    apartment = body.apartamento
    session_id = str(uuid.uuid4())
    adk_session_id = str(uuid.uuid4())
    store_session(session_id, apartment, adk_session_id)
    try:
        await request.app.state.session_service.create_session(
            app_name=APP_NAME,
            user_id=session_id,
            session_id=adk_session_id,
            state={"trusted_apartment": apartment, "api_session_id": session_id},
        )
    except Exception:
        # Evita deixar uma sessão pública sem estado ADK recuperável.
        with connect() as connection:
            connection.execute("DELETE FROM api_sessions WHERE session_id = ?", (session_id,))
        raise
    return {"session_id": session_id}


@app.post("/sessoes/{session_id}/mensagens")
async def send_message(session_id: str, body: MessageRequest, request: Request) -> dict[str, Any]:
    session = _require_session(session_id)
    return await _run_message(request, session, body.texto)


@app.post("/sessoes/{session_id}/confirmacoes")
async def confirm_action(
    session_id: str, body: ConfirmationRequest, request: Request
) -> dict[str, Any]:
    _require_session(session_id)
    result = consume_confirmation(session_id, body.id, body.confirmado)
    if result is None:
        raise HTTPException(
            status_code=409,
            detail={"errorCode": "CONFIRMATION_NOT_PENDING"},
        )
    if result.get("message"):
        response_text = str(result["message"])
    elif result.get("status") == "reserved":
        response_text = f"Reserva confirmada. Código: {result['codigo']}."
    else:
        response_text = "Ação confirmada."
    return {"resposta": response_text, "confirmacoes_pendentes": list_pending_confirmations(session_id)}


@app.get("/sessoes/{session_id}/eventos")
async def get_session_events(session_id: str) -> list[dict[str, Any]]:
    _require_session(session_id)
    return list_events(session_id)


@app.get("/apartamentos/{apartamento}/reservas")
async def verify_apartment_reservations(apartamento: str) -> list[dict[str, str]]:
    return list_reservations_for_verification(apartamento)


@app.get("/apartamentos/{apartamento}/visitantes")
async def verify_apartment_visitors(apartamento: str) -> list[dict[str, str]]:
    return list_visitors(apartamento)
