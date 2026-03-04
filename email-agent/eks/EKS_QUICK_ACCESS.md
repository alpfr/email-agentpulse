# Email AgentPulse — EKS Quick Access

## Live URL
```
https://emailaipulse.opssightai.com
```

## Quick Test
```bash
# Health check (bypasses Cognito auth)
curl https://emailaipulse.opssightai.com/health

# Test via direct ALB (replace with actual ALB URL after deploy)
curl http://<ALB_URL>/health
```

## Cluster Info
- **Cluster**: jhb-streampulse-cluster (shared EKS)
- **Namespace**: email-agent
- **Region**: us-east-1
- **Account**: 713220200108

## ECR Images
```
713220200108.dkr.ecr.us-east-1.amazonaws.com/email-agentpulse-backend:latest
713220200108.dkr.ecr.us-east-1.amazonaws.com/email-agentpulse-frontend:latest
```

## Common Commands

### View pods
```bash
kubectl get pods -n email-agent
```

### View logs
```bash
kubectl logs -f deployment/email-agentpulse-backend -n email-agent
kubectl logs -f deployment/email-agentpulse-frontend -n email-agent
```

### Restart deployments
```bash
kubectl rollout restart deployment/email-agentpulse-backend -n email-agent
kubectl rollout restart deployment/email-agentpulse-frontend -n email-agent
```

### Scale
```bash
kubectl scale deployment/email-agentpulse-backend --replicas=3 -n email-agent
```

### View ingress / ALB
```bash
kubectl get ingress -n email-agent
```

### Deploy
```bash
cd email-agent
./eks/deploy.sh              # Full deploy (build + apply)
./eks/deploy.sh --build-only # Build & push images only
./eks/deploy.sh --apply-only # Apply k8s manifests only
```

## Cognito Setup
```bash
# Deploy Cognito user pool via CloudFormation
aws cloudformation deploy \
  --template-file eks/cognito-setup.yaml \
  --stack-name email-agentpulse-cognito \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ApplicationName=email-agentpulse DomainName=emailaipulse.opssightai.com

# Get outputs (User Pool ID, Client ID, Domain)
aws cloudformation describe-stacks --stack-name email-agentpulse-cognito --query 'Stacks[0].Outputs'

# Create admin user
aws cognito-idp admin-create-user \
  --user-pool-id <USER_POOL_ID> \
  --username admin@yourdomain.com \
  --user-attributes Name=email,Value=admin@yourdomain.com Name=name,Value=Admin \
  --temporary-password 'TempPass123!'
```

## DNS Setup
Add a CNAME record for `emailaipulse.opssightai.com` pointing to the ALB DNS name:
```
emailaipulse.opssightai.com → <ALB_DNS_NAME>
```
