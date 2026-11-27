"""Medidor do uso semanal do Claude, com modo economia e modo reserva.

Usa só o que a própria barra de status do Claude Code recebe (o campo `rate_limits` do JSON no stdin):
não lê token, não chama API. A barra grava o último valor em ~/.claude/state/uso.json; os hooks leem esse arquivo.

Modos (primeiro argumento):
  statusline  barra de status: recebe o JSON no stdin, grava o estado e imprime "Modelo | semana 63% (normal) | 5h 12%"
  prompt      hook UserPromptSubmit/SessionStart: injeta no contexto o modo atual quando é economia ou reserva
  agente      hook PreToolUse do Agent: bloqueia subagente novo no modo reserva
  ver         imprime o estado em JSON (para outros scripts)

Limiares: CLAUDE_USO_ECONOMIA (padrão 80) e CLAUDE_USO_RESERVA (padrão 90), em % do limite semanal.
Para liberar o modo reserva de propósito: criar ~/.claude/state/uso-liberado.
"""
import datetime
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.expanduser("~/.claude/state")
ESTADO = os.path.join(BASE, "uso.json")
LOG = os.path.join(BASE, "uso-log.jsonl")
LIBERADO = os.path.join(BASE, "uso-liberado")
ECONOMIA = float(os.environ.get("CLAUDE_USO_ECONOMIA", 80))
RESERVA = float(os.environ.get("CLAUDE_USO_RESERVA", 90))

MSG_ECONOMIA = ("MODO ECONOMIA: subagentes só em Haiku ou Sonnet; nada de navegador na sessão principal; "
                "não refazer trabalho pronto; priorizar o que entrega hoje.")
MSG_RESERVA = ("MODO RESERVA: não começar tarefa nova. Só terminar o que está no meio e responder ao usuário. "
               "Subagente novo está bloqueado pelo hook. Se estiver no meio de algo, salvar o estado no bastão e parar.")


def ler():
    try:
        with open(ESTADO, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def modo(pct):
    if pct is None:
        return "desconhecido"
    return "reserva" if pct >= RESERVA else "economia" if pct >= ECONOMIA else "normal"


def statusline():
    try:
        d = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        d = {}
    rl = d.get("rate_limits") or {}
    sem, cin = rl.get("seven_day") or {}, rl.get("five_hour") or {}
    pct = sem.get("used_percentage")
    if pct is not None:
        novo = {"semanal": pct, "semanal_reset": sem.get("resets_at"), "cinco_horas": cin.get("used_percentage"),
                "cinco_horas_reset": cin.get("resets_at"), "lido_em": time.time()}
        antigo = ler()
        os.makedirs(BASE, exist_ok=True)
        with open(ESTADO, "w", encoding="utf-8") as f:
            json.dump(novo, f)
        if round(antigo.get("semanal", -1)) != round(pct):  # histórico: uma linha por ponto percentual
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": datetime.datetime.now().isoformat(timespec="minutes"), **novo}) + "\n")
    e = ler()
    p = e.get("semanal")
    nome = (d.get("model") or {}).get("display_name", "")
    txt = f"{nome} | semana {p:.0f}% ({modo(p)})" if p is not None else f"{nome} | semana ?"
    if e.get("cinco_horas") is not None:
        txt += f" | 5h {e['cinco_horas']:.0f}%"
    print(txt)


def aviso():
    e = ler()
    p = e.get("semanal")
    m = modo(p)
    if m in ("normal", "desconhecido"):
        return None, m
    idade = (time.time() - e.get("lido_em", 0)) / 60
    base = f"Uso semanal do Claude: {p:.0f}% (lido há {idade:.0f} min). "
    return base + (MSG_ECONOMIA if m == "economia" else MSG_RESERVA), m


def prompt():
    txt, m = aviso()
    # rotina automática (claude -p de um agendador) não começa no modo reserva
    if m == "reserva" and not os.path.exists(LIBERADO) and os.environ.get("CLAUDE_CODE_ENTRYPOINT") == "sdk-cli":
        print(json.dumps({"decision": "block", "reason": "Rotina pulada: " + txt}))
        return
    if txt:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": os.environ.get("EVENTO", "UserPromptSubmit"),
                                                 "additionalContext": txt}}))


def agente():
    txt, m = aviso()
    if m == "reserva" and not os.path.exists(LIBERADO):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": txt + f" (Para liberar: criar {LIBERADO}.)"}}))


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "ver"
    {"statusline": statusline, "prompt": prompt, "agente": agente,
     "ver": lambda: print(json.dumps({**ler(), "modo": modo(ler().get("semanal"))}))}[acao]()
