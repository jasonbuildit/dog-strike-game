#!/usr/bin/env bash
# deploy.sh — Build and deploy dogsonstrike.com to AWS
# Usage: ./deploy.sh
#
# Prerequisites:
#   - AWS CLI configured (aws configure or AWS_* env vars)
#   - Permissions: CloudFormation, S3, CloudFront, ACM, Route53, KMS
#   - Region: us-east-1 (required — CloudFront only accepts ACM certs from us-east-1)

set -euo pipefail

STACK="dogsonstrike-game"
REGION="us-east-1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 1. Deploy / update CloudFormation stack ───────────────────────────────────
echo "▶ Deploying stack: $STACK (region: $REGION)"
echo "  (First deploy: ~15–20 min for ACM cert + CloudFront propagation)"
aws cloudformation deploy \
  --stack-name "$STACK" \
  --template-file "$SCRIPT_DIR/infra.yaml" \
  --region "$REGION" \
  --no-fail-on-empty-changeset

# ── 2. Read outputs ───────────────────────────────────────────────────────────
echo "▶ Reading stack outputs..."
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" \
  --output text)

DIST_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='DistributionId'].OutputValue" \
  --output text)

echo "  Bucket:       s3://$BUCKET"
echo "  Distribution: $DIST_ID"

# ── 3. Sync assets — long cache (1 year immutable) ────────────────────────────
echo "▶ Syncing assets..."
aws s3 sync "$SCRIPT_DIR/assets/" "s3://$BUCKET/assets/" \
  --region "$REGION" \
  --cache-control "public,max-age=31536000,immutable" \
  --delete

# ── 4. Upload HTML — short cache (5 min) so updates propagate quickly ─────────
echo "▶ Uploading dogstrike.html..."
aws s3 cp "$SCRIPT_DIR/dogstrike.html" "s3://$BUCKET/dogstrike.html" \
  --region "$REGION" \
  --cache-control "public,max-age=300" \
  --content-type "text/html; charset=utf-8"

# ── 5. Invalidate CloudFront cache ────────────────────────────────────────────
echo "▶ Invalidating CloudFront cache..."
INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id "$DIST_ID" \
  --paths "/*" \
  --query "Invalidation.Id" \
  --output text)
echo "  Invalidation: $INVALIDATION_ID"

echo ""
echo "✓ Done! https://dogsonstrike.com"
echo "  (Allow ~15 min for CloudFront propagation on first deploy)"
