# refute frontend

Presentation and control surface for the `refute` patch-verification engine.

## Product flow

The primary `/verify` experience is now aimed at a real developer workflow:

1. paste a **public GitHub pull-request URL**;
2. inspect the PR metadata and linked issue when available;
3. explicitly confirm local execution;
4. let `refute` clone the base and patched revisions into an isolated workspace under `artifacts/`;
5. run the detected pytest suite on both revisions;
6. challenge repaired behavior with Iteration 5 contract-derived probes;
7. render the evidence-backed verdict and artifact path.

The current real-repository scope is intentionally narrow:

- public GitHub pull requests;
- Python repositories;
- a detectable pytest test surface;
- dependencies must already be available in the active Python environment;
- no dependency installation, publishing, merging, or remote repository modification is performed.

The Verify page also retains a **Benchmark** tab for the frozen oracle-separated Benchmark v2 cases used in the measured hackathon evaluation.

## Pages

- `/` — product overview and frozen headline metrics
- `/verify` — GitHub PR verification + reproducible benchmark mode
- `/benchmark` — Benchmark v2 results and experiment history
- `/how-it-works` — final Iteration 5 architecture
- `/journey` — measured iteration timeline

## Run locally

From the repository root, refresh the editable install and start the local API:

```powershell
python -m pip install -e ".[dev]"
python scripts/build_benchmark_v2.py
refute-dashboard
```

The API listens on `http://127.0.0.1:8765` by default.

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

- frontend: `http://localhost:5173`
- live verifier: `http://localhost:5173/verify`

The frontend uses `http://127.0.0.1:8765` unless `VITE_REFUTE_API` is set.

## Production build

```powershell
cd frontend
npm install
npm run build
npm run preview
```

## Execution safety

A GitHub PR verification can execute code from an external repository. The UI therefore requires an explicit checkbox acknowledgement before the API will run the PR. The API independently rejects GitHub verification requests without `confirm_execution: true`.

This hackathon MVP runs locally rather than claiming a hardened sandbox. Do not use real-repository mode on code you are unwilling to execute on your machine.

## Design direction

The UI follows the provided Replicate-inspired design analysis: warm cream canvas, restrained hot-orange accent, editorial display typography, dark code/evidence wells, rounded controls, hairline separators, and sparse shadows.

The scrolling rails deliberately alternate left/right movement as the document scrolls. Motion respects `prefers-reduced-motion`.
