---
kind: task
name: task-residencial-aurora-assistant
test_specs_aware: true
sources_mtime:
  docs/tasks/task-residencial-aurora-assistant/context.md: "2026-11-05T00:07:29.9992781Z"
  docs/tasks/task-residencial-aurora-assistant/library-refs.md: "2026-11-05T00:20:45.9376888Z"
  docs/decisions/technical-decisions-residencial-aurora-assistant.md: "2026-11-05T00:00:31.7680666Z"
---

# Assistente do Residencial Aurora — Task Plan

## Objective

Implementar a entrega completa do desafio Full Cycle do assistente do Residencial Aurora conforme os critérios verificáveis abaixo, transcritos e organizados da seção “Critérios de aceite” e do fluxo do avaliador na página do desafio. Os cinco arquivos de `dados/` são imutáveis. Requisitos expressamente fora de escopo estão listados ao final desta seção.

---

## Step Implementations

### SI-1 — Preparar o projeto Python e proteger a configuração

**Description:** Estruturar o pacote Python executável em clone limpo, fixar dependências e manter credenciais e dados de entrada fora de alterações acidentais.

**Technical actions:**

1. Criar `pyproject.toml` para Python >=3.12 com uv, pacote em `src/residencial_aurora/` e dependências FastAPI, Uvicorn, Google ADK, SDK Gemini e carregamento de ambiente; fixar Google ADK em uma versão exata da série 2 >=2.2.0 e gerar/versionar `uv.lock` (per `residencial-aurora-assistant/TD-04`, `residencial-aurora-assistant/TD-05`, `residencial-aurora-assistant/TD-06`).
2. Criar `.env.example` apenas com nomes das variáveis exigidas, incluindo `GOOGLE_API_KEY`, sem valores; manter `.env` no `.gitignore` e nunca adicionar credenciais ao repositório.
3. Registrar os cinco arquivos em `dados/` como fontes iniciais imutáveis; toda persistência operacional deve ir para o armazenamento escolhido, não sobrescrever os arquivos fonte.
4. Definir configuração única para o identificador `gemini-3.1-flash-lite` em agente principal e especialistas, permitindo a chave por ambiente e documentando que quota deve ser conferida no Google AI Studio (per `residencial-aurora-assistant/TD-06`).

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| Instalação e configuração local | Manual: AC-01, AC-03, AC-04 | Clone limpo; `uv sync`; inspeção do lockfile, `.env.example`, `.gitignore` e hashes dos cinco arquivos de `dados/` |

**Dependencies:** none

**Acceptance criteria:**

- `uv sync` conclui sem erro em clone limpo com Python >=3.12.
- `uv.lock` fixa uma versão exata Google ADK 2.x >=2.2.0; dependências do app estão no manifesto.
- `.env.example` lista variáveis necessárias sem valores; `.env` e chaves não aparecem no Git.
- Os cinco arquivos de `dados/` permanecem byte a byte iguais ao repositório base.

---

---

### SI-2 — Persistir estado e restaurar a base inicial

**Description:** Criar o armazenamento SQLite durável para sessões, eventos, reservas, visitantes e pendências, incluindo inicialização/restauração repetível a partir dos arquivos imutáveis.

**Technical actions:**

1. Criar schema e inicialização SQLite em `src/residencial_aurora/storage/`; importar apartamentos/áreas como dados iniciais consultáveis sem alterar os arquivos `dados/` (per `residencial-aurora-assistant/TD-02`).
2. Persistir reservas com histórico de cancelamento e código globalmente único; criar índice único parcial em `(area, data)` apenas para linhas ativas. Aplicar a unicidade na instrução de gravação dentro de transação SQLite, não por checagem prévia (per `residencial-aurora-assistant/TD-02`).
3. Persistir `Session(session_id, apartamento, adk_session_id)`, eventos completos em ordem estável e `PendingConfirmation(id, session_id, action, details_json, status, created_at)` com índice de busca por sessão/estado (per `residencial-aurora-assistant/TD-01`, `residencial-aurora-assistant/TD-02`).
4. Implementar comando idempotente de restauração de reservas e visitantes usando os arquivos iniciais; manter política explícita sobre sessões separada da restauração de dados do condomínio.

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| Persistência e restauração | Manual: AC-02, AC-03, AC-21, AC-22, AC-23, AC-28 | Executar comando de restauração e conferir reservas/visitantes iniciais; reiniciar API e consultar estado; verificar histórico de códigos e índice de exclusividade |

**Dependencies:** SI-1 — manifesto e pacote Python devem existir antes de inicializar armazenamento.

**Acceptance criteria:**

- Comando de restauração repõe reservas e visitantes iniciais sem modificar os arquivos de origem e pode ser repetido.
- Sessões, eventos, reservas, visitantes, estados de confirmação e códigos continuam persistidos após processo da API reiniciar.
- Cancelar reserva preserva seu código; nenhum código novo reutiliza código ativo, cancelado ou inicial.
- Duas gravações concorrentes não conseguem manter duas reservas ativas na mesma área/data; a constraint do SQLite rejeita a segunda no momento da gravação.

---

### SI-3 — Implementar regras de reservas e tools de domínio

**Description:** Expor operações de reserva como tools determinísticas que sempre usam o apartamento da sessão e delegam a exclusividade ao SQLite.

**Technical actions:**

1. Criar repositório/serviço de reservas que leia áreas e reservas iniciais e persista alterações em SQLite; devolver códigos de reserva gerados no servidor e nunca apagar códigos cancelados (per `residencial-aurora-assistant/TD-02`).
2. Criar tools para listar reservas do apartamento da sessão, consultar disponibilidade por área/data e solicitar reserva; disponibilidade devolve somente livre/ocupada, sem apartamento ou código do titular; áreas tarifadas apenas criam pendência de confirmação e nunca gravam a reserva diretamente.
3. Criar tool de cancelamento que recebe o contexto confiável de sessão e os critérios de área/data, restringe o `UPDATE` à reserva ativa do apartamento vinculado e não exige confirmação.
4. Converter violação esperada do índice único ativo `(area, data)` em resultado normal de indisponibilidade/conflito de negócio, mantendo transação e sem expor detalhes de outra reserva (per `residencial-aurora-assistant/TD-02`).

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| Tools e regras de reserva | Manual: AC-07, AC-09, AC-10, AC-12, AC-18, AC-23, AC-28 | Fluxos 4–6, 10 e 14 do avaliador; verificar diretamente estado e respostas/eventos |

**Dependencies:** SI-2 — tabelas, repositórios SQLite e constraint ativa são pré-requisito das tools.

**Acceptance criteria:**

- Tools de leitura/gravação nunca usam apartamento fornecido pelo modelo como identidade; listagem e cancelamento atuam apenas no apartamento da sessão.
- Cancelar reserva própria remove-a do conjunto ativo sem confirmação; tentar cancelar reserva alheia deixa seu estado intacto e não revela código.
- Reservar área com taxa zero grava sem confirmação; solicitar área tarifada cria pendência detalhada sem gravar antes da aprovação.
- Consulta de ocupação divulga somente livre/ocupada; tentativa sobre data ocupada não revela titular, código ou apartamento.
- Conflito concorrente de reserva retorna resultado normal de negócio e o SQLite conserva no máximo uma reserva ativa para área/data.
- Código gerado permanece globalmente único mesmo após cancelamento.

---

### SI-4 — Implementar autorização segura de visitantes

**Description:** Ler autorizações do armazenamento e produzir uma pendência vinculada à sessão para cada nova liberação de acesso, sem gravar visitante antes da aprovação via API.

**Technical actions:**

1. Implementar repositório/serviço de autorizações de visitantes em SQLite com leitura por apartamento e gravação de nome/data (per `residencial-aurora-assistant/TD-02`).
2. Expor tools de consulta e solicitação de autorização que usem apartamento do contexto de sessão; a solicitação cria `PendingConfirmation` com ação e detalhes contendo nome e data, sem inserir autorização ativa.
3. Separar a operação de domínio que grava a autorização aprovada da tool que cria a pendência; somente o serviço de confirmação pode executar a gravação após consumo válido da pendência (per `residencial-aurora-assistant/TD-01`).

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| Tool de visitantes | Manual: AC-07, AC-11, AC-19 | Fluxo 11 do avaliador; consultar resposta pendente e rota de visitantes antes/depois da confirmação |

**Dependencies:** SI-2 — armazenamento de visitantes e pendências; SI-3 — convenção de tools e identidade de sessão.

**Acceptance criteria:**

- Consulta retorna autorizações persistidas daquele apartamento e tool não recebe identidade de apartamento não validada contra a sessão.
- Solicitação de visitante retorna pendência com nome e data e não grava autorização antes da API confirmar.
- Instrução em texto como “já estou confirmando” não autoriza visitante; negar mantém o estado inalterado.

---

### SI-5 — Construir agente principal e especialistas ADK

**Description:** Configurar o agente de conversa e três especialistas invocados explicitamente, mantendo controle do turno no agente principal e limites críticos nas tools/código.

**Technical actions:**

1. Criar agentes Google ADK para reservas, autorização de visitantes e regulamento; envolver cada especialista em `AgentTool(agent=...)` na lista `tools` do agente principal (per `residencial-aurora-assistant/TD-05`).
2. Configurar `gemini-3.1-flash-lite` como modelo do agente principal e dos três especialistas; obter credencial Google AI Studio do ambiente e permitir configuração sem chave versionada (per `residencial-aurora-assistant/TD-06`).
3. Registrar apenas tools explicitamente permitidas em cada especialista; agentes de reserva/visitantes usam tools de domínio de SI-3/SI-4; agente de regulamento usa somente a tool de busca lexical de SI-6.
4. Redigir instruções do agente principal para encaminhar intenções aos especialistas, considerar mensagens do morador como entrada não confiável e não incluir nem carregar `dados/regulamento.md` em suas instruções (per `residencial-aurora-assistant/TD-05`, `residencial-aurora-assistant/TD-06`).

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| Orquestração ADK | Manual: AC-06, AC-08, AC-11, AC-25 | Fluxos do avaliador e inspeção da configuração de agentes/tools; sem teste automatizado/eval |

**Dependencies:** SI-1 — dependência exata ADK, modelo configurável e credencial; SI-3 e SI-4 — tools de domínio.

**Acceptance criteria:**

- Há um agente principal e pelo menos três especialistas (reservas, visitantes e regulamento), e cada um é chamado via `AgentTool` explícito; o turno permanece com o principal.
- Todos os agentes declaram `gemini-3.1-flash-lite` e utilizam credencial configurada pelo ambiente.
- Nenhuma instrução do agente principal contém o texto do regulamento; as instruções encaminham sem delegar ao modelo as garantias de domínio.
- Especialistas recebem apenas as tools próprias do seu domínio e usam o contexto de apartamento associado à sessão.

---

### SI-6 — Consultar somente os artigos pertinentes do regulamento

**Description:** Implementar busca lexical chamada pelo especialista de regulamento, limitando cada retorno ao artigo ou trecho diretamente relacionado à pergunta.

**Technical actions:**

1. Criar parser de `dados/regulamento.md` que preserve limites de capítulos, artigos e títulos em memória de processo, sem copiar o documento para instruções ou estado permanente de sessão (per `residencial-aurora-assistant/TD-03`).
2. Implementar tool que normaliza termos da pergunta, pontua títulos/conteúdo lexicalmente e retorna apenas a seção/artigo mais pertinente ou poucos trechos curtos relacionados; não devolver o documento integral nem capítulos de assuntos não relacionados.
3. Expor a tool somente ao especialista de regulamento de SI-5 e registrar no evento apenas a consulta e o trecho recuperado que fundamenta a resposta.

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| Tool de recuperação | Manual: AC-24, AC-25, AC-26 | Fluxo 12 do avaliador; pergunta sobre fechamento da piscina aos domingos e inspeção dos eventos gravados |

**Dependencies:** SI-1 — pacote e fonte imutável; SI-5 — especialista que chama a tool.

**Acceptance criteria:**

- Perguntar o horário de fechamento da piscina aos domingos produz resposta baseada no trecho correspondente de `dados/regulamento.md`.
- Instruções do agente principal e histórico persistido não recebem o regulamento completo.
- Eventos incluem chamada/resultado da tool com trecho pertinente e não incluem conteúdo de capítulos sobre outros assuntos.

---

### SI-7 — Expor criação de sessão e conversa pela API

**Description:** Implementar endpoints JSON de sessão e mensagem com Runner ADK persistente, resposta no contrato e fronteira de identidade entre conversa e domínio.

**Technical actions:**

1. Criar aplicação FastAPI em `src/residencial_aurora/api.py`, com servidor Uvicorn e rotas/documentação de schemas Pydantic (per `residencial-aurora-assistant/TD-04`).
2. Implementar `POST /sessoes` com body `apartamento`, criar `session_id`, salvar o apartamento uma única vez no estado da sessão e retornar `201`; compor dependências de armazenamento e SessionService persistente (per `residencial-aurora-assistant/TD-01`, `residencial-aurora-assistant/TD-04`).
3. Implementar `POST /sessoes/{session_id}/mensagens` com `texto`: recuperar sessão persistida, executar Runner com agente principal, usar apartamento obtido do armazenamento de sessão como contexto confiável para tools e retornar `200` com `resposta` e todas as `confirmacoes_pendentes` atuais.
4. Converter cada evento gerado pelo Runner em registro persistido em ordem da sessão. Como o Runner pode encapsular eventos internos de um `AgentTool`, cada adapter de tool registra explicitamente a chamada e seu resultado permitido; eventos não despejam fontes de dados ou capítulos alheios.
5. Garantir `404` para session_id inexistente e `422` de validação para corpo JSON inválido, sem executar Runner quando sessão não existe.

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| Rotas de sessão e conversa | Manual: AC-06, AC-08, AC-11, AC-13, AC-18, AC-20, AC-29 | Fluxos 2–7, 11–12; verificar status, payload e isolamento em eventos |

**Dependencies:** SI-1 — FastAPI/Uvicorn/ADK; SI-2 — sessões, eventos e estado persistidos; SI-3 e SI-4 — tools de domínio; SI-5 e SI-6 — agentes e tool de regulamento.

**Acceptance criteria:**

- `POST /sessoes` com JSON `{"apartamento":"101"}` retorna `201` com `session_id`.
- `POST /sessoes/{session_id}/mensagens` retorna `200`, `resposta` string e lista `confirmacoes_pendentes`; espera de confirmação pode retornar resposta vazia.
- O apartamento salvo na criação é fonte única de identidade das tools; texto que declara outro apartamento não altera identidade nem revela dados alheios.
- Chamada com sessão inexistente em rota de sessão retorna `404` sem executar agente; chamadas e respostas usam JSON.
- `confirmacoes_pendentes` lista todas as pendências atuais daquela sessão e fica vazia quando não há nenhuma.

---

### SI-8 — Consumir confirmações duráveis uma única vez

**Description:** Implementar a rota que aprova ou nega uma pendência gravada para a sessão e só executa cobranças/liberação de acesso após resposta explícita pela API.

**Technical actions:**

1. Implementar `POST /sessoes/{session_id}/confirmacoes` com `id` e boolean `confirmado`; validar sessão antes de localizar a pendência e retornar `404` se inexistente.
2. Em transação SQLite, atualizar somente pendência `pending` cujo `id` e `session_id` correspondem; ID ausente, de outra sessão ou já respondido retorna `409 CONFIRMATION_NOT_PENDING` sem operação de domínio (per `residencial-aurora-assistant/TD-01`).
3. Se negada, marcar pendência `denied` e não alterar reservas/visitantes; se aprovada, consumir pendência e executar uma única vez a operação aprovada usando identidade/detalhes persistidos, nunca valores redefinidos pelo modelo (per `residencial-aurora-assistant/TD-01`).
4. Para corrida na constraint de reserva ativa, tratar violação única como conflito de negócio; finalizar a pendência aprovada sem retornar erro de servidor e manter resultado normal `200` para ambas as aprovações (per `residencial-aurora-assistant/TD-02`).
5. Registrar decisão e resultado da confirmação no histórico da sessão e devolver o mesmo formato de `POST /mensagens`, com todas as pendências restantes.

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| Rota de confirmação | Manual: AC-13–AC-17, AC-19–AC-20, AC-27–AC-28 | Fluxos 7–9, 11 e 14; testar negação, aprovação, reenvio e aprovações concorrentes pelo endpoint |

**Dependencies:** SI-2 — armazenamento transacional de pendências; SI-3 e SI-4 — operações de domínio executadas após aprovação; SI-7 — contrato da API e histórico de sessão.

**Acceptance criteria:**

- Reserva tarifada e autorização de visitante retornam pendência contendo os detalhes específicos e não gravam estado antes da rota de confirmação.
- `confirmado: false` deixa domínio intacto; `true` executa a ação aprovada uma única vez.
- ID não pendente, de outra sessão ou já respondido retorna `409` e não altera o domínio; reenvio aprovado continua `409`.
- Mensagem textual alegando confirmação não consome pendência; confirmação válida retorna `200` no mesmo formato JSON de mensagem.
- Duas aprovações para a mesma área/data retornam ambas `200`; exatamente uma reserva fica ativa e a outra resposta comunica conflito normal.
- Aprovação de visitante persiste nome/data somente após resposta afirmativa da API.

---

### SI-9 — Consultar eventos persistidos da sessão

**Description:** Expor leitura direta e ordenada do histórico completo da sessão para auditoria e recuperação após reinício da API.

**Technical actions:**

1. Implementar `GET /sessoes/{session_id}/eventos` sobre o armazenamento de eventos; verificar existência da sessão antes de consultar a sequência.
2. Serializar cada evento persistido em ordem crescente de sequência, retornando conteúdo completo sem reconstruir histórico pelo modelo.
3. Retornar `404` para sessão inexistente e `200` com array de eventos para sessão existente, inclusive array vazio quando ainda não há mensagens.

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| Endpoint de eventos | Manual: AC-08, AC-09, AC-12, AC-21, AC-26 | Fluxos 3–4, 10, 12–13; comparar eventos antes/depois de reiniciar a API |

**Dependencies:** SI-2 — armazenamento durável e ordenado de eventos; SI-7 e SI-8 — execução de mensagens e confirmações que geram eventos.

**Acceptance criteria:**

- `GET /sessoes/{session_id}/eventos` retorna `200` com todos os eventos e seu conteúdo completo em ordem de gravação.
- Para sessão inexistente retorna `404`.
- Depois de parar/subir a API sem restaurar os dados, a sessão retorna os mesmos eventos previamente gravados e continua recebendo eventos novos.
- Eventos não contêm dados identificáveis de outros apartamentos nem capítulos não relacionados do regulamento.

---

### SI-10 — Expor rotas de verificação de domínio

**Description:** Disponibilizar consultas diretas às reservas e visitantes por apartamento para inspeção do estado persistido sem qualquer chamada ao modelo.

**Technical actions:**

1. Implementar `GET /apartamentos/{apartamento}/reservas`, consultando diretamente o repositório SQLite e serializando reservas ativas com `codigo`, `area` e `data` no formato `AAAA-MM-DD`.
2. Implementar `GET /apartamentos/{apartamento}/visitantes`, consultando diretamente o armazenamento e serializando `nome` e `data` no formato `AAAA-MM-DD`.
3. Garantir que rotas de verificação não inicializam Runner/agentes; refletem aprovações, negações, cancelamentos e restaurações persistidos.

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| Rotas de verificação | Manual: AC-02, AC-07, AC-10, AC-12–AC-19, AC-22–AC-23, AC-27–AC-29 | Fluxos do avaliador 1, 5–14; comparar JSON com estado observado após cada operação |

**Dependencies:** SI-2 — armazenamento; SI-3 e SI-4 — operações de domínio; SI-8 — consumo das confirmações.

**Acceptance criteria:**

- Rotas retornam `200` e leem dados diretamente do domínio persistido sem invocar modelo.
- Reservas retornam `codigo`, `area`, `data`; visitantes retornam `nome`, `data`; todas as datas serializadas são `AAAA-MM-DD`.
- Estado refletido inclui a reserva sem taxa, reservas tarifadas aprovadas, cancelamento próprio e autorização aprovada; estado inicial pode ser restaurado.
- Resultados das rotas permitem verificar exclusividade concorrente e códigos não reutilizados.

---

### SI-11 — Documentar arquitetura, garantias e operação

**Description:** Substituir o README-enunciado por documentação executável e rastreável da arquitetura, das garantias implementadas e do fluxo de instalação/restauração/subida.

**Technical actions:**

1. Reescrever `README.md` na raiz com seções exatas `Arquitetura`, `Garantias` e `Como rodar`; descrever agente principal, três especialistas, responsabilidades, acionamento por `AgentTool` e razão da escolha (per `residencial-aurora-assistant/TD-05`).
2. Em `Garantias`, documentar cada uma das cinco garantias e citar arquivo e trechos reais de código que a implementam; explicar por que a regra é aplicada por API, armazenamento ou tool e não depende da decisão/instrução do modelo.
3. Em `Como rodar`, declarar Python >=3.12, uv e chave Google AI Studio via `.env`; instruir cópia de `.env.example`, `uv sync`, restauração e subida em `http://localhost:8000`, com comandos existentes e conferência dos dados 101/302.
4. Incluir resumo de rotas/contrato, política de modelo/quota, imutabilidade dos arquivos de `dados/` e escopo de verificação manual; fornecer a URL completa do fork público na branch `main` como entrega final.

**Tests:**

| Artifact | Layer | Test file |
|----------|-------|-----------|
| README e comandos | Manual: AC-01–AC-07, AC-24–AC-29 | Seguir instruções desde clone limpo; conferir comandos e cada referência de arquivo/trecho contra o repositório |

**Dependencies:** SI-1 a SI-10 — documentar somente artefatos, comandos e garantias realmente implementados.

**Acceptance criteria:**

- README na raiz substitui o texto do desafio e contém as seções `Arquitetura`, `Garantias` e `Como rodar`.
- Cada garantia documentada cita caminhos e trechos que existem e descreve mecanismo de proteção no código.
- Comandos documentados de restauração e subida funcionam em clone limpo e deixam API acessível em `http://localhost:8000`.
- Fork público entregue com URL completa e implementação consolidada na branch `main`.

---

## Technical Specifications

### Data Model

#### Apartment

| Field | Type | Constraints |
|-------|------|-------------|
| numero | string | Identificador conforme `dados/apartamentos.json`; leitura da fonte inicial; nunca alterado pelo agente |
| morador | string | Nome conforme arquivo inicial; apenas leitura |

**Indexes:** carga inicial preserva os cinco arquivos de `dados/` byte a byte; atualizações não são gravadas nesses arquivos.

#### CommonArea

| Field | Type | Constraints |
|-------|------|-------------|
| id | string | Chave identificadora conforme `dados/areas.json` |
| nome | string | Nome conforme arquivo inicial |
| taxa | decimal | Valor em reais; `0` não cobra; valor maior que zero exige confirmação |

**Indexes:** arquivo inicial somente leitura.

#### Reservation

| Field | Type | Constraints |
|-------|------|-------------|
| codigo | string | PK/unique, gerado pelo sistema e nunca reutilizado, inclusive após cancelamento |
| apartamento | string | Obrigatório; deve vir do apartamento associado à sessão |
| area | string | ID de `CommonArea`; FK lógica para os dados iniciais |
| data | date | Obrigatória, wire format `AAAA-MM-DD` |
| status | string | `active` ou `cancelled`; cancelamento conserva o registro/código |

**Indexes:** unique parcial em `(area, data)` apenas para `status = 'active'`; unique global em `codigo`. Um ledger `reservation_code_registry` conserva os códigos gerados e os códigos iniciais mesmo quando o comando de restauração repõe as linhas das reservas. A constraint de unicidade ativa é aplicada no SQLite durante gravação, não em consulta prévia. (per `residencial-aurora-assistant/TD-02`)

#### VisitorAuthorization

| Field | Type | Constraints |
|-------|------|-------------|
| id | string | PK, gerada pelo sistema |
| apartamento | string | Obrigatório; vem da sessão |
| nome | string | Nome informado pelo morador |
| data | date | Data da visita em `AAAA-MM-DD` |

#### Session

| Field | Type | Constraints |
|-------|------|-------------|
| session_id | string | PK, gerada pela API |
| apartamento | string | Imutável após criação; contexto de domínio para todas as tools |
| adk_session_id | string | Identificador associado à sessão persistida do ADK |

#### SessionEvent

| Field | Type | Constraints |
|-------|------|-------------|
| sequence | integer | PK por sessão; crescente e estável na ordem de gravação |
| session_id | string | FK para Session |
| event_json | JSON | Conteúdo completo do evento ADK/tool; sem trechos de capítulos do regulamento não pertinentes |
| created_at | timestamp | Persistido para recuperação após reinício |

**Relations:** Session tem muitos SessionEvent; apartamento e contexto da sessão são obtidos no servidor antes de executar tools. (per `residencial-aurora-assistant/TD-01`, `residencial-aurora-assistant/TD-02`)

#### PendingConfirmation

| Field | Type | Constraints |
|-------|------|-------------|
| id | string | PK, imprevisível e único |
| session_id | string | FK para Session; confirmação só pode ser consumida nessa sessão |
| action | string | Operação de domínio pendente |
| details_json | JSON | Detalhes que a API devolve (`area`/`data` ou `nome`/`data`) |
| status | string | `pending`, `approved` ou `denied`; transição de `pending` ocorre uma única vez |
| created_at | timestamp | Persistido para sobreviver a reinício |

**Indexes:** índice em `(session_id, status)` para listar pendências atuais. A transação de confirmação consome a pendência e aplica, se aprovada, a operação de domínio de forma atômica. (per `residencial-aurora-assistant/TD-01`)

### API Contracts

#### POST /sessoes (SI-7)

**Request headers:**
- Content-Type: application/json

**Request body:**
- `apartamento`: string, required — apartment number from `dados/apartamentos.json`

**Response 201:**
- `session_id`: string

**Error responses:**
- `422`: invalid JSON body or missing/invalid field (framework validation response)

---

#### POST /sessoes/{session_id}/mensagens (SI-7)

**Request headers:**
- Content-Type: application/json

**Request body:**
- `texto`: string, required — resident message

**Response 200:**
- `resposta`: string; may be empty while execution awaits confirmation
- `confirmacoes_pendentes`: array of every pending confirmation for this session at response time; empty when none
  - `id`: string
  - `acao`: string
  - `detalhes`: object with action-specific details; at minimum area/date for paid reservations and name/date for visitor authorization

**Error responses:**
- `404`: session does not exist
- `422`: invalid JSON body or missing/invalid field

---

#### POST /sessoes/{session_id}/confirmacoes (SI-8)

**Request headers:**
- Content-Type: application/json

**Request body:**
- `id`: string, required — pending confirmation ID
- `confirmado`: boolean, required

**Response 200:** same JSON shape as `POST /sessoes/{session_id}/mensagens`, including the current pending confirmations

**Error responses:**
- `404`: session does not exist
- `409`: no pending confirmation with this ID in this session, including already approved or denied IDs; no domain action is executed
- `422`: invalid JSON body or missing/invalid field

---

#### GET /sessoes/{session_id}/eventos (SI-9)

**Response 200:** ordered array containing every complete persisted session event

**Error responses:**
- `404`: session does not exist

---

#### GET /apartamentos/{apartamento}/reservas (SI-10)

**Response 200:** array of reservations for the requested apartment, each with `codigo`, `area` (area ID), and `data` (`AAAA-MM-DD`); cancelled reservations are excluded from active reservation results

**Error responses:**
- No status is specified for unknown apartment by the challenge; do not make this a correctness dependency

---

#### GET /apartamentos/{apartamento}/visitantes (SI-10)

**Response 200:** array of visitor authorizations for the requested apartment, each with `nome` and `data` (`AAAA-MM-DD`)

**Error responses:**
- No status is specified for unknown apartment by the challenge; do not make this a correctness dependency

---

#### Validation Rules

- All request and response payloads use JSON.
- Dates in verification-route payloads use `AAAA-MM-DD`.
- Any route containing `{session_id}` returns `404` for an unknown session.
- `confirmacoes_pendentes` includes all still-pending confirmations for that session; a valid confirmation response uses the same response shape as a message response.
- Verification routes read persisted domain data directly and never invoke the model.
- Session apartment is server-owned state; model-selected apartment values are not accepted as domain authority.

---

### Authorization Matrix

| Operation | Session owner context | Other apartment data | Verification route |
|-----------|-----------------------|----------------------|--------------------|
| Create session | Apartment is fixed from the creation request and server session | Not applicable | Not applicable |
| Read/write reservations or visitors through chat tools | Use only the apartment bound to the session | Denied; do not disclose identifying reservation/visitor data | Not applicable |
| Check area availability | Session may consult area/date occupancy | Reveal only free/occupied, never the reserving apartment | Not applicable |
| Cancel reservation | Only active reservation owned by the session apartment; no confirmation | Denied without leaking its code | Not applicable |
| Approve visitor or paid reservation | Pending action bound to the same session; execute only via confirmation API | Never trust conversational claim of identity or approval | Not applicable |
| Read verification endpoints | Not applicable | Endpoint reads the requested apartment directly for evaluator verification | Direct persisted-data read; no model |

No authentication system or unknown-apartment response policy is added; those behaviors are outside the challenge's scope. (per `residencial-aurora-assistant/TD-01`, `residencial-aurora-assistant/TD-02`)

---

### Error Catalog

| errorCode / status | HTTP | Trigger and required behavior |
|--------------------|------|------------------------------|
| SESSION_NOT_FOUND | 404 | Session ID does not exist on any route containing `{session_id}`; no model execution |
| CONFIRMATION_NOT_PENDING | 409 | Confirmation ID is absent from this session or was already answered; no domain action is executed |
| RESERVATION_CONFLICT | 200 domain result | A concurrent approval loses the active `(area, data)` unique constraint; return a normal assistant/business response, not a server error; preserve one active reservation maximum |
| REQUEST_VALIDATION_ERROR | 422 | Request JSON does not satisfy the declared body shape; framework validation response |

HTTP `409` is reserved for invalid/replayed confirmation IDs per the contract. A reservation race is reported as a normal `200` conversation result while database uniqueness arbitrates the write. (per `residencial-aurora-assistant/TD-01`, `residencial-aurora-assistant/TD-02`, `residencial-aurora-assistant/TD-04`)

---

## Dependency Map

SI-1 (root)
└── SI-2 — depends on SI-1 (package/runtime before persistence)
    └── SI-3 — depends on SI-2 (database before reservation tools)
        └── SI-4 — depends on SI-2 + SI-3 (visitor persistence and domain-tool conventions)
            └── SI-5 — depends on SI-1 + SI-3 + SI-4 (ADK agents and domain tools)
                └── SI-6 — depends on SI-5 (regulation retrieval wired to its specialist)
                    └── SI-7 — depends on SI-2 + SI-3 + SI-4 + SI-5 + SI-6 (session/message API)
                        └── SI-8 — depends on SI-2 + SI-3 + SI-4 + SI-7 (durable confirmation API)
                            ├── SI-9 — depends on SI-2 + SI-7 + SI-8 (event history)
                            └── SI-10 — depends on SI-2 + SI-3 + SI-4 + SI-8 (verification routes)
SI-11 — depends on SI-1 through SI-10 (README describes delivered behavior and real code locations)

---

## Deliverables

- [x] SI-1 — Preparar o projeto Python e proteger a configuração
- [x] SI-2 — Persistir estado e restaurar a base inicial
- [x] SI-3 — Implementar regras de reservas e tools de domínio
- [x] SI-4 — Implementar autorização segura de visitantes
- [x] SI-5 — Construir agente principal e especialistas ADK
- [x] SI-6 — Consultar somente os artigos pertinentes do regulamento
- [x] SI-7 — Expor criação de sessão e conversa pela API
- [x] SI-8 — Consumir confirmações duráveis uma única vez
- [x] SI-9 — Consultar eventos persistidos da sessão
- [x] SI-10 — Expor rotas de verificação de domínio
- [ ] SI-11 — Documentar arquitetura, garantias e operação

**Entrega pública:**

- [ ] Fork público do repositório base com todos os artefatos na branch `main`; fornecer URL completa `https://...`.
- [ ] README na raiz substitui o enunciado e aponta trechos reais para as cinco garantias.

**Operação local:**

- [ ] Em clone limpo, executar `cp .env.example .env`, preencher `GOOGLE_API_KEY` e rodar `uv sync`.
- [ ] Restaurar reservas/visitantes com `uv run python -m residencial_aurora.restore_data`.
- [ ] Subir a API com `uv run uvicorn residencial_aurora.api:app --app-dir src --host 127.0.0.1 --port 8000` e consultar `http://localhost:8000`.
- [ ] Seguir manualmente o fluxo do avaliador descrito em `context.md` (AC-01–AC-29); testes automatizados/evals estão fora de escopo.
