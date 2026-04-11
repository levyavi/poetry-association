# scripts/run_tasks.ps1

$ErrorActionPreference = "Stop"

$TasksDir = "tasks"
$BaseSession = "base-context"

function Get-Model {
    param([string]$Level)
    switch ($Level) {
        "Low"    { return "haiku" }
        "Medium" { return "sonnet" }
        "High"   { return "opus" }
        default  { return "sonnet" }
    }
}

# Find all task files in order
$TaskFiles = Get-ChildItem -Path $TasksDir -Filter "*.md" | 
    Where-Object { $_.Name -match '^\d+\.md$' } | 
    Sort-Object Name

if ($TaskFiles.Count -eq 0) {
    Write-Error "No task files found in $TasksDir/"
    exit 1
}

foreach ($TaskFile in $TaskFiles) {
    $TaskId = $TaskFile.BaseName  # e.g. "001"

    # Find the Level line anywhere in the file
    $LevelLine = Get-Content $TaskFile.FullName | Select-String -Pattern "Level:" | Select-Object -First 1
    $Level = $LevelLine -replace '.*Level:\s*', '' -replace '\s', ''

    $Model = Get-Model $Level

    $Prompt = "Implement only tasks/${TaskId}.md. Do not start other numbered task files unless this task explicitly requires it.
When done: satisfy the task's acceptance criteria and run its verification commands (e.g. npm test, npm run build); fix any failures.
Mark that roadmap line done in docs/todo.md (``- [x] **${TaskId}**``).
Create a git commit that includes all changes for this task (staged files only for this work). Use a message like: ``task ${TaskId}: <short summary>``. Do not skip the commit if there are changes.
Reply with a short summary: task id, files touched, commands run, commit hash or message, and anything the next run should know."

    Write-Host "=================================================="
    Write-Host "Running task: $TaskId | Level: $Level | Model: $Model"
    Write-Host "=================================================="

    claude --resume $BaseSession --fork-session `
        --model $Model `
        --allowedTools "Read,Write,Edit,Glob,Grep,Bash(git *),Bash(cd *),Bash(npm *)" `
        --permission-mode auto `
        -p $Prompt

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Error "ERROR: Task $TaskId failed (Claude exited with code $LASTEXITCODE)."
        Write-Host "Fix the issue and re-run from task $TaskId."
        exit 1
    }

    Write-Host ""
    Write-Host "Task $TaskId complete."
    Write-Host ""
}

Write-Host "All tasks complete."