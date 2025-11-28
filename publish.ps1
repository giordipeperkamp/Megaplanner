Param(
    [string]$RepoOwner = "giordipeperkamp",
    [string]$RepoName  = "Megaplanner",
    [switch]$Private
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Always run from the project root
Set-Location -Path $PSScriptRoot

# 1) Ensure a sensible .gitignore exists (keeps persoonlijke data uit GitHub)
$gitIgnore = @"
.venv/
__pycache__/
*.pyc
*.pyo
*.pyd
*.log
.vscode/
.streamlit/
output/
data/custom/*.csv
data/custom/*.xlsx
data/custom/*.json

# Node / misc
node_modules/
dist/
build/
"@

if (-not (Test-Path ".gitignore")) {
    $gitIgnore | Out-File -Encoding utf8 ".gitignore"
}

# 2) Git init (if needed)
if (-not (Test-Path ".git")) {
    git init | Out-Null
}

# 3) Default branch
git branch -M main | Out-Null

# 4) Stage changes if there are any
$status = git status --porcelain
if ($status) {
    git add -A | Out-Null
    $msg = "update: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ssK')"
    git commit -m $msg | Out-Null
}

# 5) Remote origin
$remoteUrl = ""
try {
    $remoteUrl = git remote get-url origin 2>$null
} catch { }

if (-not $remoteUrl) {
    # Prefer GitHub CLI if available
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if ($gh) {
        # Try to create the repo (if it doesn't exist). If it exists, just set remote below.
        try {
            gh repo view "$RepoOwner/$RepoName" 2>$null 1>$null
        } catch {
            $vis = if ($Private) { "--private" } else { "--public" }
            gh repo create "$RepoOwner/$RepoName" $vis --source . --remote origin --push
            exit 0
        }
        git remote add origin "https://github.com/$RepoOwner/$RepoName.git" | Out-Null
    } else {
        # Fallback: user must already have created the repo on GitHub
        git remote add origin "https://github.com/$RepoOwner/$RepoName.git" | Out-Null
    }
}

# 6) Push
git push -u origin main

Write-Host ""
Write-Host "Done. Repo: https://github.com/$RepoOwner/$RepoName" -ForegroundColor Green
Write-Host "Volgende updates? Voer opnieuw publish.ps1 uit of gebruik publish.cmd." -ForegroundColor Green


