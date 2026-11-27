"""Gera monitor/demo/: sessões e transcripts falsos no mesmo formato do Claude Code, para `monitor.py --demo`."""
import json
import time
from pathlib import Path

DEMO = Path(__file__).resolve().parent / "demo"
SESSOES = [
    # id, pasta, apelido, status, idade (s), título, pedido, resposta, ferramenta pendente, subagente, custo, contexto
    ("11111111-1111-4111-8111-111111111111", "relatorio-vendas", "vendas", "waiting", 40,
     "Relatório de vendas de outubro", "monta o relatório de vendas de outubro com a margem por produto",
     "Vou ler as 3 planilhas de vendas e cruzar com o custo de reposição.", ("Bash", {"command": "python carregar.py vendas/*.csv"}), None, 0.84, 61000),
    ("22222222-2222-4222-8222-222222222222", "site-loja", "site", "idle", 300,
     "Migrar página de preços", "troca a tabela de preços pela versão nova e confere no celular",
     "A página nova está pronta e passou no teste de 390 px.\n\nPublico agora ou espera a revisão do texto?", None, None, 1.92, 118000),
    ("33333333-3333-4333-8333-333333333333", "pesquisa-fornecedores", "fornecedores", "busy", 20,
     "Comparar 4 fornecedores", "compara os 4 fornecedores de embalagem por preço, prazo e reclamações",
     "Mandei o pesquisador ler as 4 propostas e as avaliações públicas.", ("Agent", {"description": "Ler propostas e avaliações"}),
     ("pesquisador", "sonnet", "Ler propostas e avaliações"), 0.37, 42000),
    ("44444444-4444-4444-8444-444444444444", "financas", "financas", "idle", 900,
     "Fechamento do mês", "fecha o mês de outubro",
     "Fechamento de outubro pronto: R$ 12.310 gastos contra o orçamento de R$ 13.500. Duas categorias passaram do teto.", None, None, 2.40, 96000),
    ("55555555-5555-4555-8555-555555555555", "post-linkedin", "linkedin", "idle", 7200,
     "Post sobre o protótipo", "escreve 3 versões de post sobre o protótipo de cotação",
     "As 3 versões estão no arquivo post.md, com o gancho de cada uma testado em voz alta.", None, None, 0.21, 23000),
]


def main():
    (DEMO / "sessions").mkdir(parents=True, exist_ok=True)
    agora_ms = int(time.time() * 1000)
    for i, (sid, pasta, apelido, status, idade, titulo, pedido, fala, ferr, ag, custo, ctx) in enumerate(SESSOES):
        (DEMO / "sessions" / f"{1000 + i}.json").write_text(json.dumps({
            "pid": 1000 + i, "sessionId": sid, "cwd": f"/home/demo/{pasta}", "kind": "interactive",
            "entrypoint": "claude-vscode", "name": apelido, "status": status, "demo_idade_s": idade,
            "waitingFor": "Bash: python carregar.py" if status == "waiting" else None,
            "statusUpdatedAt": agora_ms - idade * 1000}, ensure_ascii=False), encoding="utf-8")
        proj = DEMO / "projects" / f"-home-demo-{pasta}"
        proj.mkdir(parents=True, exist_ok=True)
        linhas = [
            {"type": "ai-title", "aiTitle": titulo},
            {"type": "user", "message": {"role": "user", "content": pedido}},
            {"type": "last-prompt", "lastPrompt": pedido},
        ]
        conteudo = [{"type": "text", "text": fala}]
        if ferr:
            conteudo.append({"type": "tool_use", "id": f"t{i}", "name": ferr[0], "input": ferr[1]})
        linhas.append({"type": "assistant", "message": {
            "role": "assistant", "model": "claude-opus-5-5", "content": conteudo,
            "stop_reason": "tool_use" if ferr else "end_turn",
            "usage": {"input_tokens": 1200, "cache_read_input_tokens": ctx - 1200, "cache_creation_input_tokens": 0}}})
        linhas.append({"type": "cost-state", "totalCostUSD": custo})
        if not ferr:
            linhas.append({"type": "system", "subtype": "stop_hook_summary"})
        (proj / f"{sid}.jsonl").write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in linhas) + "\n", encoding="utf-8")
        if ag:
            sub = proj / sid / "subagents"
            sub.mkdir(parents=True, exist_ok=True)
            (sub / "agent-a1.meta.json").write_text(json.dumps({"agentType": ag[0], "model": ag[1], "description": ag[2]}), encoding="utf-8")
            (sub / "agent-a1.jsonl").write_text("{}\n", encoding="utf-8")
    (DEMO / "PENDENCIAS.md").write_text("# Pendências\n\n- [ ] Aprovar o texto da página de preços\n- [x] Renovar o domínio\n"
                                        "- [ ] Responder o fornecedor B sobre o prazo\n", encoding="utf-8")
    print(f"demo gerada em {DEMO}")


if __name__ == "__main__":
    main()
