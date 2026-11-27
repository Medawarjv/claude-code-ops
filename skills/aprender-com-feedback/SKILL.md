---
name: aprender-com-feedback
description: "Transforma correção, aprovação ou reprovação do usuário sobre trabalho que se repete (documento com versões, apresentação, texto, post, planilha, rotina do projeto) em aprendizado permanente: registro literal, regra ajustada, checagem automática quando dá para medir, par \"minha versão → a dele\", lista do que manter. Use quando ele disser \"ficou ruim\", \"não era isso\", \"tira isso\", \"mantém\", \"de novo esse erro\", \"eu já falei\", \"pode mandar assim\", mesmo sem pedir para anotar. Resposta pontual de conversa não precisa. Se a pasta tiver uma skill própria de feedback, use a de lá."
---

# Aprender com o feedback

Nasceu num projeto de vídeo tocado por agentes, que provou duas coisas: regra só no papel não impediu a repetição, e checagem automática impediu. O usuário não deveria ter de repetir um pedido. Este passo se faz **na hora**, antes de voltar ao conserto, sem ele pedir.

## Onde ficam os arquivos do projeto
Usar o que a pasta já tem. Se não tiver, criar em `aprendizados/` na raiz da pasta:
- `aprendizados/feedback.md`: diário literal, o mais novo no topo.
- `aprendizados/regras.md`: o manual vivo, por assunto.
- `aprendizados/pares.md`: textos reprovados e a versão dele.
- `manter.md` dentro da pasta da peça, quando a peça tem versões.

Se o projeto já guarda regras em outro lugar (CLAUDE.md, CONTEXTO.md, uma skill do projeto), a regra vai **lá**, na seção certa, e não num arquivo paralelo. Duas fontes de regra viram contradição.

## 1. Separar o comentário em itens
| Tipo | Exemplo | Vai para |
|---|---|---|
| conserto só desta peça | "o gráfico da página 3 está cortado" | conserto + feedback.md |
| gosto que vale para as próximas | "não gosto de tabela com borda" | + regra |
| defeito medível | número sem fonte, texto saindo da caixa, total que não fecha, data errada, arquivo no lugar errado, palavra proibida | + checagem automática (passo 4) |
| texto reprovado | título, frase, mensagem, resumo | + par em pares.md (passo 5) |
| "manter" | "mantém essa capa", "pode mandar assim" | + manter.md (passo 6) |
| aprovação | "ficou ótimo" | feedback.md + subir a confiança da regra que funcionou |
| decisão de processo | "daqui pra frente, sempre em PDF" | regra; memória só se valer fora deste projeto |

Item ambíguo: perguntar **uma** vez, curto, e registrar a pergunta como pendente. Nunca inventar a causa.

## 2. feedback.md
```
## DD/MM/AAAA · <peça> (`<caminho do arquivo>`)
**Disse:** "<as palavras dele, entre aspas>"
**Mudou:** <o que consertei ou vou consertar, por item>
**Causa:** <só se eu souber; hipótese marcada como hipótese>
**Regras:** <regra afetada, checagem criada, par, manter; ou "nenhuma, conserto pontual">
```
As palavras dele vão literais: é o que permite reler a intenção depois.

## 3. Regra
- Procurar a regra que já existe sobre o assunto e **ajustar essa**, em vez de criar outra ao lado.
- Nível: 👀 pedido dele; ✅ pedido dele confirmado por resultado ou repetição; 📈 dado medido (3+ casos); 🧪 hipótese minha. Origem no fim: `*(usuário, DD/MM, <peça>: "<frase curta>")*`.
- Comentário que contradiz uma regra: reescrever a regra e dizer no feedback.md o que mudou. Regra dele não cai por dado sozinho; regra 🧪 minha cai com o comentário dele.
- Corrigir na medida: a regra diz o ajuste que ele pediu, não o extremo oposto.

## 4. Checagem automática, quando o defeito dá para medir
Pergunta: **uma máquina consegue ver isso sem eu olhar?** Se sim, a checagem é obrigatória:
1. Pôr no script que já roda naquela etapa (o conferidor do projeto, o gerador do PDF, o script de publicação). Se o projeto não tem nenhum, criar `tools/conferir.py` pequeno, com uma função por checagem.
2. ❌ quando o usuário reprovou; ⚠️ quando é questão de gosto.
3. **Testar contra o caso que falhou (tem que dar ❌) e contra um aprovado (tem que dar ✅).** Sem os dois testes, não está pronta.
4. Anotar no feedback.md o nome da checagem e os dois resultados.

Se não dá para medir (gosto, tom, coerência), escrever "não medível" e deixar a regra onde a conferência final lê.

## 5. Texto reprovado → par
Se ele reprovou um texto sem reescrever, pedir em uma linha: **"Reescreve do jeito que você falaria? Guardo o par para não repetir."** Linha nova no topo de `pares.md`: data, peça, minha versão, a dele, o princípio em uma frase. Antes de escrever texto parecido, ler os pares.

## 6. "Mantém isso" → manter.md
Tudo que ele mandar manter, ou aprovar numa versão, entra no `manter.md` da pasta da peça, para nenhuma versão seguinte perder. Versão nova em pasta ou arquivo novo: levar o manter.md junto e conferir item por item antes de entregar.

## 7. Fechar
- Se mudou o que está pendente, atualizar o bastão (skill `bastao`).
- Memória só para o que vale além deste projeto ou para o jeito de trabalhar com o usuário.
- Responder numa linha por item: o que mudou e onde ficou ("Borda nas tabelas: regra nova em regras.md › Visual. Capa: no manter.md, conferida antes de cada versão.").
