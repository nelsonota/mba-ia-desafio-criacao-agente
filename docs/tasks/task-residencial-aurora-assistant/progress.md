# task-residencial-aurora-assistant — Progress

**Status:** in_progress
**SIs:** 10/11 completed

### SI-1 — Preparar o projeto Python e proteger a configuração
- **Status:** completed
- **Tests:** `uv sync` concluído localmente e `uv sync --frozen` passou em imagem Python 3.12; ADK `2.6.1` travado em `uv.lock`; `.env` confirmado ignorado; hashes dos cinco arquivos em `dados/` idênticos ao HEAD.
- **Observations:**
  - `uv` instalado no `.venv` local do projeto para permitir geração do lockfile; não foi adicionado ao repositório.
  - Modelo originalmente centralizado como `gemini-3.5-flash-lite`; em 2026-11-05 foi alterado para `gemini-3.1-flash-lite` após erro de alta demanda no teste real. Chave e caminho opcional do SQLite são configuráveis pelo ambiente.

### SI-2 — Persistir estado e restaurar a base inicial
- **Status:** completed
- **Tests:** comando de restauração repetido em Docker repôs 6 apartamentos, 3 áreas, 3 reservas e 2 visitantes; índice único rejeitou conflito ativo; ledger conservou código gerado e códigos iniciais através da restauração; hashes de `dados/` intactos.
- **Observations:** comando de restauração reinicia somente reservas/autorizações de domínio e preserva sessões, eventos e pendências.

### SI-3 — Implementar regras de reservas e tools de domínio
- **Status:** completed
- **Tests:** checks em container passaram para listagem por apartamento, cancelamentos próprio e alheio, ocupação sem titular e reserva gratuita; fluxo API→AgentTool criou pendência tarifada sem gravar reserva antes da confirmação.
- **Observations:** adapters ADK leem `trusted_apartment` e `api_session_id` do estado da sessão; nenhum parâmetro de apartamento é exposto ao modelo.

### SI-4 — Implementar autorização segura de visitantes
- **Status:** completed
- **Tests:** fluxo API→AgentTool de visitantes passou com pendência nome/data vinculada à sessão, sem gravação antes da confirmação; aprovação pela API persistiu a autorização.
- **Observations:** gravação de autorização está em serviço de domínio separado, destinado ao fluxo de aprovação da API.

### SI-5 — Construir agente principal e especialistas ADK
- **Status:** completed
- **Tests:** verificação estática anterior confirmou três `AgentTool`, modelo uniforme nos quatro agentes e tools especializadas; após alteração para `gemini-3.1-flash-lite`, imagem/container precisam ser reconstruídos e retestados.
- **Observations:** especialista de regulamento conectado à tool lexical no SI-6.

### SI-6 — Consultar somente os artigos pertinentes do regulamento
- **Status:** completed
- **Tests:** fluxo API→AgentTool→especialista→tool lexical em container respondeu `20h` e gravou apenas o Art. 22 (522 caracteres) no histórico, sem capítulo não relacionado.
- **Observations:** regulamento é fragmentado e mantido apenas em cache de processo; retorno contém no máximo dois artigos curtos.

### SI-7 — Expor criação de sessão e conversa pela API
- **Status:** completed
- **Tests:** checks em container passaram para criação de sessão `201`, mensagem `200` e formato de resposta, ausência de sessão `404`, corpo inválido `422`, estado confiável, fluxo API→Runner→AgentTool→tool de domínio com quatro eventos em ordem, e retomada após reinicialização; integração com o serviço Gemini requer chave `GOOGLE_API_KEY`.
- **Observations:** SessionService do ADK persiste no SQLite; a tabela pública usa `api_sessions` para evitar colisão com a tabela interna `sessions` do ADK.

### SI-8 — Consumir confirmações duráveis uma única vez
- **Status:** completed
- **Tests:** checks em container passaram para aprovação/negação, ID alheio e reenvio `409`; reserva tarifada e visitante exercitados pelo AgentTool; aprovações HTTP concorrentes em dois workers Uvicorn, ambas `200` com exatamente uma reserva ativa.
- **Observations:** mudança de domínio, transição de estado e evento de confirmação são gravados na mesma transação SQLite.

### SI-9 — Consultar eventos persistidos da sessão
- **Status:** completed
- **Tests:** em container, eventos em sequência permaneceram disponíveis após duas inicializações de lifespan; sessão inexistente retornou `404`.
- **Observations:** endpoint lê o histórico persistido na aplicação, incluindo eventos de confirmação gravados atomicamente.

### SI-10 — Expor rotas de verificação de domínio
- **Status:** completed
- **Tests:** em container, endpoints retornaram a reserva ativa inicial do 101 e a autorização inicial de visitante do 302 sem invocar o agente.
- **Observations:** respostas seguem os campos do contrato: código/área/data e nome/data.

### SI-11 — Documentar arquitetura, garantias e operação
- **Status:** in_progress
- **Tests:** builds `uv sync --frozen` em Python 3.12 e 3.13; container Uvicorn serviu OpenAPI e rotas de verificação com os dados-base; README conferido contra comandos e símbolos presentes.
- **Observations:** documentação local está pronta. A publicação da implementação em `main` depende da revisão solicitada; nenhum commit foi feito.
