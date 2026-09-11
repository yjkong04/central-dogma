#!/usr/bin/env bash
set -euo pipefail
# Usage: API_URL=<lambda-fn-url> BUCKET=<site-bucket> DIST_ID=<cloudfront-id> deploy/frontend-deploy.sh
cd "$(dirname "$0")/../frontend"
NEXT_PUBLIC_API_URL="${API_URL}" npm run build
aws s3 sync out/ "s3://${BUCKET}/" --delete
aws cloudfront create-invalidation --distribution-id "${DIST_ID}" --paths "/*"
echo "frontend deployed"
