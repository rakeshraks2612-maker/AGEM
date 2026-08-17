# AGEM Optimization Patch
## Resource: agem-demo-service
## Timestamp: 20260817-105121
## Status: Proposed

### Action
Rightsize Cloud Run service agem-demo-service (scale-to-zero and 512Mi RAM)

### Before Configuration
```yaml
spec.template.spec.containers[0].resources.limits.memory: 4Gi, minScale: 2
```

### After Configuration (Optimized)
```yaml
gcloud run services update agem-demo-service --memory=512Mi --cpu=1 --min-instances=0 --region=us-central1
```

### Estimated Financial Savings
$72.00/month

### Inverse Rollback Command
```bash
gcloud run services update agem-demo-service --memory=4Gi --cpu=2 --min-instances=2 --region=us-central1
```
