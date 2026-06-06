cd "C:\Users\bruno\Documents\PROJETOS\leads-portal"

# Inicializa git se ainda nao existir
if (-not (Test-Path ".git")) {
    git init
    git branch -m main
    Write-Host "Git inicializado." -ForegroundColor Green
}

# Configura o remote (so na primeira vez)
$remotes = git remote 2>$null
if (-not $remotes) {
    git remote add origin https://github.com/datamacedo/leads-portal.git
    Write-Host "Remote adicionado." -ForegroundColor Green
}

git add .
git status

$msg = Read-Host "Mensagem do commit (Enter para usar 'update')"
if ([string]::IsNullOrWhiteSpace($msg)) { $msg = "update" }

git commit -m $msg
git push -u origin main

Write-Host ""
Write-Host "Push concluido!" -ForegroundColor Cyan
