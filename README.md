# Assistente do Residencial Aurora

API de conversa para reservas de áreas comuns, autorizações de visitantes e consulta ao regulamento. O Google ADK conduz a conversa; as regras de identidade, confirmação e concorrência são aplicadas pela API e pelo SQLite.

## Arquitetura

O pacote executável está em `src/residencial_aurora/` e usa Python 3.12 ou superior.

- **Agente principal:** `root_agent`, em `src/residencial_aurora/agents.py`, acolhe a mensagem e escolhe o especialista. Os três especialistas são expostos explicitamente por `AgentTool(agent=...)`, então o principal mantém o controle da conversa.
- **Especialista de reservas:** consulta as próprias reservas, verifica ocupação, solicita novas reservas e cancela reservas próprias. Suas tools estão em `src/residencial_aurora/tools/reservations.py` e as regras determinísticas em `src/residencial_aurora/domain/reservations.py`.
- **Especialista de visitantes:** consulta autorizações do apartamento da sessão e abre uma pendência para uma nova autorização. Tools e regras estão em `src/residencial_aurora/tools/visitors.py` e `src/residencial_aurora/domain/visitors.py`.
- **Especialista de regulamento:** consulta `dados/regulamento.md` por busca lexical. `src/residencial_aurora/domain/regulation.py` separa o texto em capítulos e artigos e devolve apenas os trechos mais pertinentes; a tool está em `src/residencial_aurora/tools/regulation.py`.
- **API:** `src/residencial_aurora/api.py` expõe sessões, mensagens, confirmações, eventos e consultas diretas de verificação. FastAPI publica a documentação OpenAPI em `/docs`.
- **Persistência:** `src/residencial_aurora/storage/database.py` define tabelas e índices do domínio. `src/residencial_aurora/storage/sessions.py` persiste as sessões públicas, os eventos da API e as pendências. O `DatabaseSessionService` do ADK persiste também o estado e eventos do Runner no mesmo arquivo SQLite, em tabelas próprias do ADK.

O modelo configurado para o agente principal e os especialistas é `gemini-3.1-flash-lite`, centralizado em `src/residencial_aurora/config.py`. A chamada do Gemini exige uma chave do Google AI Studio. A disponibilidade do modelo e a quota dependem do projeto; confira os limites ativos no AI Studio.

## Garantias

### 1. Cobrança e liberação de acesso exigem confirmação explícita

`src/residencial_aurora/domain/reservations.py::create_paid_reservation` e `src/residencial_aurora/domain/visitors.py::request_visitor_authorization` gravam uma `pending_confirmation` com a ação e os detalhes, sem executar a operação. A resposta em linguagem natural do morador não altera esse estado.

`src/residencial_aurora/api.py::confirm_action` só aceita um `id` pendente da própria sessão. `src/residencial_aurora/domain/confirmations.py::consume_confirmation` valida a sessão e consome a pendência em uma transação SQLite. Na aprovação, a transição da pendência, a operação de domínio e o evento de auditoria são gravados juntos. Na negação, somente a pendência e o evento mudam. IDs ausentes, de outra sessão ou já respondidos retornam `409` sem executar a ação.

### 2. Cada sessão pertence a um apartamento

`POST /sessoes`, em `src/residencial_aurora/api.py::create_session`, valida o apartamento inicial e grava sua associação com identificadores da API e do ADK. Em cada mensagem, `_run_message` busca essa associação no SQLite e envia `trusted_apartment` e `api_session_id` ao estado do Runner. `src/residencial_aurora/tools/reservations.py::_trusted_session` é a origem de identidade das tools; elas não recebem um número de apartamento como argumento do modelo.

`list_reservations` e `cancel_reservation`, em `src/residencial_aurora/domain/reservations.py`, restringem os dados ao apartamento confiável. A consulta de disponibilidade retorna somente “livre” ou “ocupada”. O cancelamento exige correspondência de apartamento, área e data; se a reserva não for própria, retorna mensagem genérica sem expor o código.

### 3. O estado continua disponível depois de reiniciar a API

`src/residencial_aurora/storage/database.py::ensure_initial_data` carrega as fontes iniciais somente quando o armazenamento ainda não tem apartamentos, sem redefinir dados operacionais em reinicializações. `DatabaseSessionService` é configurado em `src/residencial_aurora/api.py::lifespan` com a mesma base SQLite. `src/residencial_aurora/storage/sessions.py::append_event` grava cada evento do Runner em sequência estável. O Runner externo encapsula eventos internos de `AgentTool`, então `src/residencial_aurora/tools/audit.py::record_tool_event` também registra cada tool especialista e seu resultado permitido. `list_events` lê o histórico persistido sem reconstruí-lo pelo modelo.

Reservas, cancelamentos, autorizações, sessões, eventos e pendências são dados SQLite. O comando de restauração é explícito: ele repõe reservas e visitantes iniciais e preserva sessões, eventos e pendências. Os cinco arquivos em `dados/` são fontes de leitura e não são sobrescritos.

### 4. O regulamento é consultado sob demanda

`src/residencial_aurora/domain/regulation.py::load_articles` mantém artigos delimitados em cache de processo. `search_regulation` normaliza e pontua termos da pergunta e devolve no máximo dois artigos curtos pertinentes. A tool `consultar_regulamento`, em `src/residencial_aurora/tools/regulation.py`, é oferecida somente ao especialista de regulamento. O agente principal não recebe o arquivo; eventos de chamada guardam a consulta e o resultado limitado da tool.

### 5. Uma área e data só podem ter uma reserva ativa

`src/residencial_aurora/storage/database.py`, no índice parcial `uq_reservation_active_area_date`, aplica a unicidade de `(area, data)` diretamente no SQLite para linhas `active`. `src/residencial_aurora/domain/reservations.py::create_paid_reservation` converte conflito de gravação em resultado de ocupação. `src/residencial_aurora/domain/confirmations.py::consume_confirmation` trata o conflito de aprovações concorrentes como resultado normal, finaliza a pendência aprovada e mantém apenas uma reserva ativa.

O código de cada reserva é gerado no servidor, tem unicidade global em `reservations.codigo` e também fica no ledger `reservation_code_registry`. O ledger mantém códigos históricos quando uma restauração repõe as linhas iniciais, e o cancelamento conserva a reserva e seu código.

## Como rodar

Requisitos: Python 3.12 ou superior, [uv](https://docs.astral.sh/uv/) e uma chave do Google AI Studio.

1. Copie `.env.example` para `.env` e preencha `GOOGLE_API_KEY`. `DATABASE_PATH` é opcional; por padrão, o SQLite fica em `data/residencial_aurora.sqlite3`.
2. Instale as dependências fixadas pelo lockfile:

   ```powershell
   uv sync
   ```

3. Restaure apartamentos, áreas, reservas e visitantes iniciais quando precisar reiniciar o estado do domínio:

   ```powershell
   uv run python -m residencial_aurora.restore_data
   ```

   O comando não altera arquivos em `dados/` nem apaga sessões/eventos. Executá-lo reinicia reservas e autorizações de visitantes para os dados iniciais.

4. Suba a API:

   ```powershell
   uv run uvicorn residencial_aurora.api:app --app-dir src --host 127.0.0.1 --port 8000
   ```

   A API fica em `http://localhost:8000` e a documentação interativa em `http://localhost:8000/docs`.

Para rodar em container Docker:

```powershell
docker build -t residencial-aurora-assistant .
docker run --rm -p 8000:8000 --env-file .env -v aurora-data:/app/data residencial-aurora-assistant
```

Para restaurar o volume do Docker explicitamente, pare a API e rode:

```powershell
docker run --rm --env-file .env -v aurora-data:/app/data residencial-aurora-assistant python -m residencial_aurora.restore_data
```

O lockfile fixa Google ADK em `2.6.1` e também trava as versões transitivas. `.env`, `.venv`, cache de `uv` e o banco local são ignorados pelo Git.

## Rotas da API

Todos os corpos e respostas usam JSON.

| Método e rota | Uso | Resposta principal |
|---|---|---|
| `POST /sessoes` | Cria sessão com `{"apartamento":"101"}` | `201`, `{"session_id":"..."}` |
| `POST /sessoes/{session_id}/mensagens` | Envia `{"texto":"..."}` ao agente | `200`, `resposta` e `confirmacoes_pendentes` |
| `POST /sessoes/{session_id}/confirmacoes` | Envia `{"id":"...","confirmado":true}` | `200`, mesma forma da mensagem; pendência inválida/respondida dá `409` |
| `GET /sessoes/{session_id}/eventos` | Lê eventos persistidos em ordem | `200`, lista de eventos; sessão inexistente dá `404` |
| `GET /apartamentos/{apartamento}/reservas` | Inspeciona reservas ativas | `200`, códigos, áreas e datas |
| `GET /apartamentos/{apartamento}/visitantes` | Inspeciona autorizações | `200`, nomes e datas |

## Conferência manual

Depois de restaurar os dados, confirme que `GET /apartamentos/101/reservas` inclui a reserva inicial `RSV-1377` da quadra e que `GET /apartamentos/302/visitantes` inclui Marina Duarte. A documentação do curso lista os demais fluxos de conversa e critérios do avaliador. Os checks de domínio e API dos SIs 3 a 10 foram executados em containers Docker descartáveis; setup e restauração dos dados iniciais também foram conferidos localmente. Uma conversa real com Gemini requer uma chave e quota válidas no projeto Google AI Studio.

## Fork e branch de implementação

Fork público: [nelsonota/mba-ia-desafio-criacao-agente](https://github.com/nelsonota/mba-ia-desafio-criacao-agente). A implementação deste trabalho está na branch local `feature/residencial-aurora-assistant`. Conforme a orientação de revisão, ela ainda não foi commitada ou publicada; o link público para `main` só refletirá estas mudanças depois da revisão e integração feita pelo responsável pelo repositório.
