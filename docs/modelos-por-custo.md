# Qual modelo faz o quê (delegação por custo)

Tabela usada num projeto com 14 agentes e uma rodada automática diária. A sessão principal não troca o próprio modelo; ela **escolhe o modelo de cada tarefa que delega**, sem o usuário pedir.

| Tarefa | Quem faz | Modelo |
|---|---|---|
| Rodar scripts e conferir a saída, preencher CSV de métricas, ler telas que a API não dá, organizar arquivos, registros mecânicos | agente `operador` | Haiku |
| Publicar ou preencher formulário no navegador, já com o OK do usuário e o texto pronto | agente `operador`, chamado com `model: sonnet` | Sonnet |
| Leitura de muitos arquivos, busca na web, comparação de concorrentes; devolve só o resumo | agente `pesquisador` | Sonnet |
| Triagem e mecânica de corte de vídeo | agente especializado | Sonnet |
| Roteiro, copy, direção criativa, título, estratégia, feedback virando regra | sessão principal | Opus |
| Depurar algo que travou duas vezes, decisão de arquitetura | sessão principal | o modelo mais forte, só aqui |

## Regras
- **Delegar só o que é volumoso e bem definido.** Tarefa de até 3 passos vale fazer direto: o subagente começa do zero e relê contexto, o que custa mais que a economia.
- **Navegador é o que mais gasta** (cada screenshot pesa): nunca na sessão principal num modelo caro quando dá para mandar ao `operador`.
- O brief do subagente leva o caminho dos arquivos, o que já está decidido e o formato da resposta. Nada de mandar "descobrir" o que a sessão principal já sabe.
- **O modelo mais caro nunca roda em produção automática** (rodada agendada, linha de produção).
- Sessão longa custa mais que modelo caro: ao trocar de assunto, sugerir `/clear`.
- Com o uso semanal acima de 80%, o hook `uso_claude.py` põe a sessão em **modo economia**; acima de 90%, em **modo reserva**, e bloqueia subagente novo.

## Números medidos
- Sugestão de resposta no monitor: Haiku sem ferramentas, sem hooks e com system prompt mínimo sai por ~US$ 0,004 por clique. Com o system prompt padrão do Claude Code, a mesma chamada levava ~56 s e custava ~13x mais. Com o raciocínio estendido ligado, 26 a 38 s e ~8x mais.
- Num teste cego de revisão, um agente "revisor" dedicado acertou 1 de 5 casos e saiu da linha de produção. Mais um agente não é sempre melhor.
