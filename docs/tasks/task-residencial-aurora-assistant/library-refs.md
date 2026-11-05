---
libs:
  fastapi:
    version: "current documentation (no version surfaced by Context7)"
    context7_id: "/websites/fastapi_tiangolo"
    fetched_at: "2026-11-05T00:00:39.4323779Z"
  uvicorn:
    version: "0.54.0"
    context7_id: "/websites/uvicorn_dev"
    fetched_at: "2026-11-05T00:00:39.4323779Z"
  google-adk:
    version: "v2.6.1 docs"
    context7_id: "/google/adk-python"
    fetched_at: "2026-11-05T00:00:39.4323779Z"
sources_mtime:
  docs/decisions/technical-decisions-residencial-aurora-assistant.md: "2026-11-05T00:00:31.7680666Z"
---

# Library References

### fastapi

Use typed Pydantic request models for JSON bodies; FastAPI validates and documents those shapes in OpenAPI. Async path operations can await asynchronous work, which fits the ADK calls in the API flow. Sources: [Request bodies](https://fastapi.tiangolo.com/tutorial/body/), [Async](https://fastapi.tiangolo.com/async/).

### uvicorn

Run the ASGI app on the challenge's local endpoint with `uvicorn <module>:app --host 127.0.0.1 --port 8000`; those host and port settings match the documented defaults. Source: [Settings](https://uvicorn.dev/settings/).

### google-adk

Wrap each specialist as `AgentTool(agent=specialist)` in the parent `LlmAgent.tools` list. The parent model explicitly invokes it, receives its answer as a tool result, and retains turn control. The ADK documentation example uses `from google.adk.tools import AgentTool`. Source: [AgentTool](https://github.com/google/adk-python/blob/main/docs/guides/tools/agent_tool/index.md).
