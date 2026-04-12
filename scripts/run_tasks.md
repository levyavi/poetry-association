# Task Runner Scripts

These scripts automate the numbered files in `tasks/` for either Claude or Codex.

- `scripts/run_tasks_claude.ps1`: Claude-specific runner that forks each task from a saved Claude base session.
- `scripts/run_tasks_codex.ps1`: Codex-specific runner that executes each task with `codex exec`.

Both scripts:

1. Read numbered task files from `tasks/` (`001.md`, `002.md`, etc.)
2. Read the task complexity and choose a model
3. Run each task in isolation
4. Ask the agent to implement the task, run verification, mark `docs/todo.md`, commit the result, and print a short summary
5. Stop for retry / skip / quit decisions if a task fails

---

## Project Context

For this repo, the authoritative shared context is:

- `docs/poetry_association_tool_design_document.md`
- `docs/todo.md`
- `tasks/NNN.md`
- `AGENTS.md`

There is no `spec.md` / `plan.md` pair in this project. If you adapt these scripts to another repo, update the prompts and the Claude base-context instructions accordingly.

---

## Model Selection

### Claude

| Complexity | Model  |
|------------|--------|
| Low        | Haiku  |
| Medium     | Sonnet |
| High       | Opus   |

### Codex

| Complexity | Model        |
|------------|--------------|
| Low        | gpt-5.4-mini |
| Medium     | gpt-5.4      |
| High       | gpt-5.4      |

The Codex defaults above keep the script simple and conservative. If you want a different tradeoff, change `Get-Model` in `run_tasks_codex.ps1`.

---

## Before Running Claude

### 1. Create the Claude base context

Open a terminal in the project root and start Claude Code:

```powershell
claude
```

Load the shared project context:

```text
Read AGENTS.md, docs/poetry_association_tool_design_document.md, and docs/todo.md thoroughly. Understand how the numbered task files in tasks/ relate to the roadmap.
```

Compact the context so the saved session contains only the durable project context:

```text
/compact Preserve the full design document, the roadmap in docs/todo.md, the task-file workflow, project constraints from AGENTS.md, and any key architectural decisions. Discard everything else.
```

Then rename the session:

```text
/rename base-context
```

### 2. Get the Claude base session ID

In a new terminal:

```powershell
claude --resume
```

Find the `base-context` session and copy its session ID.

### 3. Update the Claude runner

Open `scripts/run_tasks_claude.ps1` and set:

```powershell
$BaseSessionId = "your-session-id-here"
```

### 4. Check the task files

Each task file in `tasks/` must contain one of:

```text
- Level: Low
- Level: Medium
- Level: High
```

The scripts use the first `Level:` match found in the file.

---

## Before Running Codex

Make sure the Codex CLI is installed and authenticated:

```powershell
codex --help
```

The Codex runner does not use a saved base session. Instead, each task run prompts Codex to read the shared project docs fresh before it starts work.

---

## Usage

From the project root:

```powershell
# Claude: run all tasks
.\scripts\run_tasks_claude.ps1

# Claude: resume from a specific task
.\scripts\run_tasks_claude.ps1 -StartTask 005

# Codex: run all tasks
.\scripts\run_tasks_codex.ps1

# Codex: resume from a specific task
.\scripts\run_tasks_codex.ps1 -StartTask 005
```

If PowerShell blocks script execution, run this once:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## What Each Script Does Per Task

### Claude runner

For each task:

1. Skips tasks before `-StartTask`
2. Selects a Claude model from the task's `Level:`
3. Forks the saved Claude base session into a fresh task session
4. Asks Claude to implement only that task, run verification, mark `docs/todo.md`, commit, and summarize
5. On failure, lets you retry, skip, or quit

### Codex runner

For each task:

1. Skips tasks before `-StartTask`
2. Selects a Codex model from the task's `Level:`
3. Runs `codex exec --full-auto --sandbox workspace-write`
4. Prompts Codex to read `AGENTS.md`, `docs/poetry_association_tool_design_document.md`, `docs/todo.md`, and the current task file before making changes
5. On failure, lets you retry, skip, or quit

The Codex runner is stateless across tasks by design. If a task fails, inspect the working tree and rerun from that task.

---

## Failure Recovery

### Claude

The script prints the task session ID for each run. You can resume a failed Claude task directly:

```powershell
claude --resume <session-id>
```

To rerun the task sequence from that task:

```powershell
.\scripts\run_tasks_claude.ps1 -StartTask 005
```

### Codex

Codex task runs in this script are one-shot executions. If a task fails:

1. Review the current working tree and terminal output
2. Fix anything manually if needed
3. Rerun from the failed task:

```powershell
.\scripts\run_tasks_codex.ps1 -StartTask 005
```

---

## Files

```text
project/
├── tasks/
│   ├── 001.md
│   ├── 002.md
│   └── ...
├── docs/
│   ├── poetry_association_tool_design_document.md
│   └── todo.md
├── scripts/
│   ├── run_tasks.md
│   ├── run_tasks_claude.ps1
│   └── run_tasks_codex.ps1
└── AGENTS.md
```
