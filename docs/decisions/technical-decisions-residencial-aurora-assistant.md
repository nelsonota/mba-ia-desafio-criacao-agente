---
scope_type: ad-hoc
related_phases: []
status: decided
date: 2026-11-04
scope_description: "Implementar a entrega completa do desafio Full Cycle do assistente do Residencial Aurora: API JSON em Python 3.12+ com uv, Google ADK série 2 em versão exata >=2.2.0 e Gemini; contrato: POST /sessoes recebe apartamento e retorna 201/session_id; POST /sessoes/{session_id}/mensagens recebe texto e retorna 200/resposta/confirmacoes_pendentes; POST /sessoes/{session_id}/confirmacoes recebe id/confirmado e retorna o mesmo formato com 200 ou 409 para id inválido/repetido; GET /sessoes/{session_id}/eventos retorna todos os eventos em ordem com 200 ou 404 para sessão inexistente; GET /apartamentos/{apartamento}/reservas e /visitantes verificam dados diretamente; todas as rotas usam JSON e datas AAAA-MM-DD. Entregar agente principal e pelo menos dois especialistas, com tools para ler/gravar reservas e visitantes; apartamento da sessão vem do estado autenticado inicial, nunca de escolha não validada do modelo, e conversas não vazam dados de outros apartamentos; disponibilidade só revela livre/ocupada. Cobrar áreas tarifadas e autorizar visitantes somente após confirmação pela API: pendências incluem detalhes da ação, negar não altera estado, aprovar executa uma vez, reenvio ou id não pendente retorna 409; ações sem taxa e cancelamento da própria reserva não pedem confirmação. Persistir sessões, eventos e alterações de reservas/visitantes após reinício; comando de restauração retorna reservas e visitantes aos dados iniciais e a API sobe em localhost:8000; códigos de novas reservas não repetem códigos existentes ou cancelados. Consultar dados/regulamento.md sob demanda por tool, sem incluí-lo nas instruções do agente principal e sem gravar nos eventos capítulos não relacionados. Garantir no instante da gravação no máximo uma reserva ativa por área/data sob aprovações concorrentes, respondendo conflito como resultado normal. Os cinco arquivos de dados iniciais permanecem idênticos; uv sync funciona em clone limpo; .env não é versionado, .env.example lista variáveis sem valores; README na raiz contém Arquitetura, Garantias com arquivos/trechos reais e Como rodar com pré-requisitos e comandos de restauração/subida. Escopo exclui interface visual, autenticação, pagamento/estorno, regras de antecedência/data passada/horário/capacidade, testes/evals e deploy."
---

# Technical Decisions — Assistente do Residencial Aurora

_Subprojects in scope:_

- `./` — API Python, runtime ADK, persistência das sessões e dados do condomínio; este clone contém apenas os dados iniciais e o enunciado, sem subprojetos de backend separados.

_Escopo extraído da página do desafio “Regra é regra: o assistente virtual do Residencial Aurora”. O clone não contém `docs/project-plan.md`, decisões anteriores, manifesto Python ou código de aplicação; as restrições adotadas abaixo vêm do enunciado (Python ≥3.12, `uv`, Google ADK 2.x ≥2.2.0, Gemini, API em localhost:8000 e dados iniciais imutáveis)._

---

## TD-01: Retomada de ações que exigem confirmação

**Scope:** Backend

**Trigger:** A rota da API deve aprovar ou negar uma operação pendente, executar uma única vez somente após aprovação externa à conversa e continuar funcionando após reinício, apesar das particularidades de retomada do ADK.

**Context:** O ADK documenta confirmação como resposta de função associada ao ID da chamada e, quando configurado o recurso Resume, à invocação original. A documentação também lista `DatabaseSessionService` entre as limitações do recurso de confirmação. O desafio relata testes em que a retomada variou com topologia, bloqueios de transferência e serviço de sessão, incluindo sucesso com SQLite em algumas combinações. A decisão afeta arquitetura dos especialistas, eventos persistidos e a rota `POST /sessoes/{session_id}/confirmacoes`. Fontes: [ADK — Tool Confirmation](https://adk.dev/tools-custom/confirmation/), [ADK — Resume](https://adk.dev/runtime/resume/).

**Options:**

### Option A: Confirmação nativa ADK com retomada da invocação
- A tool solicita confirmação pelo mecanismo do ADK; a API guarda o ID da invocação e retorna a resposta de função correspondente para retomar o agente que pediu a confirmação.
- **Pros:** Mantém o fluxo de aprovação como parte da execução do agente e registra os eventos de tool no modelo nativo do ADK.
- **Cons:** A documentação atual lista `DatabaseSessionService` como não suportado pela confirmação; retomada errada ou incompatibilidade com sessão persistida pode falhar silenciosamente, e a topologia do agente passa a ser crítica.

### Option B: Pendência durável controlada pela API
- A tool cria uma ação pendente persistida e devolve seus detalhes à API. A rota de confirmação valida sessão, ID e estado pendente; em uma transação, nega ou consome a pendência e executa a operação de domínio aprovada. A API então registra/devolve o resultado ao histórico da sessão.
- **Pros:** A origem da aprovação é inequivocamente a rota; consumo único, reinício e execução do domínio podem ser garantidos por estado persistido e transação, sem depender da retomada de uma invocação suspensa.
- **Cons:** Parte do ciclo de vida da confirmação fica fora do runtime nativo do ADK e exige sincronizar o resultado da rota com o histórico de eventos da conversa.

**Recommendation:** Option B — o requisito central é uma aprovação externa durável e de uso único, enquanto a documentação atual alerta que o serviço de sessão de banco não é suportado pelo fluxo nativo; esta opção reduz o risco de retomada silenciosamente ineficaz.

**Decision:** B

---

## TD-02: Persistência e exclusividade de reservas

**Scope:** Backend

**Trigger:** O estado de reservas, visitantes, sessões e confirmações precisa sobreviver ao reinício, preservar códigos de reservas canceladas e impedir que duas aprovações simultâneas ocupem a mesma área e data.

**Context:** A checagem de disponibilidade antes da gravação não evita corrida. A restrição precisa ser aplicada no armazenamento durante a gravação, e uma colisão esperada deve virar resultado de negócio normal. SQLite fornece transações serializáveis e gravações serializadas; constraints únicas são verificadas no `INSERT`/`UPDATE`. Fontes: [SQLite — Isolation](https://sqlite.org/isolation.html), [SQLite — UNIQUE constraints](https://www.sqlite.org/lang_createtable.html#uniqueconst), [SQLite — Transactions](https://www.sqlite.org/transactional.html).

**Options:**

### Option A: SQLite local com constraint de unicidade
- Persistir estado do condomínio e pendências numa base SQLite; representar reservas canceladas sem apagar o código e impor unicidade apenas para reservas ativas por `(area, data)` no próprio banco.
- **Pros:** Sem serviço externo, simples de restaurar/documentar no desafio e a decisão atômica fica no armazenamento, não numa checagem sujeita a corrida.
- **Cons:** SQLite serializa escritores e pode retornar `SQLITE_BUSY`; é adequado ao avaliador local, mas oferece menos concorrência de escrita que um banco servidor.

### Option B: PostgreSQL com constraint de unicidade
- Persistir o estado num serviço PostgreSQL, com a exclusividade ativa aplicada por constraint/índice único e as operações de aprovação agrupadas em transações.
- **Pros:** Mais capacidade para escritores concorrentes e infraestrutura conhecida para evolução multi-instância.
- **Cons:** Acrescenta serviço e comando de inicialização obrigatórios ao README, mais dependências de ambiente e configuração do que o desafio local exige.

**Recommendation:** Option A — o fluxo do avaliador é uma API local e a regra exige correção sob duas aprovações concorrentes, não alta taxa sustentada; uma constraint única ativa no SQLite fornece a arbitragem no instante da gravação sem adicionar serviço externo.

**Decision:** A

**Revisions:**
- 2026-11-05 — Alterado o identificador configurado para `gemini-3.1-flash-lite` após o Gemini retornar `503 UNAVAILABLE` por alta demanda com `gemini-3.5-flash-lite` durante a validação real. Rationale: testar o modelo estável alternativo de baixo custo, mantendo um modelo Lite uniforme em todos os agentes. A documentação oficial confirma estabilidade e suporte a function calling: [Gemini 3.1 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite).

---

## TD-03: Recuperação do regulamento para respostas

**Scope:** Backend

**Trigger:** O agente deve responder dúvidas do regulamento sem receber o documento inteiro nas instruções e sem registrar nos eventos capítulos alheios à pergunta.

**Context:** `dados/regulamento.md` é um documento longo (cerca de 45 KB no clone). A consulta deve selecionar apenas o trecho pertinente antes de enviá-lo ao modelo; isso limita contexto/custo e reduz o material do regulamento que poderia entrar no histórico. A página do desafio requer explicitamente que o agente principal não receba o regulamento e que os eventos não contenham capítulos de outros assuntos.

**Options:**

### Option A: Busca lexical por capítulos/artigos
- Uma tool pesquisa títulos e termos no Markdown, identifica seções candidatas e devolve apenas o artigo ou pequeno trecho correspondente ao assunto perguntado.
- **Pros:** Nenhum serviço ou modelo de embedding adicional; conteúdo fornecido ao modelo e registrado no evento pode ser limitado diretamente ao trecho escolhido.
- **Cons:** Depende de títulos/termos e pode não recuperar bem paráfrases ou perguntas que cruzam assuntos.

### Option B: Índice de recuperação semântica local
- Dividir o regulamento em unidades por artigo/seção, indexar vetores localmente e retornar poucos trechos relevantes via tool, sem enviar o documento integral.
- **Pros:** Recupera melhor consultas em linguagem natural e sinônimos, mantendo a busca encapsulada na tool.
- **Cons:** Acrescenta dependência de embeddings, criação/atualização do índice e risco de recuperar trechos adjacentes ou não relacionados que acabem nos eventos.

**Recommendation:** Option A — o documento é um único Markdown e as regras exigem contenção estrita do contexto; busca por seções com saída limitada é suficiente para o escopo e torna simples inspecionar o que foi gravado nos eventos. Considere Option B somente se a cobertura de paráfrases se mostrar insuficiente.

**Decision:** A

---

## Decisions Summary

| ID | Scope | Decision | Recommendation | Choice |
|----|-------|----------|---------------|--------|
| TD-01 | Backend | Retomada de ações que exigem confirmação | Pendência durável controlada pela API | B |
| TD-02 | Backend | Persistência e exclusividade de reservas | SQLite local com constraint de unicidade | A |
| TD-03 | Backend | Recuperação do regulamento para respostas | Busca lexical por capítulos/artigos | A |
| TD-04 | Backend | Framework web da API | FastAPI + Uvicorn | A |
| TD-05 | Backend | Papéis e orquestração dos especialistas ADK | AgentTool explícito com três especialistas | A |
| TD-06 | Backend | Modelo Gemini dos agentes | Gemini 3.5 Flash-Lite para todos | A |

---

## TD-04: Framework web da API

**Scope:** Backend

**Trigger:** O desafio permite escolher o framework web, mas a API precisa seguir exatamente o contrato JSON, atender operações assíncronas do ADK e iniciar em `http://localhost:8000`.

**Context:** FastAPI usa type hints para validar/convertir corpos JSON e gerar OpenAPI; suas rotas aceitam `async def`, adequado para chamadas assíncronas. O curso usa FastAPI, embora permita outro framework. Fonte: [FastAPI — Async](https://fastapi.tiangolo.com/async/), [FastAPI — Request Body](https://fastapi.tiangolo.com/tutorial/body/).

**Options:**

### Option A: FastAPI + Uvicorn
- Declarar as rotas com modelos tipados e executar a aplicação ASGI com Uvicorn.
- **Pros:** Validação de JSON e documentação OpenAPI integradas; suporte direto a endpoints assíncronos; segue o exemplo do curso.
- **Cons:** Acrescenta FastAPI e Uvicorn como dependências e segue convenções específicas do framework.

### Option B: Flask + adaptador ASGI
- Implementar as rotas no Flask e expor a aplicação por um adaptador ASGI para conviver com operações assíncronas.
- **Pros:** API pequena com um framework conhecido e flexível.
- **Cons:** Validação e documentação do contrato precisam de escolhas adicionais; a integração async exige uma camada de adaptação.

**Recommendation:** Option A — o ADK e o armazenamento assíncrono se encaixam naturalmente em endpoints `async`, enquanto a validação tipada ajuda a cumprir o contrato fixo do avaliador.

**Decision:** A
**Libraries:** fastapi, uvicorn

---

## TD-05: Papéis e orquestração dos especialistas ADK

**Scope:** Backend

**Trigger:** O desafio exige agente principal e pelo menos dois especialistas, deixando como decisão o número de especialistas, suas responsabilidades e como o agente principal os aciona.

**Context:** O ADK permite invocação explícita com `AgentTool`, em que o especialista retorna o resultado como resposta de tool ao agente principal, ou transferência automática para `sub_agents`. O fluxo explícito mantém a coordenação no agente principal, o que combina com confirmações externas controladas pela API. Fonte: [ADK — Custom Agents / AgentTool](https://adk.dev/agents/custom-agents/), [ADK — Multi-agent patterns](https://adk.dev/agents/multi-agents/).

**Options:**

### Option A: AgentTool explícito com três especialistas
- O agente principal aciona especialistas de reservas, autorização de visitantes e consulta ao regulamento como tools; cada especialista usa tools de domínio permitidas.
- **Pros:** O agente principal mantém controle do turno e combina os resultados; responsabilidades acompanham os três domínios e ficam claras no README.
- **Cons:** Exige instruções e descrições de tools explícitas; chamadas de especialistas adicionam etapas ao fluxo.

### Option B: Transferência automática com dois especialistas
- Registrar especialistas de reservas e de serviços ao morador (visitantes e regulamento) em `sub_agents`; o ADK transfere o controle conforme a descrição das tarefas.
- **Pros:** Usa delegação hierárquica nativa e reduz a quantidade de tools expostas ao agente principal.
- **Cons:** A escolha de transferência depende do modelo e o controle passa ao especialista durante o turno; separar autorização de visitantes da consulta ao regulamento fica menos nítido.

**Recommendation:** Option A — mantém a coordenação em um ponto previsível e separa três domínios com permissões diferentes; as garantias continuam nas tools e na API, nunca nas instruções do agente.

**Decision:** A
**Libraries:** google-adk

---

## TD-06: Modelo Gemini dos agentes

**Scope:** Backend

**Trigger:** O desafio exige Gemini, deixa a escolha do modelo para cada agente e estima algumas dezenas de chamadas durante a avaliação; o modelo escolhido também precisa suportar function calling.

**Context:** A documentação do Google lista `gemini-3.5-flash-lite` como modelo estável, de baixo custo/latência para fluxos de alto volume, e confirma suporte a function calling. A disponibilidade pública não assegura a quota ativa do projeto no AI Studio, que ainda precisa ser conferida antes de executar o fluxo. Fontes: [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [Gemini model list](https://ai.google.dev/gemini-api/docs/models), [Function calling support](https://ai.google.dev/gemini-api/docs/function-calling).

**Options:**

### Option A: Gemini 3.5 Flash-Lite em todos os agentes
- Fixar `gemini-3.5-flash-lite` no agente principal e nos especialistas, verificando que o projeto tem quota suficiente.
- **Pros:** Um modelo estável e uniforme; a documentação o posiciona para tarefas de alto volume e confirma function calling.
- **Cons:** O agente principal também precisa rotear pedidos e aplicar instruções extensas; menor margem de raciocínio que os modelos Flash mais avançados.

### Option B: Gemini 3.8 Flash em todos os agentes
- Usar `gemini-3.8-flash`, modelo Flash estável atual, em todos os agentes.
- **Pros:** Mais capacidade para orquestração, raciocínio em várias etapas e uso de tools, mantendo configuração uniforme.
- **Cons:** Mais custo e consumo de quota nas chamadas dos especialistas.

### Option C: Gemini 3.8 Flash no principal e 3.5 Flash-Lite nos especialistas
- Usar o modelo Flash mais capaz para roteamento e modelos de menor custo para os especialistas de domínio.
- **Pros:** Reserva mais capacidade para coordenação e reduz custo nas tarefas focadas dos especialistas.
- **Cons:** Requer quota para dois modelos e pode produzir diferenças de resposta entre o principal e os especialistas.

**Recommendation:** Option A — usar o mesmo modelo estável de baixo custo em todos os agentes simplifica a configuração e a verificação de quota; confirme que o projeto no AI Studio permite as dezenas de chamadas esperadas.

**Decision:** A

---

## Fonte de escopo

- [Desafio Full Cycle — Regra é regra: o assistente virtual do Residencial Aurora](https://plataforma.fullcycle.com.br/courses/a091b0fe-a5c6-4287-a3d3-1ec61defcfd3/413/224/266/conteudos?projeto=70&fase=309) — critérios de aceite, contrato da API e fluxo de avaliação, lidos na página aberta no Chrome em 2026-11-04.
