export type DashboardCase = {
  case_id: string;
  title: string;
  issue_text: string;
  test_command: string;
};

export type ExecutionPayload = {
  passed: boolean;
  exit_code: number | null;
  timed_out: boolean;
  stdout: string;
  stderr: string;
};

export type ProbePayload = {
  probe_id: string;
  description: string;
  kind: string;
  contract_id: string;
  contract_text: string;
  classification: string;
  original: ExecutionPayload;
  patched: ExecutionPayload;
};

export type NearbyAdversaryExecution = {
  candidate_id: string;
  nodeid: string;
  classification: string;
  original: ExecutionPayload;
  patched: ExecutionPayload;
};

export type NearbyAdversaryPayload = {
  candidate_count: number;
  selected_ids: string[];
  used_fallback: boolean;
  collection_error: string | null;
  executions: NearbyAdversaryExecution[];
};

export type GitHubPRMetadata = {
  url: string;
  owner: string;
  repo: string;
  number: number;
  title: string;
  body: string;
  base_sha: string;
  head_sha: string;
  changed_files: number;
  additions: number;
  deletions: number;
  linked_issue_number: number | null;
  linked_issue_title: string | null;
  issue_text: string;
};

export type VerificationPayload = {
  run_id: string;
  case_id: string;
  issue_text: string;
  verdict: string;
  reason: string;
  test_delta: string;
  original: ExecutionPayload;
  patched: ExecutionPayload;
  planner_called: boolean;
  planner_fallback: boolean;
  challenger_called: boolean;
  challenge_generation_failures: string[];
  challenge_counterexamples: number;
  probes: ProbePayload[];
  evidence_path: string;
  source?: Record<string, unknown> | null;
  nearby_adversary?: NearbyAdversaryPayload | null;
};

export type VerificationProgressEvent = {
  stage: string;
  detail: string;
};

export type GitHubVerificationJob = {
  job_id: string;
  status: "running" | "complete" | "error";
  stage: string;
  detail: string;
  events: VerificationProgressEvent[];
  result: VerificationPayload | null;
  error: string | null;
};

const API_ROOT = import.meta.env.VITE_REFUTE_API ?? "http://127.0.0.1:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.error ?? `refute API returned ${response.status}`);
  }
  return payload as T;
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function listCases(): Promise<DashboardCase[]> {
  const payload = await request<{ cases: DashboardCase[] }>("/api/cases");
  return payload.cases;
}

export async function verifyCase(caseId: string): Promise<VerificationPayload> {
  return request<VerificationPayload>(`/api/verify/${encodeURIComponent(caseId)}`, {
    method: "POST",
    body: JSON.stringify({
      provider: "ollama",
      model: "qwen3:0.6b",
      llm_timeout: 30,
      execution_timeout: 20,
    }),
  });
}

export async function inspectGitHubPR(url: string): Promise<GitHubPRMetadata> {
  return request<GitHubPRMetadata>("/api/github/inspect", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function verifyGitHubPR(
  url: string,
  onProgress?: (job: GitHubVerificationJob) => void,
): Promise<VerificationPayload> {
  const started = await request<{ job_id: string }>("/api/github/verify/start", {
    method: "POST",
    body: JSON.stringify({
      url,
      confirm_execution: true,
      provider: "ollama",
      model: "qwen3:0.6b",
      llm_timeout: 30,
      execution_timeout: 30,
    }),
  });

  while (true) {
    const job = await request<GitHubVerificationJob>(`/api/github/jobs/${encodeURIComponent(started.job_id)}`);
    onProgress?.(job);
    if (job.status === "complete") {
      if (!job.result) throw new Error("verification completed without a result");
      return job.result;
    }
    if (job.status === "error") {
      throw new Error(job.error ?? "verification failed");
    }
    await sleep(700);
  }
}
