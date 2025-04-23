#!/bin/bash
set -e;

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
export SKAFFOLD_ROOT_DIR=$(realpath "$SCRIPT_DIR/..")

# Install Helm dependencies from all components
echo "Installing Helm dependencies..."
find "$SKAFFOLD_ROOT_DIR/components" -name "helm_dependencies.yaml" | while read -r dependency_file; do
  echo "Processing $dependency_file"
  if [ -f "$dependency_file" ]; then
    component_dir=$(dirname "$dependency_file")
    component_name=$(basename "$component_dir")
    echo "Installing Helm dependencies for $component_name"
    
    # Parse the YAML file and add repositories
    if command -v yq >/dev/null 2>&1; then
      # If yq is available, use it to parse YAML
      yq eval '.repositories[] | .name + " " + .url' "$dependency_file" | while read -r repo_info; do
        repo_name=$(echo "$repo_info" | cut -d' ' -f1)
        repo_url=$(echo "$repo_info" | cut -d' ' -f2-)
        echo "Adding Helm repository: $repo_name - $repo_url"
        helm repo add "$repo_name" "$repo_url" || true
      done
    else
      # Fallback to grep and awk if yq is not available
      grep -A2 "name:" "$dependency_file" | while read -r line; do
        if [[ "$line" == *"name:"* ]]; then
          repo_name=$(echo "$line" | awk '{print $2}')
        elif [[ "$line" == *"url:"* ]]; then
          repo_url=$(echo "$line" | awk '{print $2}')
          echo "Adding Helm repository: $repo_name - $repo_url"
          helm repo add "$repo_name" "$repo_url" || true
        fi
      done
    fi
  fi
done

# Update all Helm repositories
helm repo update

# Detect environment from the current directory or use default
CURRENT_ENV=$(basename $(find "$SKAFFOLD_ROOT_DIR/environments" -type d -mindepth 1 -maxdepth 1 | head -1))

# Use the detected environment
cd "$SKAFFOLD_ROOT_DIR/environments/$CURRENT_ENV";
python3 main.py;
cd "$SKAFFOLD_ROOT_DIR";
