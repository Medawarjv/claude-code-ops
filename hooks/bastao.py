"""Bastão entre sessões para qualquer pasta: o PROXIMA-SESSAO.md (versão global, 27/11/2026).

Quando a pasta tem tools/bastao.py próprio (um projeto com regras de bastão a mais), este fica calado para
não avisar duas vezes.

  python bastao.py inicio  [--pasta P]   hook SessionStart: 1 linha com idade e frentes (lê o cwd do hook)
  python bastao.py checar  [--pasta P]   antes de encerrar: carimbo, seções, "Próximo:" em cada frente, tamanho
  python bastao.py carimbo [--pasta P]   atualiza a data do carimbo para agora
  python bastao.py novo    [--pasta P]   cria o PROXIMA-SESSAO.md no formato padrão (não sobrescreve)

Formato: carimbo `<!-- bastao · atualizado: AAAA-MM-DD HH:MM · limite: N bytes -->`, seções
"## Em andamento" (uma "### frente" cada, com **Próximo:**), "## Falhou ou travou", "## Próximos passos".
Arquivos antigos sem esse formato funcionam: o início usa a data de modificação e lista os títulos.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NOME = "PROXIMA-SESSAO.md"
SECOES = ("Em andamento", "Falhou ou travou", "Próximos passos")
LIMITE_PADRAO = 40000
RE_CARIMBO = re.compile(r"<!-- bastao · atualizado: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · limite: (\d+) bytes -->")
IGNORAR = {".git", "node_modules", "__pycache__", ".venv", "venv", "saida", "AppData"}


def outro_projeto(d: Path) -> bool:
    """Subpasta com CLAUDE.md ou .claude é outro projeto: o bastão dela aparece só quando a sessão abre lá."""
    return (d / "CLAUDE.md").exists() or (d / ".claude").is_dir()

MODELO = """# Próxima sessão

<!-- bastao · atualizado: {agora} · limite: {limite} bytes -->

O que uma sessão nova precisa saber para continuar. O que fechou sai daqui (vai para o histórico ou some).

## Em andamento

### <frente>
Onde parou: ...
**Próximo:** ...

## Falhou ou travou

- nada

## Próximos passos

- ...
"""


def pasta_do_hook() -> Path:
    """O hook recebe JSON no stdin com "cwd"; fora do hook, usa o diretório atual."""
    if not sys.stdin.isatty():
        try:
            dados = json.loads(sys.stdin.read() or "{}")
            if dados.get("cwd"):
                return Path(dados["cwd"])
        except Exception:
            pass
    return Path.cwd()


def achar(pasta: Path) -> list[Path]:
    """PROXIMA-SESSAO.md na pasta ou até 3 níveis abaixo (ex.: um bastão dentro de uma subpasta de análise)."""
    direto = pasta / NOME
    if direto.exists():
        return [direto]
    if pasta == Path.home().resolve():
        return []  # a pasta do usuário só tem atalhos de sistema e outros projetos abaixo dela
    achados = []
    for raiz, dirs, arqs in os.walk(pasta):
        nivel = len(Path(raiz).relative_to(pasta).parts)
        dirs[:] = [d for d in dirs if d not in IGNORAR and not d.startswith(".")
                   and not outro_projeto(Path(raiz) / d)] if nivel < 3 else []
        if NOME in arqs:
            achados.append(Path(raiz) / NOME)
    return sorted(achados)


def ler(arq: Path):
    texto = arq.read_text(encoding="utf-8", errors="replace")
    m = RE_CARIMBO.search(texto)
    quando = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M") if m else None
    limite = int(m.group(2)) if m else LIMITE_PADRAO
    return texto, quando, limite


def secao(texto: str, nome: str) -> str:
    m = re.search(rf"^## {re.escape(nome)}.*?$(.*?)(?=^## |\Z)", texto, re.M | re.S)
    return m.group(1) if m else ""


def frentes(texto: str) -> list[str]:
    fr = [t.strip() for t in re.findall(r"^### (.+)$", secao(texto, "Em andamento"), re.M)]
    if fr:
        return fr
    # formato livre: os títulos "##" servem de frentes
    return [t.strip() for t in re.findall(r"^## (.+)$", texto, re.M)][:6]


def _idade(quando: dt.datetime) -> str:
    h = max(0.0, (dt.datetime.now() - quando).total_seconds() / 3600)
    return f"há {h:.0f} h" if h < 48 else f"há {h / 24:.0f} dias"


def resumo(arq: Path, base: Path) -> str:
    texto, quando, limite = ler(arq)
    mtime = dt.datetime.fromtimestamp(arq.stat().st_mtime)
    partes = []
    if quando:
        partes.append(f"atualizado {_idade(quando)} ({quando:%d/%m %H:%M})")
        if (mtime - quando).total_seconds() > 3600:
            partes.append(f"editado depois, em {mtime:%d/%m %H:%M}, sem carimbo")
    else:
        partes.append(f"sem carimbo, modificado {_idade(mtime)} ({mtime:%d/%m %H:%M})")
    ref = quando or mtime
    if (dt.datetime.now() - ref).total_seconds() > 7 * 24 * 3600:
        partes.append("PODE ESTAR VELHO: conferir antes de confiar")
    fr = frentes(texto)
    partes.append(f"{len(fr)} frente(s)" + (": " + " | ".join(fr) if fr else ""))
    tam = len(texto.encode())
    if tam > limite:
        partes.append(f"{tam} bytes, acima do limite de {limite}: enxugar ao encerrar")
    try:
        rel = arq.relative_to(base)
    except ValueError:
        rel = arq
    return f"Bastão ({rel}): " + "; ".join(partes) + "."


def cmd_inicio(pasta: Path) -> int:
    if (pasta / "tools" / "bastao.py").exists():
        return 0  # a pasta tem bastão próprio; o hook do projeto já avisa
    arqs = achar(pasta)
    if not arqs:
        return 0  # pasta sem bastão: silêncio
    for a in arqs:
        print(resumo(a, pasta))
    print("Ler o bastão antes de continuar qualquer frente. Ao encerrar uma sessão com trabalho em aberto, "
          "atualizar o arquivo (skill bastao).")
    return 0


def _um(pasta: Path) -> Path | None:
    arqs = achar(pasta)
    if not arqs:
        print(f"Nenhum {NOME} em {pasta}. Use `novo` para criar.")
        return None
    if len(arqs) > 1:
        print("Mais de um bastão; use --pasta com a pasta certa:\n- " + "\n- ".join(map(str, arqs)))
        return None
    return arqs[0]


def cmd_checar(pasta: Path) -> int:
    arq = _um(pasta)
    if not arq:
        return 1
    texto, quando, limite = ler(arq)
    erros = []
    if not quando:
        erros.append("falta o carimbo (rodar `carimbo`)")
    for s in SECOES:
        if not re.search(rf"^## {re.escape(s)}", texto, re.M):
            erros.append(f"falta a seção '## {s}'")
    for bloco in re.split(r"^### ", secao(texto, "Em andamento"), flags=re.M)[1:]:
        titulo = bloco.split("\n", 1)[0].strip()
        if "**Próximo:**" not in bloco:
            erros.append(f"frente '{titulo}' sem **Próximo:**")
    tam = len(texto.encode())
    if tam > limite:
        erros.append(f"{tam} bytes, acima do limite de {limite}: mover o que fechou para o histórico")
    if erros:
        print(f"Bastão com problema ({arq}):\n- " + "\n- ".join(erros))
        return 1
    print(f"Bastão ok ({arq}): {len(frentes(texto))} frente(s), {tam}/{limite} bytes, carimbo {quando:%d/%m %H:%M}.")
    return 0


def cmd_carimbo(pasta: Path) -> int:
    arq = _um(pasta)
    if not arq:
        return 1
    texto, _, limite = ler(arq)
    agora = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    novo = f"<!-- bastao · atualizado: {agora} · limite: {limite} bytes -->"
    texto = RE_CARIMBO.sub(novo, texto, count=1) if RE_CARIMBO.search(texto) else texto.replace("\n", f"\n\n{novo}\n", 1)
    arq.write_text(texto, encoding="utf-8", newline="")
    print(f"carimbo: {agora} ({arq})")
    return 0


def cmd_novo(pasta: Path) -> int:
    arq = pasta / NOME
    if arq.exists():
        print(f"Já existe: {arq}. Nada foi alterado.")
        return 1
    agora = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    arq.write_text(MODELO.format(agora=agora, limite=LIMITE_PADRAO), encoding="utf-8", newline="")
    print(f"criado: {arq}")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "inicio"
    if "--pasta" in args:
        pasta = Path(args[args.index("--pasta") + 1])
    elif cmd == "inicio":
        pasta = pasta_do_hook()
    else:
        pasta = Path.cwd()
    acoes = {"inicio": cmd_inicio, "checar": cmd_checar, "carimbo": cmd_carimbo, "novo": cmd_novo}
    try:
        sys.exit(acoes.get(cmd, cmd_inicio)(pasta.resolve()))
    except Exception as e:  # o hook nunca pode travar o início da sessão
        print(f"bastao.py: erro ignorado ({e})")
        sys.exit(0)
