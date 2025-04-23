#!/bin/bash
set -e;

file_path="/tmp/install-ci-requirements-version"
install_ci_requirements_version="1"
if [[ -f "$file_path" && $(<"$file_path") == "$install_ci_requirements_version" ]]; then
    echo "install-ci-requirements.sh is already installed. skipping it";
    exit 0;
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKAFFOLD_ROOT_DIR="$SCRIPT_DIR/.."

cd /tmp

# Function to install packages for Linux
install_linux() {
  curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | sudo apt-key add -
    echo "deb https://dl.yarnpkg.com/debian/ stable main" | sudo tee /etc/apt/sources.list.d/yarn.list
  sudo apt-get update;
  sudo apt-get install -y -q make unzip python3 python3-pip yarn parallel jq python3-virtualenv;

  if [ ! -x "/usr/local/bin/yq" ]; then
    curl -Lo yq "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64" && sudo install yq /usr/local/bin/;
  fi

  if [ ! -x "/usr/local/bin/kubectl" ]; then
    curl -Lo kubectl "https://dl.k8s.io/release/v1.27.3/bin/linux/amd64/kubectl" && sudo install kubectl /usr/local/bin/;
  fi

  if [ ! -x "/usr/local/bin/skaffold" ]; then
    curl -Lo skaffold https://storage.googleapis.com/skaffold/releases/latest/skaffold-linux-amd64 && sudo install skaffold /usr/local/bin/;
  fi

  if [ ! -x "/usr/local/bin/git-crypt" ]; then
    curl -Lo git-crypt https://github.com/AGWA/git-crypt/releases/download/0.7.0/git-crypt-0.7.0-linux-x86_64 && sudo install git-crypt /usr/local/bin/;
    wget http://nz2.archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2.22_amd64.deb;
    sudo dpkg -i libssl1.1_1.1.1f-1ubuntu2.22_amd64.deb;
  fi

  curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3;
  chmod 700 get_helm.sh;
  ./get_helm.sh;

  KUBESEAL_VERSION='0.27.0'
  curl -OL "https://github.com/bitnami-labs/sealed-secrets/releases/download/v${KUBESEAL_VERSION:?}/kubeseal-${KUBESEAL_VERSION:?}-linux-amd64.tar.gz"
  tar -xvzf kubeseal-${KUBESEAL_VERSION:?}-linux-amd64.tar.gz kubeseal
  sudo install -m 755 kubeseal /usr/local/bin/kubeseal

  python3 -m pip install --break-system-packages -r"$SKAFFOLD_ROOT_DIR/skaffold_templates/requirements.txt";
}

# Function to install packages for macOS
install_macos() {
    brew update
    brew install make unzip python3 yarn parallel jq yq kubernetes-cli skaffold helm virtualenv kubeseal git-crypt docker-buildx
    mkdir -p ~/.docker/cli-plugins
    ln -sfn $(which docker-buildx) ~/.docker/cli-plugins/docker-buildx
    docker buildx install

    python3 -m pip install --break-system-packages -r"$SKAFFOLD_ROOT_DIR/skaffold_templates/requirements.txt";
}

# Check the OS and call the appropriate function
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected Linux OS"
    install_linux
elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected macOS"
    install_macos
else
    echo "Unsupported OS"
    exit 1
fi

source "$SKAFFOLD_ROOT_DIR/scripts/common-env.sh";


echo "$install_ci_requirements_version" > "$file_path"
