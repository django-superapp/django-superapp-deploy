
1. SSH into Harvester node(`ssh rancher@10.5.100.220`) and run `sudo su`
2. `kubectl apply -f https://raw.githubusercontent.com/iosifnicolae2/experimental-addons/refs/heads/main/rancher-vcluster/rancher-vcluster.yaml`
3. In Harvester, go to Addons then `Edit YAML` for `rancher-vcluster (Experimental)`
4. Fill in the variables:
```yaml
hostname: main-rancher.prod1.bringes.app
rancherVersion: v2.8.2
bootstrapPassword: XXXXXX
cloudflareEmail: iosif@bringes.io
cloudflareApiToken: XXXXXX
```
5. Create a DNS record for `main-rancher.XX.XXXX` to Harvester VIP
6. Login on Rancher and export a kubeconfig file and save it
7. You're done.
8. You can continue with `./setup-kubernetes-cluster.md`
