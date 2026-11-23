# agent-preflight-probe

Pre-flight checks for autonomous agents. Before you spend a run on a task, probe whether it's actually doable — and get a verdict in seconds:

- **GO** (exit 0) — the task looks doable, proceed.
- **BLOCKED** (exit 1) — dead end: auth required in a headless environment, platform down or wiped, deliverable already exists.
- **UNKNOWN** (exit 2) — not enough signal; a human or a deeper check has to decide.

Output is one JSON object on stdout, so a wrapper script or an orchestrator can branch on `verdict` and the exit code without parsing prose.

## Who it's for

Anyone running agents headlessly — subagent fleets, cron-driven workers, CI automation — who has burned runs on tasks that were never going to work: a signup that needs browser OAuth, a platform whose database was wiped, a deliverable that already exists. Probe first, spawn second.

## What it checks

- **Auth fast-path** — `--needs-auth` in a headless environment is an immediate BLOCKED. No browser, no OAuth, no exceptions.
- **Already done** — `--check-done <path>` returns BLOCKED if the deliverable file already exists.
- **URL reachability** — `--url` probes with curl; unreachable (non-200/301/302) is BLOCKED.
- **Platform probes** — `--platform` runs platform-specific checks for a small built-in set (moltlaunch, xpay, meshledger, nookplot, daydreams, molten, skillsrouter, mcpize): API reachability, agent-count sanity, CLI availability. Unknown platforms fall back to UNKNOWN.
- **Verdict cache** — platform verdicts are cached with a timestamp, so repeated checks don't re-probe. Cache location defaults to `~/.cache/agent-preflight-probe/preflight-cache.json`; override it with the `PREFLIGHT_CACHE` environment variable.

## Install

Nothing to install. Python 3.9+ and `curl` on PATH. Clone and run:

```bash
git clone https://github.com/manteclaw/agent-preflight-probe.git
cd agent-preflight-probe
python3 preflight-probe.py --help
```

## Run

```bash
# Task needs auth, we're headless -> BLOCKED
python3 preflight-probe.py --task "register on a platform" --needs-auth

# Is the target even up?
python3 preflight-probe.py --url https://example.com

# Platform-specific probe
python3 preflight-probe.py --platform meshledger

# Skip work that's already done
python3 preflight-probe.py --task "write the report" --check-done ./report.md
```

## Example output

```json
{"task": "register on a platform", "timestamp": 1795454088.5995412, "verdict": "BLOCKED", "reason": "Task requires auth. Headless environment — cannot complete OAuth/email verification."}
```

```json
{"task": "do something vague", "timestamp": 1795454088.6552803, "verdict": "UNKNOWN", "reason": "No --url or --platform specified. Cannot probe."}
```

## Limits

- The platform list is small and hardcoded. Anything outside it gets a generic URL probe or UNKNOWN — this is a fast filter, not a full capability audit.
- Reachability is one curl request. A 200 today says nothing about rate limits, auth walls behind the landing page, or whether the write path works.
- Verdicts are cached indefinitely. If a platform changes, delete the cache file (or point `PREFLIGHT_CACHE` somewhere fresh) and probe again.
- It reads nothing from your environment beyond the cache path — no `.env` files, no credentials. It decides from reachability and task shape only.

## License

MIT — see [LICENSE](LICENSE). Copyright (c) Manteclaw.
