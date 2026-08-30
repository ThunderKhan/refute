import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, CircleDot, Github, Link2, Play, ShieldCheck, Sparkles, TestTube2, X } from "lucide-react";
import {
  inspectGitHubPR,
  listCases,
  verifyCase,
  verifyGitHubPR,
  type DashboardCase,
  type GitHubPRMetadata,
  type VerificationPayload,
} from "./api";
import MarkdownBlock from "./MarkdownBlock";

type Mode = "github" | "benchmark";

function statusText(passed: boolean, timedOut: boolean, exitCode: number | null) {
  if (timedOut) return "TIMEOUT";
  return passed ? "PASS" : `FAIL${exitCode === null ? "" : ` · exit ${exitCode}`}`;
}

function shortSha(value: string) {
  return value.slice(0, 8);
}

function normalizeHeading(value: string) {
  return value.trim().replace(/^#+\s*/, "").replace(/\s+/g, " ").toLowerCase();
}

function withoutDuplicateLeadingTitle(markdown: string, title: string) {
  const lines = markdown.replace(/^\uFEFF/, "").split(/\r?\n/);
  const firstContent = lines.findIndex((line) => line.trim().length > 0);
  if (firstContent < 0) return markdown;
  const line = lines[firstContent];
  if (/^#{1,6}\s+/.test(line) && normalizeHeading(line) === normalizeHeading(title)) {
    lines.splice(firstContent, 1);
    while (lines[firstContent]?.trim() === "") lines.splice(firstContent, 1);
  }
  return lines.join("\n").trim();
}

export default function LiveVerifyPage() {
  const [mode, setMode] = useState<Mode>("github");
  const [cases, setCases] = useState<DashboardCase[]>([]);
  const [selected, setSelected] = useState("case_002");
  const [githubUrl, setGithubUrl] = useState("");
  const [githubMeta, setGithubMeta] = useState<GitHubPRMetadata | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [result, setResult] = useState<VerificationPayload | null>(null);
  const [loadingCases, setLoadingCases] = useState(true);
  const [inspecting, setInspecting] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCases()
      .then((items) => {
        setCases(items);
        if (items.length && !items.some((item) => item.case_id === selected)) {
          setSelected(items[0].case_id);
        }
      })
      .catch(() => undefined)
      .finally(() => setLoadingCases(false));
  }, []);

  const selectedCase = useMemo(
    () => cases.find((item) => item.case_id === selected) ?? null,
    [cases, selected],
  );

  async function inspectPR() {
    if (!githubUrl.trim() || inspecting || running) return;
    setInspecting(true);
    setError(null);
    setResult(null);
    setConfirmed(false);
    try {
      const metadata = await inspectGitHubPR(githubUrl.trim());
      setGithubMeta(metadata);
    } catch (err) {
      setGithubMeta(null);
      setError(err instanceof Error ? err.message : "could not inspect GitHub PR");
    } finally {
      setInspecting(false);
    }
  }

  async function runVerification() {
    if (running) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const next = mode === "github"
        ? await verifyGitHubPR(githubUrl.trim())
        : await verifyCase(selected);
      setResult(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "verification failed");
    } finally {
      setRunning(false);
    }
  }

  const targetedReproduction = result?.source?.["reproduction_mode"] === "patch_changed_tests";
  const reproductionTargets = Array.isArray(result?.source?.["reproduction_targets"])
    ? result?.source?.["reproduction_targets"] as string[]
    : [];

  const timeline = result
    ? [
        {
          title: mode === "github" && targetedReproduction ? "Targeted reproduction" : "Public tests",
          detail: `${targetedReproduction && reproductionTargets.length ? `${reproductionTargets.join(", ")} · ` : ""}Original ${statusText(result.original.passed, result.original.timed_out, result.original.exit_code)} → patched ${statusText(result.patched.passed, result.patched.timed_out, result.patched.exit_code)}`,
          state: result.patched.passed ? "done" : "warn",
        },
        {
          title: "Test delta",
          detail: result.test_delta.replaceAll("_", " "),
          state: "done",
        },
        {
          title: "Agent planner",
          detail: result.planner_called
            ? result.planner_fallback
              ? "Planner failed; deterministic fallback recorded"
              : "Probe prioritization completed without fallback"
            : "Planner not needed for this evidence shape",
          state: result.planner_fallback ? "warn" : "done",
        },
        ...result.probes.map((probe) => ({
          title: `${probe.probe_id} · ${probe.description}`,
          detail: `${probe.classification.replaceAll("_", " ")} · original ${statusText(probe.original.passed, probe.original.timed_out, probe.original.exit_code)} · patch ${statusText(probe.patched.passed, probe.patched.timed_out, probe.patched.exit_code)}`,
          state: probe.classification.includes("counterexample") ? "warn" : "done",
        })),
      ]
    : [];

  const issueTitle = mode === "github"
    ? githubMeta?.title ?? "Public GitHub pull request"
    : selectedCase?.title ?? selected;
  const issueText = mode === "github"
    ? githubMeta
      ? withoutDuplicateLeadingTitle(githubMeta.body || githubMeta.issue_text, githubMeta.title)
      : "Paste a public GitHub pull request URL to inspect its public contract and revisions."
    : selectedCase?.issue_text ?? (loadingCases ? "Loading case…" : "Benchmark data unavailable.");

  return (
    <div className="app-shell">
      <header className="nav-wrap">
        <nav className="nav container">
          <a className="wordmark" href="/">refute<span className="wordmark-dot">.</span></a>
          <div className="nav-links desktop-nav">
            <a className="active" href="/verify">Verify</a>
            <a href="/benchmark">Benchmark</a>
            <a href="/how-it-works">How it works</a>
            <a href="/journey">Journey</a>
          </div>
          <div className="nav-actions">
            <a className="icon-button desktop-only" href="https://github.com/ThunderKhan/refute" target="_blank" rel="noreferrer" aria-label="GitHub"><Github size={17} /></a>
            <a className="pill-button dark" href="/">Overview <ArrowLeft size={15} /></a>
          </div>
        </nav>
      </header>

      <main>
        <section className="page-hero">
          <div className="container page-hero-grid">
            <div>
              <div className="eyebrow"><CircleDot size={14} /> Real patch verification</div>
              <h1>Paste the PR.<br />Get the verdict.</h1>
            </div>
            <p>refute checks a public Python/pytest pull request locally, compares base and patched revisions, challenges repaired behavior with contract-derived probes, and returns an evidence-backed verdict.</p>
          </div>
        </section>

        <section className="section-pad verify-workspace">
          <div className="container verify-grid">
            <aside className="control-card live-control-card">
              <div className="mode-switch" role="tablist" aria-label="Verification mode">
                <button className={mode === "github" ? "active" : ""} onClick={() => { setMode("github"); setResult(null); setError(null); }}>GitHub PR</button>
                <button className={mode === "benchmark" ? "active" : ""} onClick={() => { setMode("benchmark"); setResult(null); setError(null); }}>Benchmark</button>
              </div>

              {mode === "github" ? (
                <>
                  <div className="card-label">Developer workflow</div>
                  <label>Public GitHub pull request</label>
                  <div className="github-url-field">
                    <Link2 size={15} />
                    <input
                      value={githubUrl}
                      disabled={running || inspecting}
                      onChange={(event) => { setGithubUrl(event.target.value); setGithubMeta(null); setConfirmed(false); setResult(null); }}
                      onKeyDown={(event) => { if (event.key === "Enter") void inspectPR(); }}
                      placeholder="https://github.com/owner/repo/pull/123"
                    />
                  </div>
                  <button className="pill-button dark full inspect-button" onClick={inspectPR} disabled={!githubUrl.trim() || inspecting || running}>
                    {inspecting ? <><Sparkles size={15} /> Inspecting…</> : <><Github size={15} /> Inspect PR</>}
                  </button>

                  {githubMeta && (
                    <div className="pr-summary-mini">
                      <strong>{githubMeta.owner}/{githubMeta.repo} #{githubMeta.number}</strong>
                      <span>{githubMeta.changed_files} files · +{githubMeta.additions} / -{githubMeta.deletions}</span>
                      <span>base {shortSha(githubMeta.base_sha)} → head {shortSha(githubMeta.head_sha)}</span>
                    </div>
                  )}

                  {githubMeta && (
                    <label className="execution-consent">
                      <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
                      <span>I understand refute will create an isolated environment, install the repository's declared Python/test dependencies, and run its pytest suite locally.</span>
                    </label>
                  )}

                  <button className="pill-button orange full" onClick={runVerification} disabled={running || !githubMeta || !confirmed}>
                    {running ? <><Sparkles size={15} /> Provisioning & verifying…</> : <><Play size={15} fill="currentColor" /> Verify patch</>}
                  </button>
                  <p className="microcopy">When a PR changes pytest files, refute uses those patch-authored tests as a deterministic reproduction against both base and patch. Otherwise it falls back to the full suite.</p>
                </>
              ) : (
                <>
                  <div className="card-label">Reproducible demo</div>
                  <label>Benchmark case</label>
                  <select value={selected} disabled={loadingCases || running} onChange={(event) => { setSelected(event.target.value); setResult(null); setError(null); }}>
                    {cases.map((item) => <option key={item.case_id} value={item.case_id}>{item.case_id}</option>)}
                  </select>
                  <label>Provider</label>
                  <div className="readonly-field"><span>Ollama</span><small>local</small></div>
                  <label>Model</label>
                  <div className="readonly-field"><span>qwen3:0.6b</span><small>temperature 0</small></div>
                  <button className="pill-button orange full" onClick={runVerification} disabled={running || loadingCases || cases.length === 0}>
                    {running ? <><Sparkles size={15} /> Verifying…</> : <><Play size={15} fill="currentColor" /> Run benchmark case</>}
                  </button>
                  <p className="microcopy">Frozen Benchmark v2 remains the reproducible evaluation harness behind the measured results.</p>
                </>
              )}
            </aside>

            <div className="verify-main">
              <div className="issue-card">
                <div className="card-label">{mode === "github" ? "PR / issue contract" : "Public issue contract"}</div>
                <h3>{issueTitle}</h3>
                <MarkdownBlock>{issueText}</MarkdownBlock>
                {githubMeta && githubMeta.linked_issue_number && (
                  <div className="linked-issue-chip">Linked issue #{githubMeta.linked_issue_number}{githubMeta.linked_issue_title ? ` · ${githubMeta.linked_issue_title}` : ""}</div>
                )}
              </div>

              {error && (
                <div className="verdict-card verdict-partial live-error-card">
                  <div><div className="card-label">Could not complete verification</div><h2>needs_attention</h2></div>
                  <p>{error}</p>
                </div>
              )}

              <div className="timeline-card">
                <div className="timeline-head">
                  <div><div className="card-label">Evidence timeline</div><h3>{result?.case_id ?? (mode === "github" ? githubMeta ? `${githubMeta.repo}#${githubMeta.number}` : "waiting for PR" : selected)}</h3></div>
                  <span className="status-pill">Iteration 5 · live</span>
                </div>
                <div className="timeline">
                  {!result && !running && <div className="timeline-loading"><span /> ready to collect evidence</div>}
                  {running && <div className="timeline-loading"><span /> cloning revisions, provisioning an isolated environment, locating changed tests, reproducing the reported behavior, planning probes, and collecting evidence…</div>}
                  {timeline.map((item, index) => (
                    <div className="timeline-row" key={`${item.title}-${index}`}>
                      <div className={`timeline-icon ${item.state}`}>{item.state === "done" ? <Check size={14} /> : <X size={14} />}</div>
                      <div><strong>{item.title}</strong><span>{item.detail}</span></div>
                      <small>{String(index + 1).padStart(2, "0")}</small>
                    </div>
                  ))}
                </div>
              </div>

              {result && (
                <div className="verdict-card">
                  <div><div className="card-label">Verdict</div><h2>{result.verdict}</h2></div>
                  <p>{result.reason}</p>
                  <div className="verdict-meta">
                    <span><TestTube2 size={15} /> {result.challenge_counterexamples} counterexample{result.challenge_counterexamples === 1 ? "" : "s"}</span>
                    <span><ShieldCheck size={15} /> {result.planner_fallback ? "fallback recorded" : "evidence-backed"}</span>
                    <span className="evidence-path-live">{result.evidence_path}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
