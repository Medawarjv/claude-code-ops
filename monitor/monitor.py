"""Monitor de sessões do Claude Code: o que cada sessão aberta está fazendo e quais esperam por você.

Lê só arquivos locais do Claude Code (~/.claude/sessions/*.json e o fim de cada transcript em ~/.claude/projects/)
e mostra, por sessão: estado (pedindo permissão, perguntou algo, interrompida, respondeu, trabalhando, parada),
último pedido, começo da resposta, ferramenta pendente, subagentes rodando, tamanho do contexto, custo e modelo.
Não chama API, não gasta token, não escreve em projeto. Três ações, todas por clique:
  - abrir a sessão no VS Code (link oficial da extensão do Claude Code);
  - sugerir 3 respostas com o Haiku (a única ação que gasta token, ~US$ 0,004 por clique);
  - renomear a aba da sessão (uma linha `custom-title` no transcript, o mesmo que o /rename faz).

    python monitor.py                 sobe em http://127.0.0.1:8771 (--porta N para outra)
    python monitor.py --demo          usa as sessões falsas de monitor/demo/ (rodar antes: python gerar_demo.py)
    python monitor.py --uma-vez       imprime o estado em JSON e sai

Configuração opcional em monitor/config.json (modelo em config.example.json): porta, pasta do Claude e arquivos
de pendências ("- [ ] ..." vira item em "Precisa de você").
Extraído do painel operacional de um canal de YouTube tocado por agentes; aqui ficou só a parte genérica.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

try:
    import psutil
except ImportError:  # sem psutil, a checagem de "processo vivo" fica mais simples
    psutil = None

AQUI = Path(__file__).resolve().parent
CFG = {"porta": 8771, "pasta_claude": str(Path.home() / ".claude"), "pendencias": [], "estilo_usuario": ""}
cfg_arq = AQUI / "config.json"
if cfg_arq.exists():
    CFG.update(json.loads(cfg_arq.read_text(encoding="utf-8")))
DEMO = "--demo" in sys.argv
CLAUDE = AQUI / "demo" if DEMO else Path(os.path.expanduser(CFG["pasta_claude"]))
PORTA = int(sys.argv[sys.argv.index("--porta") + 1]) if "--porta" in sys.argv else int(CFG["porta"])
TOKEN = secrets.token_hex(12)  # a página recebe ao carregar; sem ele nenhuma ação é aceita
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RE_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PASTA_HAIKU = Path(tempfile.gettempdir()) / "monitor-haiku"  # pasta neutra: o Haiku não carrega CLAUDE.md de projeto

_cache_fim: dict = {}
_cache_caminho: dict = {}
_cache_sug: dict = {}


def _txt(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _limpo(s, n: int = 300) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ───────────────────────── leitura das sessões ─────────────────────────

def _transcript(sid: str):
    p = _cache_caminho.get(sid)
    if p and p.exists():
        return p
    for p in (CLAUDE / "projects").glob(f"*/{sid}.jsonl"):
        _cache_caminho[sid] = p
        return p
    return None


def _resumo_ferramenta(nome: str, entrada) -> str:
    e = entrada if isinstance(entrada, dict) else {}
    det = e.get("description") or e.get("command") or e.get("pattern") or e.get("skill") or e.get("url") or ""
    if e.get("file_path"):
        det = Path(str(e["file_path"])).name
    nome = nome.split("__")[-1]  # mcp__servidor__ferramenta -> ferramenta
    return _limpo(f"{nome}: {det}" if det and len(str(det)) > 2 else nome, 110)


def _ler_fim(p: Path) -> dict:
    """Resume o fim do transcript. Ele chega a 15 MB: lê só o rabo e guarda pelo mtime."""
    st = p.stat()
    c = _cache_fim.get(p)
    if c and c[0] == st.st_mtime and c[1] == st.st_size:
        return c[2]
    r = None
    for n in (1_200_000, 6_000_000):  # uma captura de tela no transcript passa de 300 KB
        with open(p, "rb") as f:
            if st.st_size > n:
                f.seek(st.st_size - n)
                f.readline()
            texto = f.read().decode("utf-8", "replace")
        r = _interpretar(texto.splitlines())
        if r["mensagens"] or st.st_size <= n:
            break
    _cache_fim[p] = (st.st_mtime, st.st_size, r)
    return r


def _interpretar(linhas) -> dict:
    r = {"titulo": None, "pedido": None, "fala": "", "custo": None, "contexto": None, "modelo": None,
         "fechado": False, "ferramenta": None, "mensagens": 0}
    custom = ai = None
    pend: dict = {}
    ultimo = None
    for l in linhas:
        if not l.startswith("{"):
            continue
        try:
            o = json.loads(l)
        except ValueError:
            continue
        t = o.get("type")
        if t == "ai-title":
            ai = o.get("aiTitle") or ai
        elif t == "custom-title":
            custom = o.get("customTitle") or custom
        elif t == "last-prompt":
            r["pedido"] = o.get("lastPrompt") or r["pedido"]
        elif t == "cost-state":
            v = o.get("totalCostUSD")
            if v is None and isinstance(o.get("state"), dict):
                v = o["state"].get("totalCostUSD")
            r["custo"] = v if v is not None else r["custo"]
        elif t in ("user", "assistant", "system") and not o.get("isSidechain"):
            r["mensagens"] += 1
            m = o.get("message") or {}
            cont = m.get("content")
            if t == "assistant":
                u = m.get("usage") or {}
                ctx = sum(u.get(k) or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
                if ctx:
                    r["contexto"] = ctx
                r["modelo"] = m.get("model") or r["modelo"]
                for b in cont if isinstance(cont, list) else []:
                    if b.get("type") == "text" and (b.get("text") or "").strip():
                        r["fala"] = b["text"]
                    elif b.get("type") == "tool_use":
                        pend[b.get("id")] = _resumo_ferramenta(b.get("name", ""), b.get("input"))
                ultimo = ("assistant", m.get("stop_reason"))
            elif t == "user":
                for b in cont if isinstance(cont, list) else []:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        pend.pop(b.get("tool_use_id"), None)
                    elif isinstance(b, dict) and b.get("type") == "text" and not r["pedido"]:
                        r["pedido"] = b.get("text")
                if isinstance(cont, str) and not o.get("isMeta"):
                    r["pedido"] = cont
                ultimo = ("user", None)
            elif o.get("subtype") == "stop_hook_summary":
                ultimo = ("fim", None)
    r["titulo"] = custom or ai
    r["fechado"] = bool(ultimo) and (ultimo[0] == "fim" or ultimo == ("assistant", "end_turn"))
    if not r["fechado"] and pend:
        r["ferramenta"] = list(pend.values())[-1]
    return r


def _fala(texto: str) -> dict:
    """O começo da resposta (é onde fica o resultado) e a última pergunta feita ao usuário, se houver."""
    t = re.sub(r"[*`]+|^#+\s*", "", texto or "", flags=re.M).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip() and not p.strip().startswith("|")]
    pergunta = ""
    for l in reversed(t[-700:].splitlines()):
        if "?" in l and not l.strip().startswith("|"):
            pergunta = l.strip(" -•\t")
            break
    inteira = t if len(t) <= 1800 else t[:700] + "\n[…]\n" + t[-1000:]
    return {"inicio": _limpo(paras[0] if paras else "", 300), "pergunta": _limpo(pergunta, 300), "inteira": inteira}


def _agentes(tr: Path, agora: float) -> tuple[list, float]:
    """Subagentes ainda escrevendo (últimos 150 s) e a hora do último sinal de vida deles."""
    pasta = tr.with_suffix("") / "subagents"
    saida, sinal = [], 0.0
    if not pasta.is_dir():
        return saida, sinal
    for meta in pasta.glob("agent-*.meta.json"):
        j = meta.with_name(meta.name.replace(".meta.json", ".jsonl"))
        try:
            st = j.stat()
        except OSError:
            continue
        sinal = max(sinal, st.st_mtime)
        if agora - st.st_mtime < 150:
            m = _json(meta) or {}
            saida.append({"tipo": m.get("agentType") or "agente", "desc": _limpo(m.get("description"), 60),
                          "modelo": (m.get("model") or "").replace("claude-", "")})
    return saida, sinal


def _viva(pid) -> bool:
    if DEMO:
        return True
    if psutil is None:
        return True
    try:
        return "claude" in psutil.Process(int(pid)).name().lower() or "node" in psutil.Process(int(pid)).name().lower()
    except (psutil.Error, ValueError):
        return False


def sessoes() -> list:
    agora = time.time()
    saida = []
    for f in (CLAUDE / "sessions").glob("*.json"):
        s = _json(f)
        if not s or not s.get("pid") or not _viva(s["pid"]):
            continue  # o arquivo fica para trás quando a sessão morre
        if Path(s.get("cwd") or ".").name == PASTA_HAIKU.name:
            continue  # a chamada do Haiku do próprio monitor
        automatica = s.get("kind", "interactive") != "interactive" or s.get("entrypoint") == "sdk-cli"
        d = {"id": s.get("sessionId"), "apelido": s.get("name") or f"pid {s['pid']}", "pasta": Path(s.get("cwd") or "").name,
             "automatica": automatica, "mudou": (s.get("statusUpdatedAt") or s.get("updatedAt") or 0) / 1000}
        tr = _transcript(s.get("sessionId") or "")
        r = _ler_fim(tr) if tr else None
        ags, sinal_ag = _agentes(tr, agora) if tr else ([], 0.0)
        sinal = max(tr.stat().st_mtime if tr else 0.0, sinal_ag)
        if DEMO:
            d["mudou"] = agora - float(s.get("demo_idade_s", 60))
        st = s.get("status")
        if automatica:  # em `claude -p` o status não é atualizado: vale a hora do transcript
            st = "busy" if agora - sinal < 600 else "idle"
            d["mudou"] = sinal or d["mudou"]
        if not r or not r["mensagens"]:
            d.update(estado="vazia", titulo="Sessão sem conversa", grupo="fechar")
        else:
            fala = _fala(r["fala"])
            d.update(titulo=r["titulo"] or _limpo(r["pedido"], 60) or "Sem título", pedido=_limpo(r["pedido"], 240),
                     fala=fala["inicio"], pergunta=fala["pergunta"], fala_inteira=fala["inteira"], custo=r["custo"],
                     contexto=r["contexto"], modelo=(r["modelo"] or "").replace("claude-", ""),
                     ferramenta=r["ferramenta"], agentes=ags)
            if st == "waiting":
                d.update(estado="permissao", grupo="voce", motivo=_limpo(s.get("waitingFor"), 60))
            elif st == "busy":
                d.update(estado="trabalhando", grupo="trabalhando")
            elif not r["fechado"]:
                d.update(estado="interrompida", grupo="voce")
            elif fala["pergunta"]:
                d.update(estado="pergunta", grupo="voce")
            elif agora - d["mudou"] < 1800:
                d.update(estado="respondeu", grupo="voce")
            else:
                d.update(estado="parada", grupo="fechar")
        saida.append(d)
    ordem = {"permissao": 0, "pergunta": 1, "interrompida": 2, "respondeu": 3, "trabalhando": 4, "parada": 6, "vazia": 7}
    saida.sort(key=lambda d: (ordem.get(d["estado"], 9), -d["mudou"]))
    return saida


def pendencias() -> list:
    """Itens "- [ ] ..." dos arquivos listados em config.json > pendencias."""
    itens = []
    arqs = [AQUI / "demo" / "PENDENCIAS.md"] if DEMO else [Path(os.path.expanduser(a)) for a in CFG["pendencias"]]
    for arq in arqs:
        for linha in _txt(arq).splitlines():
            m = re.match(r"\s*- \[ \]\s+(.+)", linha)
            if m:
                itens.append({"arquivo": arq.name, "texto": _limpo(re.sub(r"[*`]", "", m.group(1)), 240)})
    return itens


def coletar() -> dict:
    ss = sessoes()
    return {"token": TOKEN, "agora": time.time(), "demo": DEMO, "sessoes": ss, "pendencias": pendencias(),
            "custo_total": round(sum(s.get("custo") or 0 for s in ss), 2)}


# ───────────────────────── ações (sempre por clique) ─────────────────────────

PROMPT_SUG = """Você ajuda o usuário a responder a uma sessão do Claude Code que parou esperando por ele. Ele toca várias sessões ao mesmo tempo.

Escreva 3 respostas que ele poderia mandar, cada uma com uma decisão diferente e plausível para ESTE caso (por exemplo: aprovar; aprovar com um ajuste concreto tirado do texto; recusar ou pedir um detalhe específico).
Regras:
- Do jeito que ele escreve (veja os exemplos): curto, 1 a 3 frases, sem saudação. %s
- Se a sessão fez mais de uma pergunta ou deu opções, cada resposta cobre todas e cita a opção escolhida.
- Use só o que está no texto: não invente fato, número nem arquivo.

Responda só com JSON, sem cerca de código: {"respostas":[{"rotulo":"2 a 4 palavras","texto":"a resposta"}]}

EXEMPLOS DE COMO ELE ESCREVE:
%s

ÚLTIMO PEDIDO DELE NESTA SESSÃO:
%s

ÚLTIMA RESPOSTA DA SESSÃO:
%s
"""


def _sugerir(sid: str) -> dict:
    """Pede ao Haiku 3 respostas para a última fala de uma sessão. `claude -p` sem ferramentas, hooks, MCP nem
    sessão gravada, e com system prompt mínimo (com o padrão, a chamada levava ~56 s e custava ~13x)."""
    if DEMO:
        return {"ok": True, "custo": 0, "seg": 0, "respostas": [
            {"rotulo": "Aprovar", "texto": "Pode seguir assim."},
            {"rotulo": "Aprovar com ajuste", "texto": "Pode seguir, mas deixa a tabela só com os 5 primeiros."},
            {"rotulo": "Pedir detalhe", "texto": "Antes, me mostra de onde veio esse número."}]}
    tr = _transcript(sid)
    if not tr:
        return {"ok": False, "erro": "sessão não encontrada"}
    r = _ler_fim(tr)
    chave = (sid, tr.stat().st_mtime)
    if chave in _cache_sug:
        return _cache_sug[chave]
    fala = r["fala"] or ""
    if not fala.strip():
        return {"ok": False, "erro": "a sessão ainda não respondeu nada"}
    if len(fala) > 6000:
        fala = fala[:1500] + "\n[…]\n" + fala[-4500:]
    exemplos = []
    for f in (CLAUDE / "sessions").glob("*.json"):
        t = _transcript((_json(f) or {}).get("sessionId") or "")
        ped = _ler_fim(t)["pedido"] if t else None
        if ped and not ped.startswith("<") and len(ped) > 15:
            exemplos.append("- " + _limpo(ped, 220))
    exe = shutil.which("claude")
    if not exe:
        return {"ok": False, "erro": "não achei o comando claude no PATH"}
    PASTA_HAIKU.mkdir(exist_ok=True)
    (PASTA_HAIKU / "settings.json").write_text('{"disableAllHooks":true}', encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "VSCODE_")) and k != "ELECTRON_RUN_AS_NODE"}
    env["MAX_THINKING_TOKENS"] = "0"  # com raciocínio ligado: 26 a 38 s e ~8x o custo
    prompt = PROMPT_SUG % (CFG.get("estilo_usuario") or "", "\n".join(exemplos[:6]) or "- (sem exemplos)",
                           _limpo(r["pedido"], 500) or "(não registrado)", fala)
    t0 = time.time()
    try:
        p = subprocess.run([exe, "-p", "--model", "haiku", "--no-session-persistence", "--tools", "", "--strict-mcp-config",
                            "--settings", str(PASTA_HAIKU / "settings.json"), "--output-format", "json",
                            "--system-prompt", "Voce responde so com JSON valido, sem cerca de codigo."],
                           input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=90, cwd=str(PASTA_HAIKU), env=env, creationflags=SEM_JANELA)
        d = json.loads(p.stdout)
        m = re.search(r"\{.*\}", str(d.get("result") or ""), re.S)
        resp = json.loads(m.group(0))["respostas"]
    except subprocess.TimeoutExpired:
        return {"ok": False, "erro": "o Haiku não respondeu em 90 s"}
    except Exception as e:
        return {"ok": False, "erro": _limpo(f"{type(e).__name__}: {e}", 220)}
    saida = {"ok": True, "custo": d.get("total_cost_usd"), "seg": round(time.time() - t0, 1),
             "respostas": [{"rotulo": _limpo(x.get("rotulo"), 40), "texto": str(x.get("texto") or "").strip()[:600]}
                           for x in resp[:3] if isinstance(x, dict) and x.get("texto")]}
    if len(_cache_sug) > 40:
        _cache_sug.clear()
    _cache_sug[chave] = saida
    return saida


def _abre_vscode(uri: str) -> bool:
    """Entrega o link vscode:// ao VS Code. Pegadinha: iniciado de dentro do VS Code, o processo herda
    ELECTRON_RUN_AS_NODE=1 e o Code.exe recusa o link sem erro visível. Por isso o ambiente vai limpo."""
    env = {k: v for k, v in os.environ.items() if k != "ELECTRON_RUN_AS_NODE" and not k.startswith("VSCODE_")}
    if sys.platform == "win32":
        import winreg
        try:
            cmd = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, r"vscode\shell\open\command")
            exe = re.match(r'"([^"]+)"', cmd).group(1)
        except (OSError, AttributeError):
            return False
        subprocess.Popen([exe, "--open-url", "--", uri], env=env, creationflags=SEM_JANELA,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    abrir = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([abrir, uri], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def _renomear(sid: str, titulo) -> bool:
    """Muda o nome da aba: acrescenta `custom-title` ao transcript (o que o /rename faz). Só em sessão viva."""
    titulo = _limpo(titulo, 80)
    vivas = {(_json(f) or {}).get("sessionId") for f in (CLAUDE / "sessions").glob("*.json")}
    tr = _transcript(sid)
    if not titulo or sid not in vivas or not tr:
        return False
    with open(tr, "rb") as f:
        f.seek(-1, 2)
        fim = f.read(1)
    linha = json.dumps({"type": "custom-title", "customTitle": titulo, "sessionId": sid}, ensure_ascii=False)
    with open(tr, "ab") as f:
        f.write((b"" if fim == b"\n" else b"\n") + linha.encode("utf-8") + b"\n")
    return True


class Pagina(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _manda(self, codigo, corpo: bytes, tipo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _host_ok(self) -> bool:
        # defesa contra DNS rebinding: só aceita o próprio endereço local
        return (self.headers.get("Host") or "") in (f"127.0.0.1:{PORTA}", f"localhost:{PORTA}")

    def do_GET(self):
        if not self._host_ok():
            return self._manda(403, b"", "text/plain")
        rota = self.path.split("?")[0]
        if rota == "/estado.json":
            self._manda(200, json.dumps(coletar(), ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        elif rota in ("/", "/index.html"):
            self._manda(200, (AQUI / "monitor.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self._manda(404, b"", "text/plain")

    def do_POST(self):
        if not self._host_ok():
            return self._manda(403, b"{}", "application/json")
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            d = {}
        if d.get("token") != TOKEN:
            return self._manda(403, b"{}", "application/json")
        sid = str(d.get("sessao") or "")
        ok = False
        if self.path == "/vscode" and (not sid or RE_UUID.match(sid)):
            partes = ([f"session={sid}"] if sid else []) + ([f"prompt={quote(str(d['prompt'])[:1500])}"] if d.get("prompt") else [])
            partes.append(f"_={int(time.time() * 1000)}")  # link idêntico ao anterior o VS Code não reabre
            ok = DEMO or _abre_vscode("vscode://anthropic.claude-code/open?" + "&".join(partes))
        elif self.path == "/sugerir" and RE_UUID.match(sid):
            return self._manda(200, json.dumps(_sugerir(sid), ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        elif self.path == "/renomear" and RE_UUID.match(sid):
            ok = (not DEMO) and _renomear(sid, d.get("titulo"))
        self._manda(200 if ok else 403, json.dumps({"ok": ok}).encode(), "application/json")


def main():
    if sys.stdout:
        sys.stdout.reconfigure(encoding="utf-8")
    if "--uma-vez" in sys.argv:
        d = coletar()
        d.pop("token", None)
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORTA), Pagina)
    except OSError:
        sys.exit(f"O monitor já está rodando: http://127.0.0.1:{PORTA}")
    print(f"Monitor em http://127.0.0.1:{PORTA}" + ("  (modo demonstração)" if DEMO else "") + "  (Ctrl+C para parar)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
