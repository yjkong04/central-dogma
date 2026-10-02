# AGENTS.md

Project-specific instructions for coding agents working in this repo.

## Stack

- Backend: Python 3.11/3.12 (`api/`, `worker/`, `ingest/`), pytest
- Frontend: Next.js 16 + React 19 + TypeScript (`frontend/`)
- Deploy: AWS SAM (`deploy/template.yaml` — Lambda + Bedrock + S3/CloudFront demo) and Fly.io (`fly.toml` — lightweight demo-store API, no external services)

## Commands

### Backend (run from repo root)

- Install: `pip install -r requirements.txt -r requirements-dev.txt`
- Test: `python -m pytest -q`
  - Set `CENTRALDOGMA_EMBEDDER=hashing` to run against the hashing embedder instead of real ML models (this is what CI does)
  - Tests marked `slow` exercise real ML models / live AWS / network and are skipped by default

### Frontend (run from `frontend/`)

- Install: `npm ci`
- Dev server: `npm run dev`
- Typecheck: `npm run typecheck`
- Lint: `npm run lint`
- Test: `npm run test`
- Build: `npm run build`

## Notes

- `requirements-ml.txt` and `requirements-ingest.txt` are optional extras, not part of default CI.
- The AWS demo path (Lambda/Bedrock/S3/CloudFront, see `deploy/README.md`) is merged to `main` but not deployed — it needs the account owner's AWS credentials.
- `fly.toml` deploys a separate, smaller demo-store API build that has no external services attached; don't confuse it with the AWS demo path above.
- CI: `.github/workflows/ci.yml` runs the backend pytest matrix; `.github/workflows/frontend-ci.yml` runs frontend typecheck/lint/test/build. Both trigger on PRs to `main`.
