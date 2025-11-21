# Kubernetes Deployment Guide for vMiner

## Prerequisites

1. **Kubernetes Cluster** (1.25+)
   - Minimum: 50 nodes (for 1000+ vCenters)
   - Node size: 8 CPU, 32 GB RAM each
   - Total capacity: 400 CPU, 1.6 TB RAM

2. **kubectl** configured and connected to cluster

3. **Helm** (v3+) installed

4. **Storage Class** with SSD support
   ```bash
   kubectl get storageclass
   ```

5. **Ingress Controller** (NGINX recommended)
   ```bash
   helm install ingress-nginx ingress-nginx/ingress-nginx
   ```

6. **Cert-Manager** (for SSL certificates)
   ```bash
   helm install cert-manager jetstack/cert-manager --set installCRDs=true
   ```

## Quick Start

### 1. Create Namespace
```bash
kubectl apply -f kubernetes/deployment.yaml
# This creates the vminer namespace
```

### 2. Update Secrets
Edit the secrets in `deployment.yaml` with base64 encoded values:

```bash
# Generate base64 encoded secrets
echo -n 'your-db-password' | base64
echo -n 'your-secret-key' | base64
echo -n 'your-redis-password' | base64
echo -n 'your-rabbitmq-password' | base64
```

Replace the values in the Secret section of `deployment.yaml`.

### 3. Build and Push Docker Images

#### API Server Image
```bash
# Build
docker build -t your-registry/vminer-api:latest -f kubernetes/Dockerfile.api .

# Push
docker push your-registry/vminer-api:latest
```

#### Sync Worker Image
```bash
# Build
docker build -t your-registry/vminer-sync-worker:latest -f kubernetes/Dockerfile.worker .

# Push
docker push your-registry/vminer-sync-worker:latest
```

### 4. Deploy
```bash
kubectl apply -f kubernetes/deployment.yaml
```

### 5. Verify Deployment
```bash
# Check all pods
kubectl get pods -n vminer

# Check services
kubectl get svc -n vminer

# Check ingress
kubectl get ingress -n vminer
```

## Scaling

### Scale API Servers
```bash
kubectl scale deployment vminer-api --replicas=10 -n vminer
```

### Scale Sync Workers
```bash
kubectl scale deployment vminer-sync-worker --replicas=20 -n vminer
```

### Auto-scaling
Auto-scaling is configured via HorizontalPodAutoscaler:
- API: 5-20 replicas (70% CPU threshold)
- Workers: 10-30 replicas (70% CPU threshold)

## Monitoring

### View Logs
```bash
# API logs
kubectl logs -f deployment/vminer-api -n vminer

# Worker logs
kubectl logs -f deployment/vminer-sync-worker -n vminer

# PostgreSQL logs
kubectl logs -f statefulset/postgresql -n vminer
```

### Resource Usage
```bash
kubectl top pods -n vminer
kubectl top nodes
```

## Production Considerations

### 1. Use Managed Database
Replace the PostgreSQL StatefulSet with managed service:
- AWS: RDS Aurora PostgreSQL
- GCP: Cloud SQL for PostgreSQL
- Azure: Azure Database for PostgreSQL

Update the `PRIMARY_DATABASE_URL` in the deployment.

### 2. Use Managed Redis
Replace Redis StatefulSet with:
- AWS: ElastiCache
- GCP: Memorystore
- Azure: Azure Cache for Redis

### 3. Use Managed Message Queue
Replace RabbitMQ with:
- AWS: Amazon MQ
- GCP: Cloud Pub/Sub
- Azure: Azure Service Bus

### 4. Configure Persistent Volumes
Ensure your storage class supports:
- SSD performance
- Automatic provisioning
- Snapshots/backups

### 5. Set Resource Limits
Adjust resource requests/limits based on your workload:

```yaml
resources:
  requests:
    memory: "4Gi"
    cpu: "2"
  limits:
    memory: "8Gi"
    cpu: "4"
```

## Troubleshooting

### Pods Not Starting
```bash
kubectl describe pod <pod-name> -n vminer
kubectl logs <pod-name> -n vminer
```

### Database Connection Issues
```bash
# Test database connectivity
kubectl run -it --rm debug --image=postgres:15 --restart=Never -n vminer -- \
  psql -h postgresql -U vminer_app -d vminer
```

### Redis Connection Issues
```bash
# Test Redis connectivity
kubectl run -it --rm debug --image=redis:7 --restart=Never -n vminer -- \
  redis-cli -h redis -a <password> ping
```

## Backup and Recovery

### Database Backup
```bash
# Create backup
kubectl exec -it postgresql-0 -n vminer -- \
  pg_dump -U vminer_app vminer > backup_$(date +%Y%m%d).sql

# Restore
kubectl exec -i postgresql-0 -n vminer -- \
  psql -U vminer_app vminer < backup.sql
```

### Volume Snapshots
```bash
# Create snapshot of PostgreSQL volume
kubectl get pvc -n vminer
# Use your cloud provider's snapshot tool
```

## Upgrading

### Rolling Update
```bash
# Update image
kubectl set image deployment/vminer-api api=your-registry/vminer-api:v2.0 -n vminer

# Check rollout status
kubectl rollout status deployment/vminer-api -n vminer

# Rollback if needed
kubectl rollout undo deployment/vminer-api -n vminer
```

## Cost Optimization

1. **Use Spot/Preemptible Instances** for sync workers
2. **Right-size pods** based on actual usage
3. **Enable cluster autoscaler**
4. **Use reserved instances** for predictable workloads

## Security Best Practices

1. **Network Policies**: Already configured in deployment
2. **RBAC**: Configure role-based access control
3. **Pod Security Policies**: Enforce security standards
4. **Secrets Management**: Use external secrets manager (AWS Secrets Manager, etc.)
5. **Image Scanning**: Scan images for vulnerabilities

## Performance Tuning

### PostgreSQL
```yaml
# Add to PostgreSQL container args
args:
  - -c
  - shared_buffers=8GB
  - -c
  - effective_cache_size=24GB
  - -c
  - max_connections=500
```

### Redis
```yaml
# Already configured in deployment
- --maxmemory 30gb
- --maxmemory-policy allkeys-lru
```

## Monitoring Stack (Optional)

Deploy Prometheus and Grafana:

```bash
# Add Prometheus Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

# Install Prometheus
helm install prometheus prometheus-community/kube-prometheus-stack -n monitoring --create-namespace

# Access Grafana
kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring
```

## Support

For issues, check:
1. Pod logs
2. Events: `kubectl get events -n vminer`
3. Resource usage: `kubectl top pods -n vminer`
4. Network policies
5. Ingress configuration
