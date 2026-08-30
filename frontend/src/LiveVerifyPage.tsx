import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, CircleDot, Github, Play, ShieldCheck, Sparkles, TestTube2, X } from "lucide-react";
import { listCases, verifyCase, type DashboardCase, type VerificationPayload } from "./api";

function statusText(passed: boolean, timedOut: boolean, exitCode: number | null) {
  if (timedOut) return "TIMEOUT";
  return passed ? "PASS" : `FAIL${exitCode === null ? "" : ` · exit ${exitCode}`}`;
}

export default function LiveVerifyPage() {
  const [cases, setCases] = useState<DashboardCase[]>([]);
  const [selected, setSelected] = useState("case_002");
  const [result, setResult] = useState<VerificationPayload | null>(null);
  const [loadingCases, setLoadingCases] = useState(true);
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
      .catch((err: Error) => setError(`Dashboard API unavailable: ${err.message}`))
      .finally(() => setLoadingCases(false));
  }, []);

  const selectedCase = useMemo(
    () => cases.find((item) => item.case_id === selected) ?? null,
    [cases, selected],
  );

  async function runVerification() {
    if (running) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const next = await verifyCase(selected);
      setResult(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "verification failed");
    } finally {
      setRunning(false);
    }
  }

  const timeline = result
    ? [
        {
          title: "Public tests",
          detail: `Original ${statusText(result.original.passed, result.original.timed_out, result.original.exit_code)} → patched ${statusText(result.patched.passed, result.patched.timed_out, result.patched.exit_code)}`,
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
            <a className="icon-button desktop-only" href="https://github.com/ThunderKhan/refute" target="_blank" rel="noreferrer" aria-label="GitHub">
              <Github size={17} />
            </a>
            <a className="pill-button dark" href="/">Overview <ArrowLeft size={15} /></a>
          </div>
        </nav>
      </header>

      <main>
        <section className="page-hero">
          <div className="container page-hero-grid">
            <div>
              <div className="eyebrow"><CircleDot size={14} /> Live verification</div>
              <h1>Put the patch on trial.</h1>
            </div>
            <p>This page now calls the real Iteration 5 Python engine. Every verdict, probe outcome, and evidence path below comes from the local refute run.</p>
          </div>
        </section>

        <section className="section-pad verify-workspace">
          <div className="container verify-grid">
            <aside className="control-card">
              <div className="card-label">Verification input</div>
              <label>Benchmark case</label>
              <select
                value={selected}
                disabled={loadingCases || running}
                onChange={(event) => {
                  setSelected(event.target.value);
                  setResult(null);
                  setError(null);
                }}
              >
                {cases.map((item) => <option key={item.case_id} value={item.case_id}>{item.case_id}</option>)}
              </select>

              <label>Provider</label>
              <div className="readonly-field"><span>Ollama</span><small>local</small></div>
              <label>Model</label>
              <div className="readonly-field"><span>qwen3:0.6b</span><small>temperature 0</small></div>

              <button className="pill-button orange full" onClick={runVerification} disabled={running || loadingCases || cases.length === 0}>
                {running ? <><Sparkles size={15} /> Verifying…</> : <><Play size={15} fill="currentColor" /> Run verification</>}
              </button>
              <p className="microcopy">Local execution only. Benchmark oracle and hidden tests are not sent to the verifier.</p>
            </aside>

            <div className="verify-main">
              <div className="issue-card">
                <div className="card-label">Public issue contract</div>
                <h3>{selectedCase?.title ?? selected}</h3>
                <p className="issue-copy-live">{selectedCase?.issue_text ?? (loadingCases ? "Loading case…" : "Start the dashboard API to load public case data.")}</p>
              </div>

              {error && (
                <div className="verdict-card verdict-partial live-error-card">
                  <div><div className="card-label">Connection / verification error</div><h2>needs_attention</h2></div>
                  <p>{error}</p>
                </div>
              )}

              <div className="timeline-card">
                <div className="timeline-head">
                  <div><div className="card-label">Evidence timeline</div><h3>{result?.case_id ?? selected}</h3></div>
                  <span className="status-pill">Iteration 5 · live</span>
                </div>
                <div className="timeline">
                  {!result && !running && <div className="timeline-loading"><span /> ready to collect evidence</div>}
                  {running && <div className="timeline-loading"><span /> executing public tests, planning probes, and collecting evidence…</div>}
                  {timeline.map((item, index) => (
                    <div className="timeline-row" key={`${item.title}-${index}`}>
                      <div className={`timeline-icon ${item.state}`}>
                        {item.state === "done" ? <Check size={14} /> : <X size={14} />}
                      </div>
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
