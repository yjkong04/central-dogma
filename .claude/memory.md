# Project Memory

Durable, repo-local notes for coding agents. Update when project state materially changes; keep entries short.

## Current State

- Product: "Central Dogma" (formerly "PaperLens") — RAG pipeline over biomedical papers.
- The all-AWS demo path (Bedrock + Lambda + S3/CloudFront) is merged to `main` but **not deployed**; it needs the account owner's AWS credentials. See `deploy/README.md` before attempting a deploy.
- `fly.toml` serves a separate, smaller demo-store API build with no external services attached — distinct from the AWS path above.
- CI (`ci.yml`, `frontend-ci.yml`) is green on `main`; backend tests run against the hashing embedder, not real ML models, by default.
