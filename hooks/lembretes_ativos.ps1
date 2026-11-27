# Hook SessionStart: imprime os lembretes de ~/.claude/lembretes.md cuja janela de datas inclui hoje.
# Formato da tabela: | início (AAAA-MM-DD) | fim (AAAA-MM-DD) | texto |  (modelo em exemplos/lembretes.example.md)
# Teste manual: powershell -File lembretes_ativos.ps1 -Hoje 2026-12-07
param([string]$Hoje = (Get-Date -Format 'yyyy-MM-dd'))
# Em rodada automática (claude -p de um agendador) o lembrete não tem leitor e só gasta contexto
if ($env:CLAUDE_CODE_ENTRYPOINT -eq 'sdk-cli') { exit 0 }
$arquivo = Join-Path $PSScriptRoot '..\lembretes.md'
if (-not (Test-Path $arquivo)) { exit 0 }
$hojeD = [datetime]::ParseExact($Hoje, 'yyyy-MM-dd', $null)
$ativos = @()
foreach ($linha in Get-Content -Path $arquivo -Encoding UTF8) {
    if ($linha -match '^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.+?)\s*\|\s*$') {
        $ini = [datetime]::ParseExact($Matches[1], 'yyyy-MM-dd', $null)
        $fim = [datetime]::ParseExact($Matches[2], 'yyyy-MM-dd', $null)
        $texto = $Matches[3]; $j1 = $Matches[1]; $j2 = $Matches[2]
        # Prefixo opcional [dias:ter,qui] limita o lembrete a esses dias da semana
        $diaOk = $true
        if ($texto -match '^\[dias:([a-z,]+)\]\s*(.*)$') {
            $mapa = @{ dom='Sunday'; seg='Monday'; ter='Tuesday'; qua='Wednesday'; qui='Thursday'; sex='Friday'; sab='Saturday' }
            $dias = $Matches[1].Split(',') | ForEach-Object { $mapa[$_] }
            $diaOk = $dias -contains $hojeD.DayOfWeek.ToString()
            $texto = $Matches[2]
        }
        if ($diaOk -and $hojeD -ge $ini -and $hojeD -le $fim) { $ativos += "- $texto (janela $j1 a $j2)" }
    }
}
if ($ativos.Count -eq 0) { exit 0 }
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output "Lembretes ativos em $Hoje (de ~/.claude/lembretes.md; mencionar no início da sessão e retirar a linha do arquivo quando o usuário disser que resolveu):"
$ativos | ForEach-Object { Write-Output $_ }
