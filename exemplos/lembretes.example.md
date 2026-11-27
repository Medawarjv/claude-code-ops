# Lembretes com janela de datas

O hook `lembretes_ativos.ps1` mostra no início da sessão só as linhas cuja janela inclui hoje.
O prefixo opcional `[dias:seg,qua]` limita o lembrete a esses dias da semana. Quando resolver, apague a linha.

| Início | Fim | Lembrete |
|---|---|---|
| 2026-12-01 | 2026-12-05 | Cancelar o teste grátis do serviço X antes da cobrança |
| 2026-12-01 | 2026-12-31 | [dias:seg] Revisar as métricas da semana |
