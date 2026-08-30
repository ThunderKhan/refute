from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
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
    _git_output(args, cwd)


def _git_output(args: list[str], cwd: Path | None = None) -> str:
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
    return completed.stdout


def _detect_pytest(repo: Path) -> tuple[str, ...] | None:
    has_tests = (repo / "tests").is_dir() or any(repo.glob("test_*.py"))
    has_config = any((repo / name).is_file() for name in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"))
    if not has_tests and not has_config:
        return None
    return (sys.executable, "-m", "pytest", "-q")


def _is_pytest_file(path: str) -> bool:
    candidate = PurePosixPath(path)
    name = candidate.name
    return path.endswith(".py") and (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "tests" in candidate.parts
    )


def _changed_test_files(source: Path, base_sha: str, head_sha: str) -> tuple[str, ...]:
    output = _git_output(["diff", "--name-only", "--diff-filter=ACMR", base_sha, head_sha, "--"], cwd=source)
    return tuple(line.strip() for line in output.splitlines() if line.strip() and _is_pytest_file(line.strip()))


def _added_test_names(source: Path, base_sha: str, head_sha: str, test_files: tuple[str, ...]) -> tuple[str, ...]:
    if not test_files:
        return ()
    diff = _git_output(["diff", "--unified=0", base_sha, head_sha, "--", *test_files], cwd=source)
    names: list[str] = []
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        match = re.match(r"\+\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(", line)
        if match and match.group(1) not in names:
            names.append(match.group(1))
    return tuple(names)


def _materialize_patch_tests_on_base(original: Path, patched: Path, test_files: tuple[str, ...]) -> None:
    """Place patch-authored/modified tests onto the base worktree for reproduction."""
    for relative in test_files:
        source = patched / Path(relative)
        destination = original / Path(relative)
        if not source.is_file():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _venv_python(venv_root: Path) -> Path:
    if os.name == "nt":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


def _declared_test_dependencies(repo: Path) -> list[str]:
    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        return ["pytest>=8,<9"]

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise GitHubPRIngestionError(f"could not read target pyproject.toml: {exc}") from exc

    deps: list[str] = []
    project = data.get("project")
    if isinstance(project, dict):
        runtime = project.get("dependencies")
        if isinstance(runtime, list):
            deps.extend(str(item) for item in runtime if isinstance(item, str))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group_name in ("test", "tests", "dev"):
                group = optional.get(group_name)
                if isinstance(group, list):
                    deps.extend(str(item) for item in group if isinstance(item, str))

    groups = data.get("dependency-groups")
    if isinstance(groups, dict):
        for group_name in ("test", "tests", "dev"):
            group = groups.get(group_name)
            if isinstance(group, list):
                deps.extend(str(item) for item in group if isinstance(item, str))

    if not any(re.match(r"(?i)^pytest(?:\b|[<>=!~\[])", dep.strip()) for dep in deps):
        deps.append("pytest>=8,<9")

    return list(dict.fromkeys(dep.strip() for dep in deps if dep.strip()))


def _provision_runtime(repo: Path, run_root: Path) -> Path:
    runtime_root = run_root / "runtime"
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "venv", str(runtime_root)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitHubPRIngestionError(f"could not create isolated target environment: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise GitHubPRIngestionError(f"could not create isolated target environment: {detail[:400]}")

    python = _venv_python(runtime_root)
    dependencies = _declared_test_dependencies(repo)
    try:
        completed = subprocess.run(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", *dependencies],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitHubPRIngestionError(f"target dependency provisioning failed: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise GitHubPRIngestionError(
            "target dependency provisioning failed before verification. "
            f"pip output: {detail[-800:]}"
        )
    return python


def _write_pytest_wrapper(run_root: Path, runtime_python: Path) -> Path:
    wrapper = run_root / "run_pytest.py"
    wrapper.write_text(
        "from __future__ import annotations\n"
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        f"RUNTIME = Path({str(runtime_python)!r})\n"
        "cwd = Path.cwd().resolve()\n"
        "env = os.environ.copy()\n"
        "pythonpath = [str(cwd), str(cwd / 'src')]\n"
        "existing = env.get('PYTHONPATH')\n"
        "if existing:\n"
        "    pythonpath.append(existing)\n"
        "env['PYTHONPATH'] = os.pathsep.join(pythonpath)\n"
        "command = [str(RUNTIME), '-m', 'pytest', '-q', *sys.argv[1:]]\n"
        "completed = subprocess.run(command, cwd=cwd, env=env)\n"
        "raise SystemExit(completed.returncode)\n",
        encoding="utf-8",
    )
    return wrapper


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
        _run_git([
            "fetch", "--quiet", "origin",
            f"refs/pull/{metadata.number}/head:refs/remotes/origin/refute-pr-head",
        ], cwd=source)
        _run_git(["worktree", "add", "--quiet", "--detach", str(original), metadata.base_sha], cwd=source)
        _run_git(["worktree", "add", "--quiet", "--detach", str(patched), metadata.head_sha], cwd=source)
    except Exception:
        shutil.rmtree(run_root, ignore_errors=True)
        raise

    if _detect_pytest(patched) is None:
        raise GitHubPRIngestionError(
            "refute real-repo mode currently supports public Python repositories with a detectable pytest test surface"
        )

    changed_tests = _changed_test_files(source, metadata.base_sha, metadata.head_sha)
    added_tests = _added_test_names(source, metadata.base_sha, metadata.head_sha, changed_tests)
    diff = _git_output(["diff", "--no-ext-diff", "--unified=3", metadata.base_sha, metadata.head_sha, "--"], cwd=source)
    (run_root / "github_context.json").write_text(
        json.dumps(
            {
                "changed_tests": list(changed_tests),
                "added_test_names": list(added_tests),
                "diff": diff[:50000],
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    if changed_tests:
        _materialize_patch_tests_on_base(original, patched, changed_tests)

    runtime_python = _provision_runtime(patched, run_root)
    wrapper = _write_pytest_wrapper(run_root, runtime_python)

    issue_path = run_root / "issue.md"
    issue_path.write_text(metadata.issue_text, encoding="utf-8")
    targets = changed_tests if changed_tests else ()
    mode_note = (
        "targeted reproduction using patch-changed pytest files"
        if changed_tests
        else "full-suite fallback because the PR changed no pytest files"
    )
    return VerificationCase(
        case_id=f"github_{metadata.owner}_{metadata.repo}_pr_{metadata.number}",
        root=run_root,
        issue_path=issue_path,
        original_path=original,
        patched_path=patched,
        test_command=(sys.executable, str(wrapper), *targets),
        notes=(
            "public GitHub PR ingestion; isolated dependency environment; "
            f"{mode_note}; no evaluator oracle"
        ),
    )
