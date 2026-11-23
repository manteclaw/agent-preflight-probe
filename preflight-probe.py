#!/usr/bin/env python3
"""
Preflight Probe — Quick dead-end detection before spawning subagents.
Checks if a task is actually doable without burning a slot.

Usage:
    python3 preflight-probe.py --task "register on MCPize"
    python3 preflight-probe.py --url https://mcpize.com --needs-auth
    python3 preflight-probe.py --platform moltlaunch --check-agents

Exit codes:
    0 = GO (task is doable)
    1 = BLOCKED (auth needed / platform dead / already done)
    2 = UNKNOWN (need more info)
"""
import argparse, json, sys, subprocess, time, os
from pathlib import Path

CACHE_FILE = Path(os.environ.get(
    "PREFLIGHT_CACHE",
    Path.home() / ".cache" / "agent-preflight-probe" / "preflight-cache.json",
))
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

def load_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def probe_url(url, timeout=10):
    """Quick curl probe to check if URL is reachable and what it returns."""
    try:
        r = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-m", str(timeout), url],
            capture_output=True, text=True, timeout=timeout+5
        )
        code = r.stdout.strip()
        return {"reachable": code in ("200", "301", "302"), "code": code}
    except Exception as e:
        return {"reachable": False, "error": str(e)}

def probe_platform(platform, cache):
    """Platform-specific probes."""
    results = {"platform": platform, "probes": []}

    if platform.lower() == "moltlaunch":
        # Check if platform has any agents (indicates data wipe)
        r = probe_url("https://moltlaunch.com/api/agents")
        results["probes"].append(r)
        if r.get("reachable"):
            # Try to get agent count
            try:
                rr = subprocess.run(
                    ["curl", "-s", "-m", "10", "https://moltlaunch.com/api/agents"],
                    capture_output=True, text=True, timeout=15
                )
                data = json.loads(rr.stdout)
                if data.get("total", -1) == 0:
                    results["verdict"] = "BLOCKED"
                    results["reason"] = "Platform database wiped. Zero agents registered."
                    return results
            except:
                pass

    elif platform.lower() == "xpay":
        r = probe_url("https://app.xpay.sh")
        results["probes"].append(r)
        if r.get("reachable"):
            results["verdict"] = "BLOCKED"
            results["reason"] = "Requires browser auth (Google/GitHub/email via Privy). Cannot complete headless."
            return results

    elif platform.lower() in ("daydreams", "molten", "skillsrouter", "mcpize"):
        results["verdict"] = "BLOCKED"
        results["reason"] = f"{platform} requires browser-based OAuth/email signup. Headless blocked."
        return results

    elif platform.lower() == "meshledger":
        r = probe_url("https://meshledger.com/api/v1/skills")
        results["probes"].append(r)
        if r.get("reachable"):
            results["verdict"] = "GO"
            results["reason"] = "API reachable. Can query tasks headlessly."
            return results
        else:
            results["verdict"] = "UNKNOWN"
            results["reason"] = "API not reachable. Check URL or network."
            return results

    elif platform.lower() == "nookplot":
        # Check nookplot CLI availability
        try:
            r = subprocess.run(["nookplot", "status"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                results["verdict"] = "GO"
                results["reason"] = "nookplot CLI works. Can poll bounties headlessly."
                return results
        except FileNotFoundError:
            results["verdict"] = "BLOCKED"
            results["reason"] = "nookplot CLI not installed."
            return results

    # Generic URL probe
    if "url" in results:
        r = results["url_probe"]
        if not r.get("reachable"):
            results["verdict"] = "BLOCKED"
            results["reason"] = f"URL unreachable (HTTP {r.get('code', 'unknown')})"
            return results

    results["verdict"] = "UNKNOWN"
    results["reason"] = "No specific probe matched. Manual check needed."
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", help="Describe the task briefly")
    parser.add_argument("--url", help="URL to probe")
    parser.add_argument("--platform", help="Platform name (moltlaunch, xpay, meshledger, nookplot, etc.)")
    parser.add_argument("--needs-auth", action="store_true", help="Task requires auth — immediate block if headless")
    parser.add_argument("--check-done", help="Check if file already exists (skip if yes)")
    args = parser.parse_args()

    cache = load_cache()
    result = {"task": args.task, "timestamp": time.time()}

    # Fast-path: already done?
    if args.check_done and Path(args.check_done).exists():
        result["verdict"] = "BLOCKED"
        result["reason"] = f"Deliverable already exists: {args.check_done}"
        print(json.dumps(result))
        sys.exit(1)

    # Fast-path: auth required + headless = block
    if args.needs_auth:
        result["verdict"] = "BLOCKED"
        result["reason"] = "Task requires auth. Headless environment — cannot complete OAuth/email verification."
        print(json.dumps(result))
        sys.exit(1)

    # URL probe
    if args.url:
        r = probe_url(args.url)
        result["url_probe"] = r
        if not r.get("reachable"):
            result["verdict"] = "BLOCKED"
            result["reason"] = f"URL unreachable (HTTP {r.get('code', 'unknown')})"
            print(json.dumps(result))
            sys.exit(1)

    # Platform probe
    if args.platform:
        pr = probe_platform(args.platform, cache)
        result.update(pr)
        # Update cache
        cache[args.platform] = {"last_check": time.time(), "verdict": pr["verdict"], "reason": pr["reason"]}
        save_cache(cache)
        print(json.dumps(result))
        sys.exit(0 if pr["verdict"] == "GO" else 1)

    result["verdict"] = "UNKNOWN"
    result["reason"] = "No --url or --platform specified. Cannot probe."
    print(json.dumps(result))
    sys.exit(2)

if __name__ == "__main__":
    main()
