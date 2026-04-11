# Task {###}: {Short descriptive title}

## 0. Complexity Assessment
- Level: Low | Medium | High
- Justification:
  - Technical complexity:
  - Integration complexity:
  - Risk level:
  - Estimated effort:
- Complexity rubric alignment:
  - Low: single component, no persistence, minimal side effects
  - Medium: multiple components and/or persistence involved
  - High: cross-cutting concerns, filesystem + DB interaction, concurrency, or irreversible operations
- Recommended execution mode:
  - Low → fast iteration
  - Medium → standard implementation with tests
  - High → incremental implementation with validation checkpoints

---

## 1. Goal
Clear, single-sentence objective of this task.

---

## 2. Why this task exists now
Explain why this task is needed at this point and what dependency it satisfies.

---

## 3. Prerequisites
List required prior tasks, systems, or guarantees.

---

## 4. Scope
Precisely define what is included.

---

## 5. Out of Scope
Explicitly define what is excluded.

---

## 6. Observable Outcome
Describe what concrete, user-visible or system-visible result will exist after this task.
Examples:
- CLI output
- UI change
- Files created/modified
- Database state change

If no observable outcome exists, the task is invalid and must be merged with another task.

---

## 7. Files to Create
- {path/to/file}: {purpose}

---

## 8. Files to Modify
- {path/to/file}: {what changes and why}

---

## 9. Files to Delete
- {path/to/file}: {reason}

---

## 10. Classes to Implement or Modify
### {ClassName}
- Responsibility:
- Key methods (names only):
- Interactions:

---

## 11. Public Functions / Methods
### {function_name}
- Purpose:
- Parameters:
- Returns:
- Side effects:
- Errors:

---

## 12. Data Model / Schema Changes
- Database changes:
- File formats:
- In-memory structures:

---

## 13. UI / UX Changes
- Screens:
- Interactions:
- States and transitions:
- Error states:

---

## 14. State Transitions
Describe system state before and after this task.
- Before:
- After:
- Invariants (must always hold true):

---

## 15. Detailed Implementation Notes
Step-by-step plan.
- sequencing
- constraints
- edge handling

Do not include code.

---

## 16. Acceptance Criteria
1. {Measurable condition}
2. {Measurable condition}
3. {Measurable condition}

---

## 17. Test Plan

### 17.1 Unit Tests
- {Test name}: verification, inputs, expected outputs

### 17.2 Integration Tests
- {Test name}: components, scenario, expected behavior

### 17.3 Filesystem Tests
- {Test name}: setup, operations, expected results

### 17.4 Persistence Tests
- {Test name}: DB state validation

### 17.5 UI Tests (if applicable)
- {Test name}: user flow, expected UI state

### 17.6 Performance Smoke Tests
- {Test name}: basic limits and expectations

### Test Constraints
- Use real filesystem operations when applicable
- Use a real database (e.g., SQLite) for persistence tests
- Avoid mocks unless strictly necessary

---

## 18. Failure Handling & Rollback
Required if task modifies or deletes data.

- Failure scenarios:
- Partial failure handling:
- Rollback strategy:
- Idempotency considerations:

---

## 19. Risks and Edge Cases
- {Risk}: mitigation
- {Edge case}: handling

---

## 20. Dependencies Introduced
- External libraries:
- Internal modules:

---

## 21. Estimated Change Size
Approximate number of lines added/modified.

---

## 22. Definition of Done
- All acceptance criteria met
- All tests implemented and passing
- No orphaned or unused code
- Fully integrated with previous tasks
- Observable outcome verified
- No placeholder or incomplete logic

---

## 23. Anti-Patterns Check
Confirm none of the following exist:
- Placeholder implementations or TODOs instead of logic
- Dead or unused code
- One-line wrapper functions with no added value
- Premature abstractions not required by this task

---

## 24. Notes (Optional)
Any additional clarifications