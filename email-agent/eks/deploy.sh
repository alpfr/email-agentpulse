#!/bin/bash
# ============================================================
# Email AgentPulse — EKS Deployment Script
# ============================================================
# Builds Docker images, pushes to ECR, and applies K8s manifests.
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - kubectl configured for the EKS cluster
#   - Docker running
#
# Usage:
#   ./eks/deploy.sh              # Full deploy
#   ./eks/deploy.sh --build-only # Build & push images only
#   ./eks/deploy.sh --apply-only # Apply k8s manifests only
# ============================================================

set -euo pipefail

# Configuration
AWS_ACCOUNT_ID="713220200108"
AWS_REGION="us-east-1"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
BACKEND_IMAGE="${ECR_REGISTRY}/email-agent-backend"
FRONTEND_IMAGE="${ECR_REGISTRY}/email-agent-frontend"
NAMESPACE="email-agent"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[deploy]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }

# Parse args
BUILD=true
APPLY=true
if [[ "${1:-}" == "--build-only" ]]; then APPLY=false; fi
if [[ "${1:-}" == "--apply-only" ]]; then BUILD=false; fi

# ---- Build & Push ----
if $BUILD; then
    log "Authenticating with ECR..."
    aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

    # Create ECR repos if they don't exist
    for repo in email-agent-backend email-agent-frontend; do
        aws ecr describe-repositories --repository-names "$repo" --region "$AWS_REGION" 2>/dev/null || \
        aws ecr create-repository --repository-name "$repo" --region "$AWS_REGION" --image-scanning-configuration scanOnPush=true
    done

    log "Building backend image..."
    docker build -t "$BACKEND_IMAGE:latest" "$PROJECT_DIR"

    log "Building frontend image..."
    docker build -t "$FRONTEND_IMAGE:latest" "$PROJECT_DIR/dashboard"

    log "Pushing images to ECR..."
    docker push "$BACKEND_IMAGE:latest"
    docker push "$FRONTEND_IMAGE:latest"

    log "Images pushed successfully."
fi

# ---- Apply K8s Manifests ----
if $APPLY; then
    K8S_DIR="$PROJECT_DIR/k8s"

    log "Applying Kubernetes manifests to namespace '${NAMESPACE}'..."

    # Apply in dependency order
    kubectl apply -f "$K8S_DIR/namespace.yaml"
    kubectl apply -f "$K8S_DIR/configmap.yaml"
    kubectl apply -f "$K8S_DIR/secret.yaml"
    kubectl apply -f "$K8S_DIR/backend-deployment.yaml"
    kubectl apply -f "$K8S_DIR/frontend-deployment.yaml"
    kubectl apply -f "$K8S_DIR/ingress.yaml"
    kubectl apply -f "$K8S_DIR/hpa.yaml"

    log "Waiting for rollout..."
    kubectl rollout status deployment/email-agent-backend -n "$NAMESPACE" --timeout=120s
    kubectl rollout status deployment/email-agent-frontend -n "$NAMESPACE" --timeout=120s

    log "Deployment complete!"
    echo ""
    echo -e "${BLUE}--- Status ---${NC}"
    kubectl get pods -n "$NAMESPACE"
    echo ""
    kubectl get ingress -n "$NAMESPACE"
    echo ""
    log "DNS: https://emailaipulse.opssightai.com"
fi
