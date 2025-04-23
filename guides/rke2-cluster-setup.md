# RKE2 Cluster Setup Guide

A quick guide to set up an RKE2 Kubernetes cluster with the built-in ingress-nginx disabled.

## Server Node Setup

1. **Disable built-in ingress-nginx** (Optional):
```bash
sudo mkdir -p /etc/rancher/rke2/
sudo cat > /etc/rancher/rke2/config.yaml << EOF
disable:
  - rke2-ingress-nginx
EOF
```

2. **Install and start RKE2 server**:
   ```bash
   curl -sfL https://get.rke2.io | sudo sh -
   sudo systemctl enable rke2-server.service
   sudo systemctl start rke2-server.service
   ```

3. **Get node token** (needed for adding worker nodes):
   ```bash
   cat /var/lib/rancher/rke2/server/node-token
   ```

## Worker Node Setup

1. **Install RKE2 agent**:
   ```bash
   curl -sfL https://get.rke2.io | INSTALL_RKE2_TYPE="agent" sh -
   ```

2. **Configure agent**:
   ```bash
   sudo mkdir -p /etc/rancher/rke2/
   sudo cat > /etc/rancher/rke2/config.yaml << EOF
   server: https://<SERVER_IP>:9345
   token: <TOKEN_FROM_SERVER_NODE>
   EOF
   ```

3. **Start agent**:
   ```bash
   sudo systemctl enable rke2-agent.service
   sudo systemctl start rke2-agent.service
   ```

## Access Cluster

Configure kubectl access:
```bash
export KUBECONFIG=/etc/rancher/rke2/rke2.yaml
# Or copy to user directory:
mkdir -p ~/.kube
sudo cp /etc/rancher/rke2/rke2.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
```
