
## Github Runners
### Create a VM with the following cloud configurations:
```yaml
#cloud-config:
package_update: true

packages:
   # Required for Docker
   - apt-transport-https
   - ca-certificates
   - curl
   - gnupg-agent
   - software-properties-common
   - qemu-guest-agent
   - unzip
   - make
   - gh
   - qemu-user-static

ssh_authorized_keys:
   - YOUR_SSH_KEY_HERE

runcmd:
   - - systemctl
     - enable
     - --now
     - qemu-guest-agent.service
   # Steps for Docker
   - curl https://releases.rancher.com/install-docker/26.0.sh | sh
   # I don't need to add this user to the groupRef but I will just in case I ssh in for troubleshooting something
   - usermod -a -G docker ubuntu
```
- install git-crypt:
```bash
sudo su
apt-get update
apt-get install -y openssl libssl-dev gh
wget http://nz2.archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.22_amd64.deb
sudo dpkg -i libssl1.1_1.1.1f-1ubuntu2.22_amd64.deb
wget https://github.com/AGWA/git-crypt/releases/download/0.7.0/git-crypt-0.7.0-linux-x86_64 -O /usr/local/bin/git-crypt
chmod +x /usr/local/bin/git-crypt
```

### Setup multiple Github runners
```bash
sudo su
export REPO=https://github.com/bringes
export REPO_TOKEN=YOUR_TOKEN_HERE
export RUNNER_VERSION=2.322.0
export RUNNER_NAME=organization-dedicated-worker-1
mkdir /actions-runner_$RUNNER_NAME
cd /actions-runner_$RUNNER_NAME
curl -s -O -L https://github.com/actions/runner/releases/download/v$RUNNER_VERSION/actions-runner-linux-x64-$RUNNER_VERSION.tar.gz
tar xzf ./actions-runner-linux-x64-$RUNNER_VERSION.tar.gz
# I need to put RUNNER_ALLOW_RUNASROOT=1 to allow the below to run as rootSection (because that's what happens since the runner is configured & run as part of cloud-init)
# The ubuntu user is not really used except for me to SSH into it if needed
RUNNER_ALLOW_RUNASROOT=1 ./config.sh --name $RUNNER_NAME --url $REPO --token $REPO_TOKEN --unattended
# I used to run the runner immediately but now I want to make it a service so I can reuse the VM and cache later
# RUNNER_ALLOW_RUNASROOT=1 ./run.sh --unattended
RUNNER_ALLOW_RUNASROOT=1 ./svc.sh install
RUNNER_ALLOW_RUNASROOT=1 ./svc.sh start
RUNNER_ALLOW_RUNASROOT=1 ./svc.sh status
chown -R ubuntu /actions-runner_$RUNNER_NAME
```

### Setup Github Actions secrets
0. Create an organization and move the repository there
1. Create a Github account and grant owner access to the repository
2. Create a classic PAT token with `repo`, `workflow`, `write:packages` and `delete:packages`  then name it `ACTIONS_TOKEN`
3. Configure your repository actions environment variables with the following:
```bash
ACTIONS_TOKEN=PAT_TOKEN_HERE
REGISTRY_DOMAIN=ghcr.io
REGISTRY_USERNAME=XXX-team
REGISTRY_PASSWORD=PAT_TOKEN_HERE
GIT_CRYPT_KEY=(run make extract-git-crypt)
```
4. Make sure to set Workflow permissions to read wnd write permissions
5. Create a branch called `production`