from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .models import VerificationCase


class GitHubPRIngestionError(RuntimeError):
    """Raised when a public GitHub pull request cannot be prepared safely."""


@dataclass(frozen=True, slots=True)
class GitHubPRMetadata:
    url: str
    owner: str
    repo: str
    number: int
    title: str
    body: str
    base_sha: str
    head_sha: str
    clone_url: str
    changed_files: int
    additions: int
    deletions: int
    linked_issue_number: int | None = None
    linked_issue_title: str | None = None
    linked_issue_body: str | None = None

    @property
    def issue_text(self) -> str:
        chunks = [f"# {self.title}"]
        if self.body.strip():
            chunks.extend(["", self.body.strip()])
        if self.linked_issue_number is not None:
            chunks.extend(["", f"## Linked issue #{self.linked_issue_number}", self.linked_issue_title or ""])
            if self.linked_issue_body and self.linked_issue_body.strip():
                chunks.extend(["", self.linked_issue_body.strip()])
        return "\n".join(chunks).strip() + "\n"


def parse_github_pr_url(value: str) -> tuple[str, str, int]:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise GitHubPRIngestionError("enter a public https://github.com/.../pull/... URL")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 4 or parts[2] != "pull":
        raise GitHubPRIngestionError("URL must look like https://github.com/owner/repo/pull/123")
    owner, repo, _, raw_number = parts
    try:
        number = int(raw_number)
    except ValueError as exc:
        raise GitHubPRIngestionError("pull request number must be numeric") from exc
    if number < 1:
        raise GitHubPRIngestionError("pull request number must be positive")
    return owner, repo, number


def _github_json(url: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "refute/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            raise GitHubPRIngestionError("GitHub PR not found or repository is not public") from exc
        raise GitHubPRIngestionError(f"GitHub API returned HTTP {exc.code}: {detail[:240]}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GitHubPRIngestionError(f"could not read GitHub PR metadata: {exc}") from exc
    if not isinstance(payload, dict):
        raise GitHubPRIngestionError("GitHub returned an unexpected response")
    return payload


def _linked_issue_number(body: str) -> int | None:
    match = re.search(r"(?i)\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+#(\d+)\b", body)
    return int(match.group(1)) if match else None


def fetch_github_pr_metadata(value: str) -> GitHubPRMetadata:
    owner, repo, number = parse_github_pr_url(value)
    payload = _github_json(f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}")
    body = str(payload.get("body") or "")
    linked_number = _linked_issue_number(body)
    issue_title = None
    issue_body = None
    if linked_number is not None:
        try:
            issue = _github_json(f"https://api.github.com/repos/{owner}/{repo}/issues/{linked_number}")
            issue_title = str(issue.get("title") or "")
            issue_body = str(issue.get("body") or "")
        except GitHubPRIngestionError:
            linked_number = None

    base = payload.get("base") or {}
    head = payload.get("head") or {}
    base_repo = base.get("repo") or {}
    clone_url = str(base_repo.get("clone_url") or f"https://github.com/{owner}/{repo}.git")
    base_sha = str(base.get("sha") or "")
    head_sha = str(head.get("sha") or "")
    if not base_sha or not head_sha:
        raise GitHubPRIngestionError("GitHub PR metadata did not include base/head revisions")

    return GitHubPRMetadata(
        url=value.strip(), owner=owner, repo=repo, number=number,
        title=str(payload.get("title") or f"PR #{number}"), body=body,
        base_sha=base_sha, head_sha=head_sha, clone_url=clone_url,
        changed_files=int(payload.get("changed_files") or 0),
        additions=int(payload.get("additions") or 0),
        deletions=int(payload.get("deletions") or 0),
        linked_issue_number=linked_number,
        linked_issue_title=issue_title,
        linked_issue_body=issue_body,
    )


def _run_git(args: list[str], cwd: Path | None = None) -> None:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=120, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitHubPRIngestionError(f"git operation failed: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise GitHubPRIngestionError(f"git operation failed: {detail[:400]}")


def _detect_pytest(repo: Path) -> tuple[str, ...] | None:
    has_tests = (repo / "tests").is_dir() or any(repo.glob("test_*.py"))
    has_config = any((repo / name).is_file() for name in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"))
    if not has_tests and not has_config:
        return None
    return (sys.executable, "-m", "pytest", "-q")


def prepare_github_pr_case(metadata: GitHubPRMetadata, workspace_root: str | Path) -> VerificationCase:
    workspace_root = Path(workspace_root).resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    run_root = workspace_root / f"github-{metadata.owner}-{metadata.repo}-pr-{metadata.number}-{uuid.uuid4().hex[:8]}"
    source = run_root / "source"
    original = run_root / "original"
    patched = run_root / "patched"
    run_root.mkdir(parents=True)

    try:
        _run_git(["clone", "--quiet", "--filter=blob:none", "--no-checkout", metadata.clone_url, str(source)])
        _run_git(["fetch", "--quiet", "origin", metadata.base_sha], cwd=source)
        # GitHub exposes pull-request heads in the base repository even when the
        # contributor branch lives in a fork. Fetching this ref makes fork PRs
        # work without adding an untrusted fork remote.
        _run_git([
            "fetch", "--quiet", "origin",
            f"refs/pull/{metadata.number}/head:refs/remotes/origin/refute-pr-head",
        ], cwd=source)
        _run_git(["worktree", "add", "--quiet", "--detach", str(original), metadata.base_sha], cwd=source)
        _run_git(["worktree", "add", "--quiet", "--detach", str(patched), metadata.head_sha], cwd=source)
    except Exception:
        shutil.rmtree(run_root, ignore_errors=True)
        raise

    test_command = _detect_pytest(patched)
    if test_command is None:
        raise GitHubPRIngestionError(
            "refute real-repo mode currently supports public Python repositories with a detectable pytest test surface"
        )

    issue_path = run_root / "issue.md"
    issue_path.write_text(metadata.issue_text, encoding="utf-8")
    return VerificationCase(
        case_id=f"github_{metadata.owner}_{metadata.repo}_pr_{metadata.number}",
        root=run_root,
        issue_path=issue_path,
        original_path=original,
        patched_path=patched,
        test_command=test_command,
        notes="public GitHub PR ingestion; no evaluator oracle",
    )
