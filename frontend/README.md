# refute frontend

Presentation layer for the `refute` patch-verification engine.

## Current scope

The frontend establishes the visual system and multi-page product experience before backend wiring:

- `/` — overview and frozen headline metrics
- `/verify` — interactive case_002 verification walkthrough
- `/benchmark` — Benchmark v2 results and experiment history
- `/how-it-works` — final Iteration 5 architecture
- `/journey` — measured iteration timeline

The Verify page currently uses frozen demonstration data from the clean Iteration 5 case_002 run. It is intentionally labelled as presentation data until the Python engine API wrapper is connected.

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

Vite serves the frontend on `http://localhost:5173` by default.

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
