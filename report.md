# Eigen Bot Audit Report

**Date:** 2026-09-18  
**Scope:** Static review of the full repository, configuration, deployment files, command/error paths, persistence, tests, and language-resource data. No live Discord server, database migration, or external service was exercised.

## Executive Summary

The project has a broad feature set and its baseline checks currently pass (`ruff`, `pytest`, and the configured `mypy` run). The most important work is operational reliability rather than syntax: preserve SQLite data in Docker, isolate state by guild, fix the TTS queue model, make errors observable, and add meaningful tests.

The current working tree also contains uncommitted improvements to `bot.py` and `cogs/misc.py`. Those changes fix the reported unsupported-language failure and improve global command error messages; they were included in this review.

## Validation Performed

| Check | Result | Notes |
| --- | --- | --- |
| `ruff check .` | Pass | No configured lint violations. |
| `pytest -q` | Pass | 3 smoke tests only. |
| `mypy .` | Pass with notes | Untyped `cogs/counting.py` bodies are not checked. |
| Language-resource JSON | Valid | 134 configured languages. |

## Priority Findings

### Critical

1. **Bot data is not persisted by Docker Compose.**
   - Evidence: `docker-compose.yml` mounts only `./logs:/app/logs`, while runtime state is written to `/app/botdata.db` and files beneath `/app/data`.
   - Impact: recreating the bot container can erase tickets, tags, staff applications, AFK state, birthdays, starboard settings, CodeBuddy data, and other SQLite-backed state.
   - Fix: mount a dedicated persistent data volume, for example `./data:/app/data` plus `./botdata.db:/app/botdata.db`, or move every database to a single mounted `/app/data` directory. Add backup and restore procedures.

2. **The TTS queue is global instead of per guild/voice client.**
   - Evidence: `cogs/tts.py` stores one `Queue`, one `playing` flag, and one `leave_task` for the entire cog; `tts()` places plain text into that shared queue and starts `process_queue(vc)` for one voice client.
   - Impact: messages submitted in a second server can be spoken in the first server's voice channel, can be left queued indefinitely, and auto-leave tasks can cancel each other across guilds.
   - Fix: maintain a queue, worker task, and idle-disconnect task keyed by guild ID (or voice-client ID). Queue structured jobs containing guild, channel, requester, and text. Close/cancel all workers in `cog_unload`.

### High

3. **Chowkidar persistence is not multi-guild safe.**
   - Evidence: `cogs/chowkidar.py` loads one configuration using `SELECT ... LIMIT 1`; `watched_users` is a global set; `chowkidar_tracked` has `user_id` as its only primary key.
   - Impact: one guild's watchlog channel can be used in another guild, and tracking or untracking a member in one guild affects every guild.
   - Fix: key configuration and tracked users by `(guild_id, user_id)`, keep in-memory state per guild, and require guild-only execution for all relevant commands/events. Migrate existing rows explicitly.

4. **Operational errors are frequently hidden.**
   - Evidence: many cogs contain broad `except Exception` blocks that either use `pass` or only `print`; prominent examples are `cogs/counting.py`, `cogs/codebuddy_quiz.py`, `cogs/starboard.py`, and `cogs/suggestions.py`.
   - Impact: users receive vague failures, while maintainers lose the traceback and correlation needed to diagnose production incidents. Silent state-update failures can also leave features inconsistent.
   - Fix: define a shared error-reporting helper using module loggers and `logger.exception`; catch only expected Discord/database exceptions where recovery is possible. Add a user-safe error code and log the correlation ID rather than exposing raw exceptions.

5. **Some commands expose internal exception text to users.**
   - Evidence: the bug-report, feature-request, feedback, timestamp, edit, and react paths in `cogs/misc.py` interpolate `e` or `e!s` into Discord responses.
   - Impact: Discord/API/database details can be disclosed and users see technical messages instead of recovery guidance.
   - Fix: log the exception server-side and return a generic, actionable message such as “I could not submit that right now; please try again later.” Keep raw details in logs only.

6. **The Docker stack has insecure and unused infrastructure.**
   - Evidence: `docker-compose.yml` uses the literal PostgreSQL password `password` and publishes PostgreSQL and Redis ports to the host. The application code does not use PostgreSQL, Redis, `asyncpg`, SQLAlchemy, Top.gg, or the configured Redis URL.
   - Impact: unnecessary attack surface, misleading deployment requirements, and credentials unsafe for any non-local environment.
   - Fix: remove unused services/dependencies or implement them intentionally. If retained, source credentials from secrets/environment variables and do not publish database/cache ports unless required.

7. **Hard-coded Discord IDs prevent safe reuse and testing.**
   - Evidence: staff-role/channel IDs, support/feedback channels, TODO targets, and staff-application defaults are embedded in `cogs/staff_guide.py`, `cogs/staff_applications.py`, and `cogs/misc.py`.
   - Impact: a deployment to another guild can post to the wrong server, fail silently, or make a feature unusable. It also makes tests environment-dependent.
   - Fix: move IDs to validated configuration or per-guild database settings, add setup commands, and fail with a clear “not configured” message.

### Medium

8. **SQLite access is fragmented and mixes synchronous with asynchronous I/O.**
   - Evidence: the project writes to `botdata.db`, `data/tags.db`, `data/starboard.db`, `data/staff_applications.db`, `data/afk.db`, and `data/birthdays.db`. `cogs/tickets.py` and `cogs/tts.py` use synchronous `sqlite3` in an async bot while other paths use `aiosqlite`.
   - Impact: synchronous database calls can block the event loop; multiple uncoordinated databases complicate backups, migrations, locking, and recovery.
   - Fix: standardize on `aiosqlite`, use a consistent data directory and connection settings, enable WAL where appropriate, define schema migrations, and centralize database lifecycle/backup logic.

9. **Resource metadata is substantially incomplete.**
   - Evidence: of 134 language entries, 126 have no CodeVerse Hub URL, 126 have no related Discord channels, and 126 have no extra resources. Beginner-resource arrays are present for all entries.
   - Impact: most `/resources` results are technically valid but do not deliver the full experience promised by the embed and usage description.
   - Fix: add a metadata-completeness check to CI, expose a paginated `/resources list` or autocomplete interface, and either fill the missing fields or label them as intentionally unavailable.

10. **The language-resource listing previously exceeded Discord embed limits.**
    - Evidence: 134 language names were joined into a single embed field, which exceeds Discord’s 1,024-character field-value limit.
    - Status: fixed in the current uncommitted `cogs/misc.py` changes by truncating the displayed list and returning the intended unsupported-language response.
    - Follow-up: provide a paginated listing/search command so truncation does not hide valid languages.

11. **Global error handling cannot cover commands that catch their own errors.**
    - Evidence: many command handlers catch exceptions locally and send “An error occurred...” messages, so the improved central handlers in the pending `bot.py` changes are bypassed.
    - Impact: error-message quality is inconsistent across features.
    - Fix: migrate local handlers to the shared error utility, preserving only feature-specific expected-error branches.

12. **Startup continues after important initialization/loading failures.**
    - Evidence: `bot.py` logs but continues if CodeBuddy database initialization or a cog load fails.
    - Impact: the bot can appear online with missing commands or partially initialized storage; users see unknown commands or later failures.
    - Fix: distinguish optional from required cogs. Fail startup for required dependencies, emit a startup health summary, and expose an owner-only health command that identifies disabled cogs.

13. **Command synchronization runs on every startup.**
    - Evidence: `bot.py` calls `tree.sync()` (and clear/copy/sync for configured guilds) during every `setup_hook` run.
    - Impact: unnecessary API work and increased risk of rate-limit or deployment issues as the bot grows.
    - Fix: use an explicit owner-only sync/deploy command or a deployment flag. Keep per-guild development sync separate from production global sync.

14. **The default Discord token is a non-empty placeholder.**
    - Evidence: `utils/config.py` defaults `discord_token` to `demo_token`, while startup only checks whether the value is truthy.
    - Impact: a misconfigured deployment tries to authenticate with a known-invalid token instead of failing immediately with an actionable configuration error.
    - Fix: require `DISCORD_TOKEN` with no default, or explicitly reject placeholder values during configuration validation.

15. **Staff-application persistence code contains a no-op interaction listener and large abandoned design comments.**
    - Evidence: `StaffApplications.on_interaction()` matches review button IDs and then executes `pass`; `cog_load()` contains extensive unresolved design notes.
    - Impact: it is unclear which persistence mechanism is authoritative, increasing the risk of broken application review buttons after restarts.
    - Fix: keep the existing `register_persistent_views()` approach if it is sufficient, test restart recovery, delete the no-op listener/comments, or replace it with a tested dynamic-item implementation.

16. **Several features are incomplete or misleading to users.**
    - Evidence: `?support` replies “Coming Soon!”, the modmail cog is commented out in `bot.py`, and configuration includes unused Top.gg/Redis fields.
    - Impact: advertised or discoverable functionality has no usable outcome.
    - Fix: implement, hide, or remove incomplete commands and configuration. Track deferred features in issues rather than shipping placeholders.

17. **The command surface is broad but not consistently available through both interfaces.**
    - Evidence: the repository contains 116 command decorators: 59 hybrid, 40 prefix-only, and 20 slash-only. Some matching commands duplicate implementations instead of sharing a service layer.
    - Impact: behavior, permissions, validation, help text, and errors can diverge by invocation style.
    - Fix: inventory commands in CI, decide which must be hybrid, and move business logic into shared methods that receive a normalized response adapter.

### Low

18. **Test coverage is insufficient for a stateful Discord bot.**
    - Evidence: `tests/test_smoke.py` contains three utility tests only; there are no tests for command validation, permissions, database migrations, persistence/restart behavior, pagination, or error handling.
    - Fix: add focused async tests using temporary SQLite databases and mocked Discord contexts/interactions. Prioritize the findings above before adding end-to-end tests.

19. **Configured mypy does not validate significant untyped code.**
    - Evidence: mypy reports that bodies of untyped functions in `cogs/counting.py` are skipped.
    - Fix: incrementally add annotations to database and command boundaries, then enable `check_untyped_defs` for core modules.

20. **Blocking network work should remain isolated from the event loop.**
    - Evidence: `cogs/fun.py` uses `urllib.request.urlopen` with a 20-second timeout for template downloads. It is currently called through `asyncio.to_thread`, which is good, but future callers must not bypass that wrapper.
    - Fix: retain the thread boundary or migrate to a shared async HTTP client with timeouts, size limits, retries, and caching.

21. **Documentation and dependency intent need reconciliation.**
    - Evidence: requirements include `asyncpg`, SQLAlchemy, Black, and Flake8 although the running code uses SQLite/`aiosqlite` and configured linting is Ruff; Compose starts PostgreSQL/Redis that the bot does not consume.
    - Fix: remove inactive dependencies/services, pin production dependencies using a lock file or compatible upper bounds, and document the supported deployment architecture.

## Recommended Implementation Order

1. Add persistent Docker volumes and a tested backup/restore plan for all SQLite files.
2. Refactor TTS into per-guild queue workers and add concurrency/restart tests.
3. Fix Chowkidar schema/state to be guild-scoped and migrate existing data.
4. Introduce shared logging/error-response utilities; remove silent broad exception handlers and raw exception messages sent to users.
5. Centralize configuration, remove hard-coded IDs, and require a real Discord token.
6. Consolidate database access and introduce migrations/WAL/locking policy.
7. Complete or hide placeholders; add resource discovery and metadata validation.
8. Add command-level test coverage and a CI workflow running Ruff, mypy, and pytest.

## Feature Opportunities

- **Health dashboard:** owner-only command showing loaded cogs, database health, configured channels, active worker counts, and last error IDs.
- **Resource browser:** autocomplete plus paginated category/list views, “random language,” favourites, and user-submitted resource links subject to staff review.
- **Ticket analytics:** resolution time, category volume, reopen rate, staff workload, and CSV export with permission controls.
- **Scheduled backups:** encrypted SQLite snapshots, retention policy, restore verification, and an owner alert on failure.
- **Per-guild settings UI:** configure support channels, roles, starboard, staff application review channel, TTS defaults, and feature toggles without source edits.
- **Error feedback flow:** every safe user error includes a short code; admins can retrieve the matching logged traceback.
- **Command discovery:** a generated help index that shows prefix/slash availability, aliases, permissions, cooldowns, and examples.

## Suggested Test Matrix

| Area | Minimum automated cases |
| --- | --- |
| Configuration | Missing/placeholder token, malformed guild IDs, missing required IDs. |
| Resources | Unknown language, aliases, 134-item list limits, malformed JSON, pagination. |
| TTS | Two guilds queue simultaneously, disconnect/reconnect, worker cancellation, text limits. |
| Chowkidar | Same user tracked in two guilds, independent channels, guild-only checks. |
| Database | Fresh schema, migration from existing data, concurrent writes, backup/restore. |
| Errors | Prefix and slash missing input, invalid member/channel, permission denied, Discord forbidden/rate-limit behavior. |
| Persistent views | Ticket and staff-review buttons work after process restart. |

## Notes

- This report does not claim a live integration test; Discord permissions, external URLs, and deployed database contents still need verification in a staging guild.
- No production code was changed during this audit beyond the pre-existing uncommitted error-handling work. This report itself is the only new audit artifact.
