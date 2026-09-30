# AGENTS.md

## Repository Rules
- Build & Verification Command: Run `./scripts/check-all.ps1` (or the task's specific `Verify:` command).
- STRICT Git Prohibition: DO NOT run any `git` commands (`git commit`, `git add`, `git push`, `git checkout`, etc.). All changes MUST remain as uncommitted working directory edits.
- Scope: Edit local source files only for the active task. Do not touch or modify unrelated files or anything inside `lorebook/`.
- UI Design: Use vanilla HTML/CSS/JS with local `UX4G` components (`ux4g-web-components@2.1.0`). Always run the UX4G preflight (`ux4g-design`) before adding markup. Match existing page design and styling.
- Domain Context: Check `lorebook/` for domain details, `docs/DECISIONS.md` for architectural rules, and `HANDOVER.md` for session state.
- Security & Constraints: No authentication, login forms, or password fields. Never output image bytes, OCR text, or identity data into terminal stdout or logs.

## Output Constraints & Token Safety
- Be concise. Do not write lengthy code explanations or commentary in chat.
- Apply file edits directly using tool commands rather than displaying long code blocks in terminal output.
- Keep terminal responses under 150 words per task run.
- Focus ONLY on the single specified task. Do not refactor adjacent modules.

## Task Execution Protocol
1. Read `HANDOVER.md` for current session state, then read `tasks.md` to identify the first unchecked task (`- [ ]`).
2. Implement code changes ONLY for that single task.
3. Verify changes by executing the task's specific `Verify:` command or running `./scripts/check-all.ps1`.
4. If verification passes:
   - Change the task status in `tasks.md` from `- [ ]` to `- [x]`.
   - Update `HANDOVER.md` following the Handover Protocol below.
   - Output a 1-line summary of changes.
5. If verification fails after up to 2 targeted fix attempts:
   - Mark task as `- [ ] [BLOCKED]` in `tasks.md`.
   - Record the blocker and error trace in `HANDOVER.md`.
   - Stop execution cleanly.

## Handover Protocol
After completing or blocking a task, update `HANDOVER.md` in the root directory:
1. **Last Completed Task**: 1-line summary of what was completed and verified.
2. **Current State & Key Decisions**: Relevant component state or design decisions made.
3. **Known Issues / Blockers**: Failing tests or missing dependencies if blocked.
4. **Immediate Next Step**: The exact next task ID from `tasks.md`.