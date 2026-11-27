# Hook PreToolUse para mcp__claude-in-chrome__select_browser: impede o Claude de usar o perfil de navegador errado.
# Regras em ~/.claude/navegadores.json (modelo em exemplos/navegadores.example.json):
#   "proibidos": perfis que nunca podem ser usados (ex.: o navegador pessoal);
#   "so_nas_pastas": perfil -> pastas onde ele é permitido (ex.: a conta de um cliente só na pasta do cliente);
#   "padrao": o perfil sugerido na mensagem de bloqueio.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$entrada = [Console]::In.ReadToEnd()
try { $dados = $entrada | ConvertFrom-Json } catch { exit 0 }
$cfgArq = Join-Path $env:USERPROFILE '.claude\navegadores.json'
if (-not (Test-Path $cfgArq)) { exit 0 }
$cfg = Get-Content -Raw -Encoding UTF8 $cfgArq | ConvertFrom-Json
$id = "$($dados.tool_input.deviceId)"
$partes = "$($dados.cwd)".Replace('/', '\').Split('\')
$sugestao = "Use o perfil padrao ($($cfg.padrao.nome), $($cfg.padrao.id))."
$motivo = $null
foreach ($p in $cfg.proibidos) { if ($id -eq $p.id) { $motivo = "O perfil '$($p.nome)' nao pode ser usado. $sugestao" } }
foreach ($regra in $cfg.so_nas_pastas) {
    if ($id -eq $regra.id) {
        $permitido = $false
        foreach ($pasta in $regra.pastas) { if ($partes -icontains $pasta) { $permitido = $true } }
        if (-not $permitido) { $motivo = "O perfil '$($regra.nome)' so e usado nas pastas: $($regra.pastas -join ', '). $sugestao" }
    }
}
if ($motivo) {
    @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $motivo } } | ConvertTo-Json -Compress -Depth 4
}
exit 0
