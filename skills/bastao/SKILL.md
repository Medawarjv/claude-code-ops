---
name: bastao
description: "Passa o estado de uma sessão para a próxima pelo PROXIMA-SESSAO.md da pasta (frentes com \"Próximo:\", o que falhou, próximos passos, carimbo e teto de tamanho). Use ao encerrar sessão com trabalho em aberto, quando o usuário disser \"anota no bastão\", \"deixa anotado\", \"onde paramos?\", \"continua de onde parou\", ou quando o aviso de início mostrar bastão velho ou grande. Se a pasta tiver regra própria de bastão no CLAUDE.md, ela vale."
---

# Bastão entre sessões

Uma sessão nova não lembra da anterior. O bastão é o que ela lê primeiro para não refazer o que já foi feito nem esquecer o que ficou pela metade. O hook global (SessionStart) roda `python ~/.claude/hooks/bastao.py inicio` e avisa em uma linha que existe um bastão, de quando ele é e quais frentes estão abertas. O conteúdo só é lido quando for continuar.

## Formato

```markdown
# Próxima sessão

<!-- bastao · atualizado: AAAA-MM-DD HH:MM · limite: 40000 bytes -->

## Em andamento

### <frente, em poucas palavras>
Onde parou: <estado concreto, com caminho de arquivo, link e número>
**Falhou:** <se algo deu errado, com a mensagem literal> (opcional)
**Próximo:** <a primeira ação da próxima sessão, executável sem perguntar>

## Falhou ou travou

- <o que não funcionou e por quê, para não tentar de novo do mesmo jeito>

## Próximos passos

- <o que vem depois das frentes, em ordem>
```

`python ~/.claude/hooks/bastao.py novo` cria o arquivo com esse molde na pasta atual (não sobrescreve).

## Ao encerrar (ou quando o usuário mandar anotar)
1. Abrir o PROXIMA-SESSAO.md da pasta. Se não existir, criar com `novo`.
2. Atualizar só o que mudou: frente nova, frente que avançou (reescrever "Onde parou" e "Próximo"), frente que fechou (sai do bastão; se tiver valor histórico, vai para `PROXIMA-SESSAO-historico.md`, sem apagar nada).
3. Escrever para quem não estava na conversa: caminhos completos, links de artifact, decisões do usuário com a data e as palavras dele quando importam. Nada de "aquilo que combinamos".
4. Decisão que o usuário ainda precisa tomar vai escrita como pergunta, com a recomendação ao lado.
5. `bastao.py carimbo` e depois `bastao.py checar` (precisa dar "Bastão ok").
6. Dizer ao usuário em uma linha o que ficou anotado e onde.

## Ao retomar
- Ler o bastão inteiro antes de propor qualquer coisa.
- Se o aviso disser "PODE ESTAR VELHO" ou "editado depois, sem carimbo", conferir os arquivos citados antes de confiar no texto.
- Bastão em formato antigo (sem carimbo ou sem as seções) funciona; ao atualizar, migrar para o formato acima sem perder conteúdo.

## O que não vai no bastão
- O que vale para sempre: regra de trabalho vai para o CLAUDE.md da pasta ou para a memória; aprendizado de feedback vai pela skill `aprender-com-feedback`.
- Segredos, tokens, CPF, número de cartão.
- Histórico longo: acima do limite, mover o que fechou para o histórico.
