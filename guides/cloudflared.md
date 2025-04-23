## CloudflareD in Harvester
1. Create a tunnel in Cloudflare Zero Trust
Deploy the following yaml
```
kubectl apply -f - <<EOF
apiVersion: harvesterhci.io/v1beta1
kind: Addon
metadata:
  name: cloudflare-tunnel-remote
  namespace: harvester-system
spec:
  enabled: true
  repo: https://cloudflare.github.io/helm-charts
  version: 0.1.2
  chart: cloudflare-tunnel-remote
  valuesContent: |-
    cloudflare:
      tunnel_token: "XXXXX"
EOF

```