<!-- ai-generated: 80% - Claude drafted, reviewed by me -->
# svcdesk - notes for coding agents

- The contract is API.md (Lab package) and `specs/001-svcdesk/spec.md`; the decisions are in `DECISIONS.md`
  (C1 wallclock, C2 immutable, C3 matrix). Do not change a decision without updating `DECISIONS.md`.
- Code lives in `src/svcdesk/`, own tests in `src/tests/` (runner: `python -m tests.run`).
- Never add bind mounts to `docker-compose.yml`, never fetch anything at run time, keep the `ai-generated:`
  header on every file under `src/` and `specs/`.
- Tags `lab1/v*` never move; git history and receipts are not an agent's business.
