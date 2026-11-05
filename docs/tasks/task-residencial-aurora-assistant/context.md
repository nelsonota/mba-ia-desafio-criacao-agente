---
kind: task
name: task-residencial-aurora-assistant
sources_mtime:
  docs/decisions/technical-decisions-residencial-aurora-assistant.md: "2026-11-05T00:00:31.7680666Z"
---

# task-residencial-aurora-assistant — Context

## Scope

Implementar a entrega completa do desafio Full Cycle do assistente do Residencial Aurora conforme os critérios verificáveis abaixo, transcritos e organizados da seção “Critérios de aceite” e do fluxo do avaliador na página do desafio. Os cinco arquivos de `dados/` são imutáveis. Requisitos expressamente fora de escopo estão listados ao final desta seção.

## Acceptance Criteria

Os itens AC-01 a AC-29 devem ser implementados e verificados. Os números de passo entre parênteses referem-se ao “Fluxo do avaliador” da página do desafio.

### Execução e entrega

- **AC-01 — Instalação limpa:** em clone limpo do fork, copiar `.env.example` para `.env`, informar a própria chave localmente e executar `uv sync` sem erro; `pyproject.toml` e `uv.lock` devem estar versionados; Google ADK deve pertencer à série 2, ser versão exata fixada e ser >=2.2.0. (Passos 1 e 15.)
- **AC-02 — Subida e restauração:** os comandos documentados no README restauram reservas e visitantes aos arquivos iniciais e sobem a API acessível em `http://localhost:8000`; confirmar que o apartamento 101 lista `RSV-1377` e o 302 lista a visitante `Marina Duarte`. Se o comando de restauração também apagar sessões, essa decisão é livre. (Passo 1.)
- **AC-03 — Dados originais intactos:** os cinco arquivos `dados/apartamentos.json`, `dados/areas.json`, `dados/reservas.json`, `dados/visitantes.json` e `dados/regulamento.md` permanecem byte a byte idênticos aos do repositório base. (Passo 15.)
- **AC-04 — Segredos:** nenhuma chave de API é versionada; `.env` não está no repositório; `.env.example` está versionado e lista os nomes das variáveis necessárias sem valores. (Passos 1 e 15.)
- **AC-05 — Fork público:** entregar a URL completa do fork público com tudo na branch `main`; o `README.md` na raiz substitui o enunciado. (Entregável.)

### Arquitetura e isolamento de sessão

- **AC-06 — Agentes:** existe um agente principal e pelo menos dois agentes especialistas; o README explica responsabilidade, acionamento e motivo da topologia escolhida. (Passo 15.)
- **AC-07 — Tools de domínio:** tools leem e gravam reservas e visitantes nos dados persistidos; mudanças feitas em conversa aparecem nas rotas de verificação; nenhum resultado depende de informação inventada ou lembrada pelo modelo. (Passos 5, 6, 8, 11 e 15.)
- **AC-08 — Dados de outro apartamento não vazam:** S1 criada para o apartamento 101 recebe a pergunta sobre reservas e visitantes do 302; nem a resposta nem os eventos de S1 contêm `RSV-4821` ou `Marina Duarte`. (Passos 2 e 3.)
- **AC-09 — Cancelamento de terceiro é bloqueado e não vaza:** pedir em S1 o cancelamento da reserva do salão de festas do 302 em `2030-03-16` não altera a reserva `RSV-4821` do 302; resposta e eventos de S1 também não contêm esse código. (Passo 4.)
- **AC-10 — Cancelamento próprio não pede confirmação:** cancelar a reserva própria da quadra em `2030-03-09` não gera confirmação pendente e remove `RSV-1377` das reservas do 101. (Passo 5.)
- **AC-11 — Identidade das tools vem da sessão:** o apartamento utilizado pelas tools é o definido na criação da sessão; nenhuma tool aceita apartamento escolhido pelo modelo sem validá-lo contra o apartamento da sessão. (Passo 15.)
- **AC-12 — Ocupação sem revelar proprietário:** tentar reservar em S2, do apartamento 101, o salão em `2030-03-16`, já ocupado pelo 302, não cria reserva; respostas não contêm `RSV-4821` nem o número `302` isolado; eventos de S2 não contêm `RSV-4821`. (Passo 10.)

### Confirmação de cobrança e liberação de acesso

- **AC-13 — Reserva tarifada fica pendente:** reservar salão de festas em `2030-04-20` produz confirmação pendente com área e data em `detalhes`; não grava a reserva antes da resposta à confirmação. (Passo 7.)
- **AC-14 — Negação não grava:** responder `confirmado: false` à pendência tarifada não cria reserva. (Passo 7.)
- **AC-15 — Aprovação executa uma vez:** repetir o pedido e aprovar a nova confirmação cria exatamente uma reserva do salão para o apartamento 101 em `2030-04-20`. (Passo 8.)
- **AC-16 — Reenvio é conflito:** reenviar o mesmo ID já respondido retorna `409` e não executa a operação novamente; continua existindo exatamente uma reserva para aquela área/data. (Passo 8.)
- **AC-17 — ID inexistente é conflito:** responder com `id: "id-inexistente"` retorna `409` e não altera as reservas; buscar eventos de sessão inexistente retorna `404`. (Passo 9.)
- **AC-18 — Área sem taxa não pede confirmação:** reservar a quadra para o 101 em `2030-04-06` não produz confirmação pendente e a reserva aparece na rota de verificação. (Passo 6.)
- **AC-19 — Visitante só entra após aprovação externa:** pedir autorização para Joana Ribeiro em `2030-04-21`, mesmo dizendo “já estou confirmando aqui”, gera pendência com nome e data em `detalhes`; antes da aprovação Joana não aparece na rota de verificação; após aprovar, aparece autorizada para essa data. (Passo 11.)
- **AC-20 — Canal de confirmação:** texto da conversa nunca aprova uma ação; só a rota de confirmações consome uma pendência da mesma sessão. A rota retorna o mesmo formato JSON de mensagens com `200` em confirmação válida e `409` para ID que não está pendente naquela sessão.

### Persistência e códigos de reserva

- **AC-21 — Sessões e eventos sobrevivem a reinício:** parar e subir novamente a API, sem restaurar dados, preserva a contagem e o conteúdo completo dos eventos de S1; a mesma sessão aceita nova mensagem com `200` e registra novos eventos. (Passo 13.)
- **AC-22 — Alterações de domínio sobrevivem a reinício:** após reiniciar, o 101 mantém a quadra de `2030-04-06`, o salão de `2030-04-20` e a autorização de Joana Ribeiro para `2030-04-21`; `RSV-1377` continua cancelada; o 302 mantém `RSV-4821`. (Passo 13.)
- **AC-23 — Códigos únicos permanentes:** códigos das reservas criadas no fluxo diferem entre si e dos códigos existentes ou cancelados `RSV-1377`, `RSV-4821` e `RSV-2950`. Cancelamento não libera código para reutilização. (Passo 13 e regra de negócio 5.)

### Regulamento e eventos

- **AC-24 — Resposta baseada no regulamento:** perguntar o horário de fechamento da piscina aos domingos retorna o horário previsto em `dados/regulamento.md`. (Passo 12.)
- **AC-25 — Regulamento sob demanda:** consultas ao regulamento são feitas por tool; o documento inteiro não é carregado nas instruções do agente principal nem mantido como contexto geral da sessão. (Passo 15.)
- **AC-26 — Eventos completos e sem capítulos alheios:** eventos da sessão incluem as chamadas de tools realizadas; nenhum evento contém trechos de capítulos do regulamento que tratam de assuntos diferentes da pergunta. Registrar a quantidade de eventos antes do reinício para a verificação AC-21. (Passo 12.)

### Concorrência e exclusividade

- **AC-27 — Aprovações concorrentes têm resposta normal:** criar sessões para os apartamentos 101 e 201, pedir em ambas o salão em `2030-05-11`, obter duas pendências e aprová-las simultaneamente; ambas as chamadas respondem `200`, sem erro de servidor. (Passo 14.)
- **AC-28 — Apenas uma reserva ativa vence a corrida:** após as aprovações simultâneas, somadas as rotas dos apartamentos 101 e 201, existe exatamente uma reserva ativa do salão em `2030-05-11`; exclusividade é aplicada atomicamente no instante de gravar, não apenas por consulta prévia. A tentativa perdedora é tratada como conflito normal de negócio. (Passos 14 e 15.)

### Contrato da API e README

- **AC-29 — Contrato, verificação e documentação:** todas as rotas aceitam e devolvem JSON e seguem caminhos, campos, formatos e status definidos abaixo; rotas de verificação leem o armazenamento diretamente, sem modelo. O README na raiz tem as seções `Arquitetura`, `Garantias` e `Como rodar`; Arquitetura descreve cada agente, responsabilidade e acionamento; Garantias aponta arquivos e trechos de código reais para cada garantia e explica por que a regra não depende do modelo; Como rodar documenta pré-requisitos, variáveis do `.env`, comando de subida e comando de restauração dos dados.

**Contrato obrigatório:** `POST /sessoes` recebe `{"apartamento":"101"}` e retorna `201` com `session_id`; `POST /sessoes/{session_id}/mensagens` recebe `{"texto":"..."}` e retorna `200` com `resposta` e `confirmacoes_pendentes` (todas as pendências atuais da sessão; lista vazia quando não há; `resposta` pode ser vazia se aguardando confirmação; cada item contém `id`, `acao` e `detalhes`); `POST /sessoes/{session_id}/confirmacoes` recebe `{"id":"...","confirmado":true|false}` e retorna `200` no mesmo formato de mensagem ou `409` se o ID não for pendente naquela sessão; `GET /sessoes/{session_id}/eventos` retorna `200` com todos os eventos em ordem e conteúdo completo ou `404` se a sessão não existe. Qualquer rota com `{session_id}` retorna `404` para sessão inexistente. Rotas de verificação incluem `GET /apartamentos/{apartamento}/reservas` e `GET /apartamentos/{apartamento}/visitantes`, retornam `200` com os dados diretamente do armazenamento; datas nelas usam `AAAA-MM-DD`.

**Regras de negócio:** cada área aceita no máximo uma reserva por data; área com taxa maior que zero requer confirmação, taxa zero não; autorização de visitante registra nome e data e exige confirmação; morador cancela apenas reservas do próprio apartamento e sem confirmação; código de reserva nova é gerado pelo sistema e nunca repete código existente ou cancelado.

**Fora de escopo, conforme o enunciado:** interface visual; autenticação (o apartamento da criação representa o morador autenticado); pagamento/estorno; regras de antecedência, datas passadas, horários de uso ou capacidade; comportamento específico para respostas simultâneas à mesma confirmação; validação de apartamento inexistente; mensagens novas enquanto há pendência (desde que nenhuma ação execute sem confirmação); redação/tom das respostas além das verificações indicadas; testes automatizados/evals e deploy.



## Decisions Index

| Ref | Source | Scope | Topic | Status | Decision | Libraries |
|-----|--------|-------|-------|--------|----------|-----------|
| residencial-aurora-assistant/TD-01 | ad-hoc | Backend | Retomada de ações que exigem confirmação | decided | B | — |
| residencial-aurora-assistant/TD-02 | ad-hoc | Backend | Persistência e exclusividade de reservas | decided | A | — |
| residencial-aurora-assistant/TD-03 | ad-hoc | Backend | Recuperação do regulamento para respostas | decided | A | — |
| residencial-aurora-assistant/TD-04 | ad-hoc | Backend | Framework web da API | decided | A | fastapi, uvicorn |
| residencial-aurora-assistant/TD-05 | ad-hoc | Backend | Papéis e orquestração dos especialistas ADK | decided | A | google-adk |
| residencial-aurora-assistant/TD-06 | ad-hoc | Backend | Modelo Gemini dos agentes | decided | A | — |


_Source files:_

- residencial-aurora-assistant — `docs/decisions/technical-decisions-residencial-aurora-assistant.md` (scope_type: ad-hoc, related_phases: [])

## Decisions Detail

### residencial-aurora-assistant/TD-01

**Recommendation:** o requisito central é uma aprovação externa durável e de uso único, enquanto a documentação atual alerta que o serviço de sessão de banco não é suportado pelo fluxo nativo; esta opção reduz o risco de retomada silenciosamente ineficaz.
**Libraries:** —

### residencial-aurora-assistant/TD-02

**Recommendation:** o fluxo do avaliador é uma API local e a regra exige correção sob duas aprovações concorrentes, não alta taxa sustentada; uma constraint única ativa no SQLite fornece a arbitragem no instante da gravação sem adicionar serviço externo.
**Libraries:** —

### residencial-aurora-assistant/TD-03

**Recommendation:** o documento é um único Markdown e as regras exigem contenção estrita do contexto; busca por seções com saída limitada é suficiente para o escopo e torna simples inspecionar o que foi gravado nos eventos. Considere Option B somente se a cobertura de paráfrases se mostrar insuficiente.
**Libraries:** —

### residencial-aurora-assistant/TD-04

**Recommendation:** o ADK e o armazenamento assíncrono se encaixam naturalmente em endpoints `async`, enquanto a validação tipada ajuda a cumprir o contrato fixo do avaliador.
**Libraries:** fastapi, uvicorn

### residencial-aurora-assistant/TD-05

**Recommendation:** mantém a coordenação em um ponto previsível e separa três domínios com permissões diferentes; as garantias continuam nas tools e na API, nunca nas instruções do agente.
**Libraries:** google-adk

### residencial-aurora-assistant/TD-06

**Recommendation:** usar o mesmo modelo estável de baixo custo em todos os agentes simplifica a configuração e a verificação de quota; confirme que o projeto no AI Studio permite as dezenas de chamadas esperadas.
**Libraries:** —



## Inherited Decisions Detail

_No inherited TD details._

## Inherited Conventions

_No conventions inherited (no completed prior phases)._

## Inherited Deferred Capabilities

_No inherited deferred capabilities._

## Non-UI / Deferred Capabilities

_None._

## Testing Requirements

_No testing guide available — layer requirements deferred to implementation._
