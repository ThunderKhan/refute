import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownRight,
  ArrowRight,
  Check,
  ChevronRight,
  CircleDot,
  Code2,
  ExternalLink,
  Github,
  Gauge,
  GitPullRequest,
  Menu,
  Play,
  ShieldCheck,
  Sparkles,
  Terminal,
  TestTube2,
  X,
  Zap,
} from "lucide-react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";

const metrics = [
  { label: "Baseline accuracy", value: "10.0%", note: "static issue + diff" },
  { label: "Final accuracy", value: "100.0%", note: "Iteration 5 · Benchmark v2" },
  { label: "False acceptance", value: "0.0%", note: "down from 57.1%" },
  { label: "Avg runtime", value: "5.077s", note: "per controlled case" },
];

const benchmark = [
  ["001", "complete_fix", "complete_fix"],
  ["002", "partial_fix", "partial_fix"],
  ["003", "regression_introduced", "regression_introduced"],
  ["004", "ineffective_fix", "ineffective_fix"],
  ["005", "complete_fix", "complete_fix"],
  ["006", "partial_fix", "partial_fix"],
  ["007", "regression_introduced", "regression_introduced"],
  ["008", "ineffective_fix", "ineffective_fix"],
  ["009", "complete_fix", "complete_fix"],
  ["010", "inconclusive", "inconclusive"],
];

const experiments = [
  ["Baseline", 10, "Static review only"],
  ["Iter. 1", 40, "Execution evidence"],
  ["Iter. 2", 10, "Generated reproduction"],
  ["Iter. 2.1", 40, "Discriminating evidence"],
  ["Iter. 2.2", 30, "Evidence weighting"],
  ["Iter. 2.3", 50, "Test deltas"],
  ["Iter. 2.4", 60, "Test-first routing"],
  ["Iter. 3", 40, "Free-form challenger"],
  ["Iter. 3.1", 30, "Exact quote grounding"],
  ["Iter. 3.2", 30, "Contract IDs"],
  ["Iter. 3.3", 30, "Entailment critic"],
  ["Iter. 4", 30, "Structured intents"],
  ["Iter. 5", 100, "Deterministic probes"],
] as const;

const verifySteps = [
  ["Public tests", "Reported trigger changed from FAIL → PASS", "done"],
  ["Contract extraction", "0 through 100 inclusive", "done"],
  ["Probe compiler", "Upper boundary probe compiled deterministically", "done"],
  ["Agent planner", "p2 prioritized", "done"],
  ["Original execution", "Upper boundary still fails", "warn"],
  ["Patched execution", "Upper boundary still fails", "warn"],
] as const;

function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/verify" element={<Verify />} />
        <Route path="/benchmark" element={<Benchmark />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/journey" element={<Journey />} />
      </Routes>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [location.pathname]);

  const nav = [
    ["Verify", "/verify"],
    ["Benchmark", "/benchmark"],
    ["How it works", "/how-it-works"],
    ["Journey", "/journey"],
  ];

  return (
    <div className="app-shell">
      <header className="nav-wrap">
        <nav className="nav container">
          <Link className="wordmark" to="/" aria-label="refute home">
            refute<span className="wordmark-dot">.</span>
          </Link>
          <div className="nav-links desktop-nav">
            {nav.map(([label, to]) => (
              <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : "")}>
                {label}
              </NavLink>
            ))}
          </div>
          <div className="nav-actions">
            <a className="icon-button desktop-only" href="https://github.com/ThunderKhan/refute" target="_blank" rel="noreferrer" aria-label="GitHub">
              <Github size={17} />
            </a>
            <Link className="pill-button dark" to="/verify">
              Run verification <ArrowRight size={15} />
            </Link>
            <button className="menu-button" onClick={() => setOpen(!open)} aria-label="Toggle menu">
              {open ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </nav>
        {open && (
          <div className="mobile-menu container">
            {nav.map(([label, to]) => (
              <NavLink key={to} to={to}>{label}</NavLink>
            ))}
          </div>
        )}
      </header>
      <main>{children}</main>
      <Footer />
    </div>
  );
}

function Home() {
  return (
    <>
      <section className="hero-orange">
        <div className="hero-mesh" />
        <div className="container hero-grid">
          <div className="hero-copy reveal">
            <div className="eyebrow light"><CircleDot size={14} /> Evidence-backed patch verification</div>
            <h1>Don't trust the patch.<br />Try to <em>break</em> it.</h1>
            <p>
              refute tests whether a software patch actually fixes the reported bug — then challenges it with nearby contract-derived cases before it earns a verdict.
            </p>
            <div className="hero-actions">
              <Link className="pill-button white" to="/verify"><Play size={15} fill="currentColor" /> Verify a patch</Link>
              <Link className="text-link light-link" to="/how-it-works">See how it works <ArrowDownRight size={15} /></Link>
            </div>
          </div>
          <div className="hero-terminal reveal delay-1">
            <div className="terminal-top"><span /><span /><span /><small>case_002 · iteration 5</small></div>
            <pre><code><span className="muted">$</span> refute verify case_002{`\n\n`}<span className="muted">original tests</span>   <b className="bad">FAIL</b>{`\n`}<span className="muted">patched tests</span>    <b className="good">PASS</b>{`\n\n`}<span className="muted">probe</span>            upper boundary: 100{`\n`}<span className="muted">patch outcome</span>    <b className="bad">FAIL</b>{`\n\n`}<span className="orange">VERDICT</span>          <b>partial_fix</b></code></pre>
          </div>
        </div>
      </section>

      <section className="metrics-band section-pad">
        <div className="container">
          <div className="section-kicker">Measured, not vibes.</div>
          <div className="metric-grid">
            {metrics.map((metric) => <MetricCard key={metric.label} {...metric} />)}
          </div>
          <p className="benchmark-note">Frozen controlled Benchmark v2 · 10 oracle-separated Python/pytest cases · qwen3:0.6b</p>
        </div>
      </section>

      <ScrollRail direction="left" items={["COMPLETE FIX", "PARTIAL FIX", "REGRESSION", "INEFFECTIVE", "INCONCLUSIVE"]} />

      <section className="dark-band section-pad">
        <div className="container split-feature">
          <div>
            <div className="eyebrow dark-eye"><Zap size={14} /> The final architecture</div>
            <h2>The agent decides <em>where</em> to look. Deterministic tools decide what happened.</h2>
            <p>Earlier iterations asked the model to invent tests, assertions, and even semantic expectations. Reliability collapsed. Iteration 5 moved mechanically derivable requirements into a deterministic probe compiler and narrowed the model to prioritization.</p>
            <Link className="pill-button orange" to="/journey">See the experiments <ArrowRight size={15} /></Link>
          </div>
          <Pipeline compact />
        </div>
      </section>

      <section className="section-pad editorial-cta">
        <div className="container">
          <div className="big-quote">“The breakthrough was not a better prompt. It was giving the model <em>less responsibility.</em>”</div>
          <div className="cta-row">
            <span>See the evidence behind every verdict.</span>
            <Link className="pill-button dark" to="/benchmark">Explore benchmark <ArrowRight size={15} /></Link>
          </div>
        </div>
      </section>
    </>
  );
}

function Verify() {
  const [running, setRunning] = useState(false);
  const [visibleSteps, setVisibleSteps] = useState(verifySteps.length);

  function runDemo() {
    if (running) return;
    setRunning(true);
    setVisibleSteps(0);
    verifySteps.forEach((_, index) => {
      window.setTimeout(() => setVisibleSteps(index + 1), 520 * (index + 1));
    });
    window.setTimeout(() => setRunning(false), 520 * (verifySteps.length + 1));
  }

  return (
    <>
      <PageHero eyebrow="Interactive verification" title="Put the patch on trial." body="A visual control surface for the refute engine. This frontend currently demonstrates the frozen case_002 evidence path; backend wiring comes next." />
      <section className="section-pad verify-workspace">
        <div className="container verify-grid">
          <aside className="control-card">
            <div className="card-label">Verification input</div>
            <label>Benchmark case</label>
            <select defaultValue="case_002"><option>case_002</option><option>case_001</option><option>case_003</option><option>case_006</option><option>case_007</option></select>
            <label>Provider</label>
            <div className="readonly-field"><span>Ollama</span><small>local</small></div>
            <label>Model</label>
            <div className="readonly-field"><span>qwen3:0.6b</span><small>temperature 0</small></div>
            <button className="pill-button orange full" onClick={runDemo}>{running ? <><Sparkles size={15} /> Verifying…</> : <><Play size={15} fill="currentColor" /> Run verification</>}</button>
            <p className="microcopy">Demo presentation data only. The next wiring step will call the Python engine directly.</p>
          </aside>

          <div className="verify-main">
            <div className="issue-card">
              <div className="card-label">Public issue contract</div>
              <h3>Percentage boundaries are inclusive</h3>
              <p><code>normalize_percentage</code> should accept values <strong>0 through 100 inclusive</strong>. The patch repairs the lower boundary; refute tests whether the broader contract survives.</p>
            </div>

            <div className="timeline-card">
              <div className="timeline-head"><div><div className="card-label">Evidence timeline</div><h3>case_002</h3></div><span className="status-pill">Iteration 5</span></div>
              <div className="timeline">
                {verifySteps.slice(0, visibleSteps).map(([title, detail, state], index) => (
                  <div className="timeline-row" key={title}>
                    <div className={`timeline-icon ${state}`}>
                      {state === "done" ? <Check size={14} /> : <X size={14} />}
                    </div>
                    <div><strong>{title}</strong><span>{detail}</span></div>
                    <small>0{index + 1}</small>
                  </div>
                ))}
                {running && visibleSteps < verifySteps.length && <div className="timeline-loading"><span /> collecting evidence</div>}
              </div>
            </div>

            {visibleSteps === verifySteps.length && (
              <div className="verdict-card verdict-partial">
                <div><div className="card-label">Verdict</div><h2>partial_fix</h2></div>
                <p>The reported lower boundary is repaired, but a contract-derived upper-boundary probe still fails on both original and patch.</p>
                <div className="verdict-meta"><span><TestTube2 size={15} /> 1 counterexample</span><span><ShieldCheck size={15} /> evidence-backed</span></div>
              </div>
            )}
          </div>
        </div>
      </section>
    </>
  );
}

function Benchmark() {
  return (
    <>
      <PageHero eyebrow="Benchmark v2" title="A measurable improvement, not a prettier explanation." body="The same ten oracle-separated cases are scored across the frozen static baseline and the final Iteration 5 workflow." />
      <section className="section-pad">
        <div className="container metric-grid benchmark-metrics">
          {metrics.map((metric) => <MetricCard key={metric.label} {...metric} />)}
        </div>
      </section>

      <ScrollRail direction="right" items={["10 → 100 ACCURACY", "57.1 → 0 FAR", "4 COUNTEREXAMPLES", "0 FALLBACKS"]} />

      <section className="section-pad bone-band">
        <div className="container">
          <div className="section-heading-row"><div><div className="section-kicker">Case matrix</div><h2>Ten cases. Ten correct verdicts.</h2></div><span className="status-pill success">10 / 10</span></div>
          <div className="case-table">
            <div className="case-row case-header"><span>Case</span><span>Expected</span><span>refute</span><span>Status</span></div>
            {benchmark.map(([id, expected, predicted]) => (
              <div className="case-row" key={id}><span><code>case_{id}</code></span><span>{prettyVerdict(expected)}</span><span>{prettyVerdict(predicted)}</span><span className="table-pass"><Check size={14} /> correct</span></div>
            ))}
          </div>
        </div>
      </section>

      <section className="section-pad">
        <div className="container">
          <div className="section-heading-row"><div><div className="section-kicker">Improvement history</div><h2>Progress was not monotonic.</h2></div><p className="side-copy">The failed iterations are part of the evidence. Prompt refinement plateaued at 30%; architecture changed the result.</p></div>
          <ExperimentChart />
        </div>
      </section>
    </>
  );
}

function HowItWorks() {
  return (
    <>
      <PageHero eyebrow="Architecture" title="Falsification, with a chain of custody." body="Every important verdict claim is tied back to deterministic execution evidence. The model never gets access to evaluator-only oracle data." />
      <section className="section-pad dark-band">
        <div className="container"><Pipeline /></div>
      </section>
      <ScrollRail direction="left" items={["PUBLIC CONTRACT", "PROBE COMPILER", "AGENT PLANNER", "EXECUTION", "VERDICT"]} />
      <section className="section-pad">
        <div className="container principles-grid">
          <Principle icon={<ShieldCheck />} number="01" title="Public evidence only" text="Agents see the issue, public tests, and public code. Expected verdicts and hidden evaluator tests remain outside the verification path." />
          <Principle icon={<Code2 />} number="02" title="Compile, don't hallucinate" text="Iteration 5 recognizes a narrow contract vocabulary and deterministically compiles valid probes instead of asking the LLM to author pytest." />
          <Principle icon={<Gauge />} number="03" title="Narrow agency" text="The model prioritizes pre-grounded probe IDs under a bounded budget. If planning fails, refute records the fallback instead of fabricating success." />
          <Principle icon={<Terminal />} number="04" title="Execution decides" text="Original and patched programs run under the same deterministic command path. Verdict policy follows observed evidence shapes." />
        </div>
      </section>
    </>
  );
}

function Journey() {
  return (
    <>
      <PageHero eyebrow="Improvement journey" title="Seven wrong turns made the final system better." body="refute was built as an experiment log, not a feature checklist. Every major architecture change was measured against the same controlled task." />
      <section className="section-pad journey-section">
        <div className="container journey-list">
          {experiments.map(([name, score, note], index) => (
            <article className={`journey-item ${score === 100 ? "final" : ""}`} key={name}>
              <div className="journey-index">{String(index).padStart(2, "0")}</div>
              <div><div className="journey-name">{name}</div><p>{note}</p></div>
              <div className="journey-score">{score}%</div>
            </article>
          ))}
        </div>
      </section>
      <section className="hero-orange closing-band">
        <div className="container closing-grid">
          <h2>The final lesson:<br /><em>less generative freedom, more trustworthy evidence.</em></h2>
          <div><p>Iteration 5 did not win by making the model smarter. It changed the division of labor between probabilistic reasoning and deterministic machinery.</p><Link className="pill-button white" to="/verify">See it verify <ArrowRight size={15} /></Link></div>
        </div>
      </section>
    </>
  );
}

function PageHero({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <section className="page-hero">
      <div className="container page-hero-grid">
        <div><div className="eyebrow"><CircleDot size={14} /> {eyebrow}</div><h1>{title}</h1></div>
        <p>{body}</p>
      </div>
    </section>
  );
}

function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="metric-card"><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-note">{note}</div></article>;
}

function ScrollRail({ direction, items }: { direction: "left" | "right"; items: string[] }) {
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    const onScroll = () => setOffset(window.scrollY * 0.08 * (direction === "left" ? -1 : 1));
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [direction]);

  const repeated = useMemo(() => [...items, ...items, ...items], [items]);
  return (
    <div className="scroll-rail" aria-hidden="true"><div className="rail-track" style={{ transform: `translate3d(calc(-28% + ${offset}px),0,0)` }}>{repeated.map((item, i) => <span key={`${item}-${i}`}>{item}<i>↗</i></span>)}</div></div>
  );
}

function Pipeline({ compact = false }: { compact?: boolean }) {
  const steps = [
    ["01", "Public tests", "Establish the observed before/after delta."],
    ["02", "Contract compiler", "Turn recognizable public requirements into grounded probe candidates."],
    ["03", "Agent planner", "Prioritize probe IDs under a bounded budget."],
    ["04", "Executor", "Run the same probe against original and patch."],
    ["05", "Verdict policy", "Classify only from the evidence that survived execution."],
  ];
  return <div className={`pipeline ${compact ? "compact" : ""}`}>{steps.map(([n, title, text], i) => <div className="pipeline-row" key={n}><span>{n}</span><div><strong>{title}</strong>{!compact && <p>{text}</p>}</div>{i < steps.length - 1 && <ChevronRight className="pipeline-arrow" size={17} />}</div>)}</div>;
}

function ExperimentChart() {
  return <div className="experiment-chart">{experiments.map(([name, score, note]) => <div className="chart-item" key={name}><div className="bar-wrap"><div className={`bar ${score === 100 ? "final" : ""}`} style={{ height: `${Math.max(score, 8)}%` }}><span>{score}%</span></div></div><strong>{name}</strong><small>{note}</small></div>)}</div>;
}

function Principle({ icon, number, title, text }: { icon: React.ReactNode; number: string; title: string; text: string }) {
  return <article className="principle-card"><div className="principle-top"><span className="principle-icon">{icon}</span><code>{number}</code></div><h3>{title}</h3><p>{text}</p></article>;
}

function Footer() {
  return (
    <footer className="footer">
      <div className="container footer-top"><div><div className="footer-wordmark">refute.</div><p>A patch should not be trusted because it looks correct. It should survive attempts to falsify it.</p></div><div className="footer-links"><div><strong>Product</strong><Link to="/verify">Verify</Link><Link to="/benchmark">Benchmark</Link><Link to="/how-it-works">Architecture</Link></div><div><strong>Project</strong><a href="https://github.com/ThunderKhan/refute" target="_blank" rel="noreferrer">GitHub <ExternalLink size={12} /></a><Link to="/journey">Journey</Link></div></div></div>
      <div className="container footer-bottom"><span>Frontier Engineering Challenge 2026</span><span>Built for defensible uncertainty.</span></div>
    </footer>
  );
}

function prettyVerdict(value: string) {
  return value.replaceAll("_", " ");
}

export default App;
