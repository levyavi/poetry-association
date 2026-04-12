param(
    [string]$StartTask = "001"
)

$ErrorActionPreference = "Stop"

$TasksDir = "tasks"

function Get-Model {
    param([string]$Level)
    if ($Level -eq "Low") { return "gpt-5.4-mini" }
    return "gpt-5.4"
}

$TaskFiles = Get-ChildItem -Path $TasksDir -Filter "*.md" |
    Where-Object { $_.Name -match '^\d+\.md$' } |
    Sort-Object Name

if ($TaskFiles.Count -eq 0) {
    Write-Error "No task files found in $TasksDir/"
    exit 1
}

$StartTaskNormalized = $StartTask.PadLeft(3, '0')

foreach ($TaskFile in $TaskFiles) {
    $TaskId = $TaskFile.BaseName

    if ([string]::Compare($TaskId, $StartTaskNormalized) -lt 0) {
        Write-Host "Skipping task $TaskId"
        continue
    }

    $LevelLine = Get-Content $TaskFile.FullName | Select-String -Pattern "Level:" | Select-Object -First 1
    $Level = $LevelLine -replace '.*Level:\s*', '' -replace '\s', ''
    $Model = Get-Model $Level

    $Prompt = @"
You are working in the project repo root.
Follow AGENTS.md, including the lean-ctx requirement for reads, searches, and shell commands.
Read docs/poetry_association_tool_design_document.md, docs/todo.md, and tasks/$TaskId.md before making changes.
Implement only tasks/$TaskId.md. Do not start other numbered task files unless this task explicitly requires it.
When done:
- satisfy the task acceptance criteria
- run the task's verification commands and fix failures
- mark that roadmap line done in docs/todo.md
- create a git commit that includes all changes for this task, using a message like: task $TaskId short summary
- reply with a short summary: task id, files touched, commands run, commit hash or message, and anything the next run should know
"@

    Write-Host ""
    Write-Host "=================================================="
    Write-Host "Running task: $TaskId | Level: $Level | Model: $Model"
    Write-Host "=================================================="

    $done = $false
    while (-not $done) {
        codex exec --full-auto --sandbox workspace-write -m $Model $Prompt

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "Task $TaskId complete."
            $done = $true
        } else {
            Write-Host ""
            Write-Host "=================================================="
            Write-Host "  TASK $TaskId FAILED (exit code $LASTEXITCODE)"
            Write-Host "=================================================="
            Write-Host ""

            $validChoice = $false
            while (-not $validChoice) {
                Write-Host "What would you like to do?"
                Write-Host "  [R] Retry this task"
                Write-Host "  [S] Skip this task and continue to next"
                Write-Host "  [Q] Quit"
                Write-Host ""
                $choice = Read-Host "Enter choice"

                if ($choice -eq "R" -or $choice -eq "r") {
                    Write-Host "Retrying task $TaskId..."
                    $validChoice = $true
                } elseif ($choice -eq "S" -or $choice -eq "s") {
                    Write-Host "Skipping task $TaskId."
                    $done = $true
                    $validChoice = $true
                } elseif ($choice -eq "Q" -or $choice -eq "q") {
                    Write-Host ""
                    Write-Host "Quitting. To resume from this task:"
                    Write-Host "  .\scripts\run_tasks_codex.ps1 -StartTask $TaskId"
                    exit 1
                } else {
                    Write-Host "Invalid choice. Please enter R, S, or Q."
                }
            }
        }
    }
}

Write-Host ""
Write-Host "All tasks complete."
