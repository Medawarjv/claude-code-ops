# Hook SessionStart: avisa contas que vencem hoje ou amanhã e as vencidas sem pagamento registrado.
# Fonte: ~/.claude/contas-recorrentes.md (modelo em exemplos/contas-recorrentes.example.md).
# Teste manual: powershell -File contas_do_dia.ps1 -Hoje 2026-12-10
param([string]$Hoje = (Get-Date -Format 'yyyy-MM-dd'))
# Em rodada automática (claude -p de um agendador) o aviso não tem leitor e só gasta contexto
if ($env:CLAUDE_CODE_ENTRYPOINT -eq 'sdk-cli') { exit 0 }
$arquivo = Join-Path $PSScriptRoot '..\contas-recorrentes.md'
if (-not (Test-Path $arquivo)) { exit 0 }
$hojeD = [datetime]::ParseExact($Hoje, 'yyyy-MM-dd', $null)
$contas = @(); $pagos = @{}; $secao = ''
foreach ($l in Get-Content -Path $arquivo -Encoding UTF8) {
    if ($l -match '^##\s+(.+)$') { $secao = $Matches[1].Trim(); continue }
    if ($secao -eq 'Contas' -and $l -match '^\|\s*([^|]+?)\s*\|\s*(\d{1,2})\s*\|\s*(\d{4}-\d{2})\s*\|\s*(\d{4}-\d{2}|-)\s*\|') {
        $contas += [pscustomobject]@{ Nome = $Matches[1]; Dia = [int]$Matches[2]; De = $Matches[3]; Ate = $Matches[4] }
    }
    if ($secao -eq 'Pagos' -and $l -match '^\|\s*(\d{4}-\d{2})\s*\|\s*([^|]+?)\s*\|') { $pagos["$($Matches[1])|$($Matches[2])"] = $true }
}
$avisos = @()
foreach ($c in $contas) {
    foreach ($m in @($hojeD.AddMonths(-1), $hojeD, $hojeD.AddMonths(1))) {
        $mes = $m.ToString('yyyy-MM')
        if ($mes -lt $c.De) { continue }
        if ($c.Ate -ne '-' -and $mes -gt $c.Ate) { continue }
        $dia = [Math]::Min($c.Dia, [datetime]::DaysInMonth($m.Year, $m.Month))
        $venc = Get-Date -Year $m.Year -Month $m.Month -Day $dia -Hour 0 -Minute 0 -Second 0 -Millisecond 0
        if ($pagos.ContainsKey("$mes|$($c.Nome)")) { continue }
        $diff = ($venc - $hojeD).Days
        $data = $venc.ToString('dd/MM')
        if ($diff -lt 0) { $avisos += "- ATRASADA: $($c.Nome), venceu $data (ha $(-$diff) dia(s)), sem confirmação de pagamento" }
        elseif ($diff -eq 0) { $avisos += "- VENCE HOJE: $($c.Nome) ($data)" }
        elseif ($diff -eq 1) { $avisos += "- vence amanhã: $($c.Nome) ($data)" }
    }
}
if ($avisos.Count -eq 0) { exit 0 }
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output "Contas em $Hoje (de ~/.claude/contas-recorrentes.md). Avisar no início da sessão. Quando o usuário confirmar o pagamento, registrar em 'Pagos' (mês do vencimento + nome exato da conta):"
$avisos | ForEach-Object { Write-Output $_ }
