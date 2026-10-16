"""Local deployment helper. Uses Git Credential Manager; never prints tokens."""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


def request(path, method="GET", body=None):
    env = {**os.environ, "GCM_INTERACTIVE": "Never", "GIT_TERMINAL_PROMPT": "0"}
    credential = subprocess.run(
        ["git", "-c", "credential.interactive=false", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n", text=True, capture_output=True, env=env, timeout=20)
    if credential.returncode:
        raise RuntimeError("No stored GitHub credential")
    fields = dict(line.split("=", 1) for line in credential.stdout.splitlines() if "=" in line)
    req = urllib.request.Request("https://api.github.com/" + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + fields["password"],
                 "Accept": "application/vnd.github+json", "Content-Type": "application/json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "GameTechWeekly-Setup"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
        return json.loads(data) if data else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="Ash-final-light/EmailSender")
    parser.add_argument("command", choices=["status", "dispatch", "set-secret", "set-var", "run"])
    parser.add_argument("name", nargs="?")
    parser.add_argument("--mode", choices=["preview", "send", "collect", "preview-seeds", "preview-cached", "resume",
                                          "confirm-delivered", "release-delivery"], default="preview")
    parser.add_argument("--weekly-token-limit")
    args = parser.parse_args()
    root = "repos/" + args.repo
    if args.command == "status":
        repo = request(root)
        secrets = request(root + "/actions/secrets")
        workflows = request(root + "/actions/workflows")
        runs = request(root + "/actions/runs?per_page=6")
        print(json.dumps({"repository": repo["full_name"], "private": repo["private"],
            "secrets": [s["name"] for s in secrets.get("secrets", [])],
            "workflows": [{"name": w["name"], "state": w["state"]} for w in workflows.get("workflows", [])],
            "runs": [{"id": r["id"], "name": r["name"], "status": r["status"],
                      "conclusion": r["conclusion"], "url": r["html_url"]} for r in runs.get("workflow_runs", [])]},
            indent=2))
    elif args.command == "dispatch":
        inputs = {"mode": args.mode} if (args.name or "weekly.yml") in ("weekly.yml", "job-radar.yml") else {}
        if args.weekly_token_limit and args.name == "job-radar.yml":
            inputs["weekly_token_limit"] = args.weekly_token_limit
        request(root + "/actions/workflows/" + (args.name or "weekly.yml") + "/dispatches", "POST",
                {"ref": request(root)["default_branch"], "inputs": inputs})
        print("Workflow dispatched:", args.name or "weekly.yml", args.mode)
    elif args.command == "run":
        run = request(root + "/actions/runs/" + args.name)
        jobs = request(root + "/actions/runs/" + args.name + "/jobs")
        print(json.dumps({"id": run["id"], "status": run["status"], "conclusion": run["conclusion"],
            "url": run["html_url"], "jobs": [{"name": j["name"], "conclusion": j["conclusion"],
                "steps": [{"name": s["name"], "conclusion": s["conclusion"]}
                          for s in j.get("steps", [])]} for j in jobs.get("jobs", [])]}, indent=2))
    elif args.command == "set-secret":
        from base64 import b64decode, b64encode
        from nacl.public import PublicKey, SealedBox
        value = sys.stdin.read().strip()
        if not value or not args.name:
            raise RuntimeError("Secret name and nonempty stdin are required")
        public = request(root + "/actions/secrets/public-key")
        encrypted = b64encode(SealedBox(PublicKey(b64decode(public["key"]))).encrypt(value.encode())).decode()
        request(root + "/actions/secrets/" + args.name, "PUT",
                {"encrypted_value": encrypted, "key_id": public["key_id"]})
        print("Secret configured:", args.name)
    else:
        if not args.name:
            raise RuntimeError("Variable name is required")
        value = sys.stdin.read().strip()
        existing = request(root + "/actions/variables")
        present = any(x["name"] == args.name for x in existing.get("variables", []))
        path = root + "/actions/variables" + ("/" + args.name if present else "")
        request(path, "PATCH" if present else "POST", {"name": args.name, "value": value})
        print("Variable configured:", args.name)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print("GitHub request failed: HTTP", exc.code, file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print("Deployment helper failed:", type(exc).__name__, file=sys.stderr)
        sys.exit(1)
