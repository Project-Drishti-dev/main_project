# AGENTS.md

## Repository Rules
- Build & Verification Command: Run `./scripts/check-all.ps1` (or the task's specific `Verify:` command).
- STRICT Git Prohibition: DO NOT run any `git` commands (`git commit`, `git add`, `git push`, `git checkout`, etc.). All changes MUST remain as uncommitted working directory edits.
- Scope: Edit local source files only for the active task. Do not touch or modify unrelated files or anything inside `lorebook/`.
- UI Design: Use vanilla HTML/CSS/JS with local `UX4G` components (`ux4g-web-components@2.1.0`). Always run the UX4G preflight (`ux4g-design`) before adding markup. Match existing page design and styling.
- Domain Context: Check `lorebook/` for domain details, `docs/DECISIONS.md` for architectural rules, and `HANDOVER.md` for session state.
- Security & Constraints: No authentication, login forms, or password fields. Never output image bytes, OCR text, or identity data into terminal stdout or logs.

## Code & File Anti-Bloat Rules
- **Docstring Hygiene**: Docstrings must describe ONLY function/module purpose, inputs, outputs, and invariants, they should be very consise and not beyond 5 lines, NEVER embed test harness outputs, mutant counts, design debates, or task post-mortems in docstrings or code comments. Put design rationale in `docs/DECISIONS.md`.
- **`tasks.md` Cleanliness**: A completed task (`- [x]`) receives **at most one indented verification line** (e.g., `— verified: tests pass, check-all.ps1 exits 0`). NEVER paste multi-paragraph notes, test execution traces, or logs under task checkboxes.
- **`HANDOVER.md` Pruning**: The **Last Completed Task** section must hold details for the **single most recent completed task only**. Overwrite details from older tasks—do not accumulate an ongoing log of historical tasks in `HANDOVER.md`.
- **Output Safety**: Keep terminal responses under 150 words per run. Apply file edits directly using tool commands rather than displaying long code blocks in chat. Focus ONLY on the single active task.

## Task Execution Protocol
1. Read `HANDOVER.md` for current session state, then read `tasks.md` to identify the first unchecked task (`- [ ]`).
2. Implement code changes ONLY for that single task.
3. Verify changes by executing the task's specific `Verify:` command or running `./scripts/check-all.ps1`.
4. If verification passes:
   - Change the task status in `tasks.md` from `- [ ]` to `- [x]` with a 1-line verification note.
   - Update `HANDOVER.md` following the Handover Protocol below.
   - Output a 1-line summary in chat.
5. If verification fails after up to 2 targeted fix attempts:
   - Mark task as `- [ ] [BLOCKED]` in `tasks.md`.
   - Record the blocker and error trace briefly in `HANDOVER.md`.
   - Stop execution cleanly.

## Handover Protocol
After completing or blocking a task, update `HANDOVER.md` in the root directory:
1. **Last Completed Task**: 1-line or concise bullet summary of *only* the most recent task completed.
2. **Current State & Key Decisions**: Tight, deduplicated bullet points of active system invariants.
3. **Known Issues / Blockers**: Brief failing test details or missing dependencies if blocked.
4. **Immediate Next Step**: The exact next task ID and title from `tasks.md`.