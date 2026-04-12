param(
    [string]$StartTask = "001"
)

$ErrorActionPreference = "Stop"

$TasksDir = "tasks"
$BaseSessionId = "ab39fae1-5b5b-4d4a-b307-dbf70e0cf5d6"

function Get-Model {
    param([string]$Level)
    if ($Level -eq "Low") { return "haiku" }
    if ($Level -eq "High") { return "opus" }
    return "sonnet"
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
    $TaskSessionId = [guid]::NewGuid().ToString()

    $Prompt = "Implement only tasks/$TaskId.md. Do not start other numbered task files unless this task explicitly requires it. When done: satisfy the task acceptance criteria and run its verification commands; fix any failures. Mark that roadmap line done in docs/todo.md. Create a git commit that includes all changes for this task (staged files only for this work). Use a message like: task $TaskId short summary. Do not skip the commit if there are changes. Reply with a short summary: task id, files touched, commands run, commit hash or message, and anything the next run should know."

    Write-Host ""
    Write-Host "=================================================="
    Write-Host "Running task: $TaskId | Level: $Level | Model: $Model"
    Write-Host "Session ID:   $TaskSessionId"
    Write-Host "=================================================="

    $done = $false
    while (-not $done) {
        claude --resume $BaseSessionId --fork-session --session-id $TaskSessionId --model $Model --allowedTools "Read,Write,Edit,Glob,Grep,Bash(git *),Bash(cd *),Bash(npm *)" --permission-mode auto -p $Prompt

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "Task $TaskId complete. Session: $TaskSessionId"
            $done = $true
        } else {
            Write-Host ""
            Write-Host "=================================================="
            Write-Host "  TASK $TaskId FAILED (exit code $LASTEXITCODE)"
            Write-Host "  To inspect this session:"
            Write-Host "    claude --resume $TaskSessionId"
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
                    $TaskSessionId = [guid]::NewGuid().ToString()
                    $validChoice = $true
                } elseif ($choice -eq "S" -or $choice -eq "s") {
                    Write-Host "Skipping task $TaskId."
                    $done = $true
                    $validChoice = $true
                } elseif ($choice -eq "Q" -or $choice -eq "q") {
                    Write-Host ""
                    Write-Host "Quitting. To resume from this task:"
                    Write-Host "  .\scripts\run_tasks_claude.ps1 -StartTask $TaskId"
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
