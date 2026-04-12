# run_tasks.ps1

Automates running a sequence of implementation tasks using Claude Code. Each task is executed in its own isolated Claude session, forked from a shared base context that contains the project spec and plan.

---

## How It Works

1. Reads all numbered task files from the `tasks/` folder (`001.md`, `002.md`, etc.)
2. For each task, reads the complexity level and picks the appropriate Claude model
3. Forks the base context session so every task starts clean with the spec and plan — but no pollution from previous tasks
4. Runs Claude non-interactively with a standard prompt that implements the task, runs verification, commits the result, and reports back
5. Stops immediately if any task fails

### Model Selection

| Complexity | Model  |
|------------|--------|
| Low        | Haiku  |
| Medium     | Sonnet |
| High       | Opus   |

---

## Before Running

### 1. Set up the base context session in Claude Code

Open a terminal in your project root and start Claude Code:

```
claude
```

Load your spec and plan:

```
Read spec.md and plan.md thoroughly.
```

Once done, compact the context to create a clean, optimized snapshot:

```
/compact Preserve the full project spec, the complete plan, all task definitions, key architectural decisions, and any constraints or requirements. Discard everything else.
```

After compacting, skim the summary to confirm the spec and plan came through correctly.

Then name the session:

```
/rename base-context
```

You can now close this terminal. The session is saved to disk.

### 2. Get the base session ID

Open a new terminal in your project root and run:

```
claude --resume
```

This opens an interactive session picker. Find the `base-context` session, and note its session ID (a UUID like `ab39fae1-5b5b-4d4a-b307-dbf70e0cf5d6`).

### 3. Update the script

Open `scripts/run_tasks.ps1` and paste the session ID into this line near the top:

```powershell
$BaseSessionId = "your-session-id-here"
```

### 4. Check your task files

Each task file in `tasks/` must have a complexity line somewhere in the file:

```
- Level: Low
- Level: Medium
- Level: High
```

The script scans for the first `Level:` match in each file.

---

## Usage

From your project root:

```powershell
# Run all tasks from the beginning
.\scripts\run_tasks.ps1

# Resume from a specific task (e.g. after a failure)
.\scripts\run_tasks.ps1 -StartTask 5

# Both formats work
.\scripts\run_tasks.ps1 -StartTask 005
```

If you have never run PowerShell scripts before, you may need to run this once first:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## What the Script Does Per Task

For each task file the script will:

1. Skip tasks before the `-StartTask` value
2. Read the complexity level and select the model
3. Fork the base context into a fresh isolated session
4. Run Claude with this prompt:
   - Implement the task
   - Run verification commands (`npm test`, `npm run build`, etc.) and fix failures
   - Mark the task done in `docs/todo.md`
   - Create a git commit with all changes
   - Reply with a summary of what was done
5. Stop and report the failed task ID if Claude exits with an error

---

## If a Task Fails

The script will print:

```
ERROR: Task 005 failed (Claude exited with code 1).
Fix the issue and re-run from this task with:
  .\scripts\run_tasks.ps1 -StartTask 005
```

Fix whatever caused the failure (manually or by resuming the task's session), then re-run from that task using the command shown.

Each task's session ID is printed during the run, so you can resume any specific task session for debugging:

```
claude --resume <session-id>
```

---

## File Structure

```
project/
├── tasks/
│   ├── 001.md
│   ├── 002.md
│   └── ...
├── docs/
│   ├── todo.md
│   ├── spec.md
│   └── plan.md
├── scripts/
└   └── run_tasks.ps1

```