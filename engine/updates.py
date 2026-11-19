"""Finds out whether a newer Pawn Engine has been released on GitHub. Never blocks the app and never complains when offline."""
import json
import re
import urllib.request

from .paths import resource
from .project import VERSION


def parse_version(text):
    """'v1.2.3' -> (1, 2, 3). Anything that isn't numbers is ignored."""
    return tuple(int(n) for n in re.findall(r"\d+", str(text))[:4]) or (0,)


def is_newer(latest, current=VERSION):
    a, b = parse_version(latest), parse_version(current)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def repo_name():
    """'owner/name' of the GitHub repository this build came from (written into release.json by the build), or ''."""
    try:
        data = json.loads(resource("release.json").read_text(encoding="utf-8"))
        repo = str(data.get("repo", "")).strip()
        return repo if re.fullmatch(r"[\w.-]+/[\w.-]+", repo) else ""
    except Exception:
        return ""


def download_url(repo):
    return f"https://github.com/{repo}/releases/latest/download/PawnEngine-Setup.exe"


def check(repo=None, fetch=None, current=VERSION):
    """Returns a dict: {"status": "newer"|"current"|"unset"|"offline", "latest": "1.3", "url": ..., "notes": ...}."""
    repo = repo_name() if repo is None else repo
    if not repo:
        return {"status": "unset", "latest": "", "url": "", "notes": ""}
    try:
        if fetch is None:
            req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                         headers={"User-Agent": "PawnEngine", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.loads(r.read().decode("utf-8"))
        else:
            data = fetch(repo)
        tag = str(data.get("tag_name", "")).lstrip("vV")
        if not tag:
            return {"status": "offline", "latest": "", "url": "", "notes": ""}
        status = "newer" if is_newer(tag, current) else "current"
        return {"status": status, "latest": tag, "url": download_url(repo), "notes": str(data.get("body") or "")[:600]}
    except Exception:
        return {"status": "offline", "latest": "", "url": "", "notes": ""}
