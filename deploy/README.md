# Deploying the Central Dogma live demo

This runbook stands up the whole live demo — a Lambda-backed API (via a
Function URL, calling Amazon Bedrock for embeddings + generation) and a
CloudFront-fronted static frontend — from the
[`central-dogma`](https://github.com/yjkong04/central-dogma) repo. It's a
single AWS SAM stack (`deploy/template.yaml`) plus one script
(`deploy/frontend-deploy.sh`).

Run every step below from the repo root unless noted otherwise.

## 1. Sign in to AWS

```bash
aws configure          # access key + secret, or...
aws sso login           # ...SSO, if your org uses IAM Identity Center
```

Confirm you're pointed at the right account/region:

```bash
aws sts get-caller-identity
```

## 2. Enable Bedrock model access

The demo calls **Anthropic Claude Haiku 4.5** (generation) and **Amazon
Titan Text Embeddings v2** (embeddings), both in **us-east-1**. Bedrock
model access is opt-in per account/region and is not enabled by default.

In the console: **Bedrock → Model access** (us-east-1) → request/enable
access to:

- `anthropic.claude-haiku-4-5-20251001-v1:0`
- `amazon.titan-embed-text-v2:0`

Access is usually granted instantly. If either model shows anything other
than "Access granted," wait a minute and refresh before deploying — the
Lambda's IAM policy scopes `bedrock:InvokeModel` to exactly these two model
ARNs, so a deploy will succeed but calls will fail with an access-denied
error until this step is done.

Note: generation actually calls the **cross-region inference profile**
`us.anthropic.claude-haiku-4-5-20251001-v1:0`, not the bare on-demand model
id — Claude Haiku 4.5 requires it for on-demand invocation. Enabling model
access for Claude Haiku 4.5 in the console (above) covers this; no separate
opt-in is needed for the inference profile.

## 3. Build and commit the demo corpus

The demo answers questions over a small, pre-embedded corpus baked into the
Lambda image (no vector DB — see `api/config.py` / `FileVectorStore`).
Build it locally (this calls Bedrock for embeddings, so step 2 must be done
first):

```bash
CENTRALDOGMA_EMBEDDER=bedrock CENTRALDOGMA_EMBEDDING_DIM=1024 \
  python -m scripts.build_demo_corpus
```

This writes `api/data/demo_corpus.json`. Commit it — the Lambda container
image is built from the repo, so the corpus needs to be in git before you
`sam build`:

```bash
git add api/data/demo_corpus.json
git commit -m "Add demo corpus for live deploy"
```

## 4. Deploy the backend stack

```bash
cd deploy
sam build
sam deploy --guided
```

`sam deploy --guided` walks you through stack name, region (use
**us-east-1** to match the Bedrock model access from step 2), and confirms
the IAM capabilities the template needs (it creates an execution role for
the Lambda). It saves your answers to `deploy/samconfig.toml` for repeat
deploys (`sam deploy` without `--guided` after the first run).

When it finishes, note the four stack outputs — you'll need all of them:

- **`ApiUrl`** — the Lambda Function URL the frontend calls
- **`SiteBucketName`** — the S3 bucket the static frontend syncs to
- **`SiteUrl`** — the CloudFront URL you'll open at the end
- **`SiteDistributionId`** — the CloudFront distribution id, needed to
  invalidate the cache on each frontend deploy

## 5. Deploy the frontend

From the repo root, using the values from step 4:

```bash
API_URL=<ApiUrl> BUCKET=<SiteBucketName> DIST_ID=<SiteDistributionId> \
  deploy/frontend-deploy.sh
```

This builds the Next.js static export with `NEXT_PUBLIC_API_URL` baked in,
syncs it to S3, and invalidates the CloudFront cache so the new build is
served immediately.

## 6. Set a billing alarm

Before sending real traffic, set a low-threshold billing alarm so an
unexpected spike (or a misconfigured public endpoint) can't run up a
surprise bill silently:

1. Console → **CloudWatch → Alarms → Billing** (or **Alarms → All alarms →
   Create alarm**, metric `AWS/Billing` → `EstimatedCharges`, currency USD).
2. Threshold: **$5**.
3. Notification: an SNS topic that emails you.

(Billing metrics are only published in **us-east-1**, so create the alarm
there regardless of which region you deployed the stack to.)

## 7. Open the demo

Open **`SiteUrl`** (from step 4) in a browser. The frontend calls `ApiUrl`
directly (browser → Lambda Function URL) — no proxy in the loop. CORS is
handled entirely by the app's own `CORSMiddleware` (`api/main.py`), not the
Function URL, so there's a single CORS layer end-to-end.

## Cost note

Everything here is **AWS free-tier / always-free EXCEPT Bedrock tokens**,
which have **no free tier**:

- **Lambda** — 1M requests + 400k GB-s/mo **always free**. Demo traffic is
  far under this → **$0**.
- **CloudFront** — 1 TB/mo egress + 10M requests **always free**. → **$0**.
- **S3** — pennies for a few MB of static assets (free tier for 12 mo; ~$0
  after).
- **ECR** (Lambda image) — 500 MB/mo storage free tier; image is small →
  ~$0.
- **Bedrock** — **pay per token, no free tier.** At demo scale (small
  retrieved context + 1–2 images per call), Claude Haiku 4.5 is on the
  order of **a fraction of a cent per answer**; Titan embeddings are
  ~$0.00002/1k tokens. A few hundred demo answers ≈ **well under $1**.

**Guardrails so a public endpoint can't run up a bill:**

1. **Lambda reserved concurrency = small** (e.g. 2) — caps parallelism and
   blast radius.
2. **Hard daily request cap** in the app (env `CENTRALDOGMA_DEMO_DAILY_CAP`, default
   e.g. 500) — best-effort per warm container; combined with reserved
   concurrency this bounds worst-case spend. (A truly hard cross-instance
   cap would need DynamoDB — deliberately omitted to avoid another service;
   the concurrency + per-container cap + billing alarm is sufficient at
   demo scale.)
3. **Conservative `max_tokens`** on generation.
4. **CloudWatch billing alarm** at a low threshold (e.g. $5) → email if
   anything is off.

**If you want literally $0:** the only non-free piece is Bedrock. Swapping
generation for the CPU **cited-extractive** generator (no LLM) makes it
fully free — but the live demo uses the LLM path for answer quality, so
this stack keeps Bedrock with the caps above. This is the one place
"minimal credits" ≠ "exactly zero."

## Tearing it down

```bash
cd deploy
sam delete
```

This deletes the Lambda, Function URL, CloudFront distribution, and S3
bucket contents created by the stack (empty the bucket first if `sam
delete` complains about a non-empty bucket).
