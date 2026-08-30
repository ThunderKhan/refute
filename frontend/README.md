# refute frontend

Presentation layer for the `refute` patch-verification engine.

## Current scope

- `/` — overview and frozen headline metrics
- `/verify` — live Iteration 5 verification against local Benchmark v2 cases
- `/benchmark` — Benchmark v2 results and experiment history
- `/how-it-works` — final Iteration 5 architecture
- `/journey` — measured iteration timeline

The Verify page now calls the local Python `refute` engine through the standard-library dashboard API. The API does not load evaluator-only oracle or hidden-test material into the verification path.

## Run locally

From the repository root, refresh the editable install so the `refute-dashboard` entry point exists:

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

Vite serves the frontend on `http://localhost:5173` by default.

The frontend uses `http://127.0.0.1:8765` unless `VITE_REFUTE_API` is set.

## Production build

```powershell
cd frontend
npm install
npm run build
npm run preview
```

## Design direction

The UI follows the provided Replicate-inspired design analysis: warm cream canvas, restrained hot-orange accent, editorial display typography, dark code/evidence wells, rounded controls, hairline separators, and sparse shadows.

The scrolling rails deliberately alternate left/right movement as the document scrolls. Motion respects `prefers-reduced-motion`.
