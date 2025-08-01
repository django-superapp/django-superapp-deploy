#!/bin/bash

set -e;
set -m  # Enable job control

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKAFFOLD_ROOT_DIR="$SCRIPT_DIR/.."

source "$SKAFFOLD_ROOT_DIR/scripts/common-env.sh";

bash "$SKAFFOLD_ROOT_DIR/scripts/generate-skaffolds.sh";

echo "Deleting old manifests..";
rm -rf "$GENERATED_MANIFESTS_DIR";
mkdir "$GENERATED_MANIFESTS_DIR";
cd "$GENERATED_MANIFESTS_DIR";

echo "Copying values files for Fleet-only components..";
cd "$GENERATED_SKAFFOLD_DIR";

# Copy values files for Fleet-only components that reference git charts
for d in */ ; do
  cd "$d" || continue
  
  # Check if this is a Fleet-only component (has fleet.yaml with git URL and values files)
  if [ -e "fleet.yaml" ] && grep -q 'chart: git@' fleet.yaml 2>/dev/null && grep -q 'valuesFiles:' fleet.yaml 2>/dev/null; then
    echo "Copying values files for Fleet-only component: $d"
    mkdir -p "$GENERATED_MANIFESTS_DIR/$d"
    
    # Copy the fleet.yaml file
    cp fleet.yaml "$GENERATED_MANIFESTS_DIR/$d/"
    
    # Copy all values files (typically *.yaml files except fleet.yaml and skaffold*.yaml)
    for values_file in *.yaml; do
      if [ "$values_file" != "fleet.yaml" ] && [ "$values_file" != "skaffold.yaml" ] && [[ "$values_file" != skaffold-*.yaml ]]; then
        if [ -f "$values_file" ]; then
          cp "$values_file" "$GENERATED_MANIFESTS_DIR/$d/"
          echo "Copied $values_file to $GENERATED_MANIFESTS_DIR/$d/"
        fi
      fi
    done
  fi
  
  cd ..
done

cd "$GENERATED_MANIFESTS_DIR";

echo "Rendering skaffolds..";
cd "$GENERATED_SKAFFOLD_DIR";

# Helper function to extract namespace from skaffold config files
function extract_namespace_from_skaffold {
  local extracted_ns=""
  
  # Function to extract namespace from a single file
  extract_from_file() {
    local file="$1"
    local ns=""
    
    # Try defaultNamespace first
    ns=$(yq eval '.deploy.kubectl.defaultNamespace // ""' "$file" 2>/dev/null)
    
    # If not found, try helm releases namespace
    if [ -z "$ns" ] || [ "$ns" = "null" ]; then
      ns=$(yq eval '.manifests.helm.releases[0].namespace // ""' "$file" 2>/dev/null)
    fi
    
    # Filter out null and empty values
    if [ "$ns" = "null" ] || [ -z "$ns" ]; then
      ns=""
    fi
    
    echo "$ns"
  }
  
  # First check main skaffold.yaml
  if [ -e "skaffold.yaml" ]; then
    extracted_ns=$(extract_from_file "skaffold.yaml")
  fi
  
  # If not found in main file, check skaffold-*.yaml files
  if [ -z "$extracted_ns" ]; then
    for skaffold_file in skaffold-*.yaml; do
      if [ -f "$skaffold_file" ]; then
        extracted_ns=$(extract_from_file "$skaffold_file")
        [ -n "$extracted_ns" ] && break
      fi
    done
  fi
  
  # If still not found, try to extract from fleet.yaml
  if [ -z "$extracted_ns" ] && [ -f "fleet.yaml" ]; then
    extracted_ns=$(yq eval '.diff.comparePatches[0].namespace // .diff.comparePatches[1].namespace // ""' "fleet.yaml" 2>/dev/null)
    # Filter out null and empty values
    if [ "$extracted_ns" = "null" ] || [ -z "$extracted_ns" ]; then
      extracted_ns=""
    fi
  fi
  
  # If still not found, try to extract from manifests.yaml (for namespace components)
  if [ -z "$extracted_ns" ] && [ -f "manifests.yaml" ]; then
    # Check if this is a namespace manifest itself
    kind=$(yq eval '.kind // ""' "manifests.yaml" 2>/dev/null)
    if [ "$kind" = "Namespace" ]; then
      extracted_ns=$(yq eval '.metadata.name // ""' "manifests.yaml" 2>/dev/null)
    else
      # Try to extract namespace from any resource metadata (take first non-empty value)
      extracted_ns=$(yq eval '.metadata.namespace // ""' "manifests.yaml" 2>/dev/null | grep -v '^$' | grep -v '^null$' | head -1)
    fi
    # Filter out null and empty values
    if [ "$extracted_ns" = "null" ] || [ -z "$extracted_ns" ]; then
      extracted_ns=""
    fi
  fi
  
  # Last resort: try to extract namespace from service references in manifests.yaml
  if [ -z "$extracted_ns" ] && [ -f "manifests.yaml" ]; then
    # Look for service references like "service.namespace:port" in the file
    extracted_ns=$(grep -oE "\.radio-crestin-[a-zA-Z0-9_-]+:" "manifests.yaml" 2>/dev/null | head -1 | sed 's/^\.//;s/:$//' || echo "")
    # Filter out empty values
    if [ -z "$extracted_ns" ]; then
      extracted_ns=""
    fi
  fi
  
  # Final fallback: look for namespace manifests in subdirectories
  if [ -z "$extracted_ns" ]; then
    # Find Namespace kind manifest files in subdirectories
    for subdir in */ ; do
      if [ -d "$subdir" ]; then
        namespace_file=$(find "$subdir" -name "*-Namespace.yml" -o -name "*Namespace.yaml" 2>/dev/null | head -1)
        if [ -n "$namespace_file" ] && [ -f "$namespace_file" ]; then
          kind=$(yq eval '.kind // ""' "$namespace_file" 2>/dev/null)
          if [ "$kind" = "Namespace" ]; then
            extracted_ns=$(yq eval '.metadata.name // ""' "$namespace_file" 2>/dev/null)
            # Filter out null and empty values
            if [ "$extracted_ns" != "null" ] && [ -n "$extracted_ns" ]; then
              break
            else
              extracted_ns=""
            fi
          fi
        fi
      fi
    done
  fi
  
  echo "$extracted_ns"
}

function render_skaffold {
  local d=$1
  local tmpfile=$2

  cd "$d" || exit 1
  echo "Rendering skaffold for $d"
  mkdir -p "$GENERATED_MANIFESTS_DIR/$d"
  cp fleet.yaml "$GENERATED_MANIFESTS_DIR/$d"

  # Extract namespace from skaffold config files
  extracted_ns=$(extract_namespace_from_skaffold)
  
  # Use extracted namespace or exit with error if not found
  if [ -n "$extracted_ns" ]; then
    export NS="$extracted_ns"
    echo "Using extracted namespace: $NS for $d"
  else
    echo "Error: No namespace found in skaffold configuration for $d"
    exit 1
  fi

  if [ -e "skaffold.yaml" ]; then
    if ! skaffold render \
      --offline=true \
      --sync-remote-cache='never' \
      --digest-source='tag' \
      --tag="$IMAGES_TAG" \
      --filename='skaffold.yaml' \
      --verbosity='debug' \
      --output="$GENERATED_MANIFESTS_DIR/$d/manifests.yaml" > "$tmpfile" 2>&1; then

      echo "┌─────────────────────────────────────────────────────────────────┐"
      echo "│                       SKAFFOLD ERROR                            │"
      echo "└─────────────────────────────────────────────────────────────────┘"
      echo -e "\033[1;31mError rendering skaffold for directory: \033[1;33m$d\033[0m"
      echo -e "\033[1;31m──────────────────── ERROR DETAILS ────────────────────\033[0m"
      cat "$tmpfile"
      echo -e "\033[1;31m──────────────────── END OF ERROR ────────────────────\033[0m"
      return 1
    fi
  fi
  cd ..
}

export -f extract_namespace_from_skaffold  # Export the helper function
export -f render_skaffold  # Export the function to be used by subshells

pids=()  # Array to hold process IDs
tmpfiles=()  # Array to hold temporary file paths

for d in */ ; do
  tmpfile=$(mktemp)  # Create a temporary file
  tmpfiles+=("$tmpfile")
  render_skaffold "$d" "$tmpfile" &
  pids+=($!)  # Collect the PID of the background job
done

# Track if any process failed
failed=false

for i in "${!pids[@]}"; do
  pid=${pids[$i]}
  tmpfile=${tmpfiles[$i]}

  if ! wait "$pid"; then
    failed=true
    # Error is already printed by the render_skaffold function
  else
    # Only remove tmpfile if successful
    rm -f "$tmpfile"
  fi
done

if [ "$failed" = true ]; then
  echo -e "\033[1;31m┌─────────────────────────────────────────────────────────────────┐\033[0m"
  echo -e "\033[1;31m│                  MANIFEST GENERATION FAILED                     │\033[0m"
  echo -e "\033[1;31m└─────────────────────────────────────────────────────────────────┘\033[0m"
  exit 1
else
  echo -e "\033[1;32m✓ All skaffold render processes completed successfully.\033[0m"
fi
sync;

cd "$GENERATED_MANIFESTS_DIR";

if [ -z "$KUBESEAL_CERT" ]; then
  echo -e "\033[1;31m┌─────────────────────────────────────────────────────────────────┐\033[0m"
  echo -e "\033[1;31m│                         ERROR                                   │\033[0m"
  echo -e "\033[1;31m└─────────────────────────────────────────────────────────────────┘\033[0m"
  echo -e "\033[1;31mSecrets can't be sealed, KUBESEAL_CERT environment variable is missing.\033[0m"
  echo -e "\033[1;33mPlease set the KUBESEAL_CERT environment variable before running this script.\033[0m"
  exit 1;
else
  export KUBESEAL_CERTIFICATE_PATH="/tmp/kubeseal-cert.pem";
  echo "$KUBESEAL_CERT" > "$KUBESEAL_CERTIFICATE_PATH";
fi

# Function to handle errors
handle_error() {
  echo -e "\033[1;31m┌─────────────────────────────────────────────────────────────────┐\033[0m"
  echo -e "\033[1;31m│                     PROCESSING ERROR                            │\033[0m"
  echo -e "\033[1;31m└─────────────────────────────────────────────────────────────────┘\033[0m"
  echo -e "\033[1;31mAn error occurred while processing directory: $1\033[0m"
  echo -e "\033[1;31mCommand failed: $2\033[0m"
  exit 1
}

for d in */ ; do
  cd "$d" || handle_error "$d" "cd $d"
  echo "Processing $d";
  
  # Extract namespace from skaffold config files
  extracted_ns=$(extract_namespace_from_skaffold)
  
  # Use extracted namespace or exit with error if not found
  if [ -n "$extracted_ns" ]; then
    export NS="$extracted_ns"
    echo "Using extracted namespace: $NS for processing $d"
  else
    echo "Error: No namespace found in skaffold configuration for processing $d"
    exit 1
  fi

  if [ -e "manifests.yaml" ] && [ -s "manifests.yaml" ] && yq eval '.metadata.name' manifests.yaml 2>/dev/null | grep -v '^---$' | grep -v '^null$' | grep -q .; then
        #  cp manifests.yaml manifests.yaml.bak;

        echo "Deleting empty manifests elements..";
        yq eval --inplace 'del(. | select(. == null or . == ""))' manifests.yaml || handle_error "$d" "yq delete empty elements"

        echo "Adding namespace value in each manifest file..";
        yq eval --inplace "select((.metadata.namespace == \"\" or .metadata.namespace == null) and .kind != \"CustomResourceDefinition\" and .kind != \"MutatingWebhookConfiguration\" and .kind != \"ValidatingWebhookConfiguration\" and .kind != \"ClusterRoleBinding\" and .kind != \"Namespace\" and \"$NS\" != \"\") |= .metadata.namespace = \"$NS\"" manifests.yaml || handle_error "$d" "yq add namespace"
        sync;

        echo "Creating manifests subdirectories..";
        # Capture the output in a variable to check if it's empty
        names=$(yq eval '.metadata.labels["app.kubernetes.io/instance"] // .metadata.labels["release"] // .metadata.name' manifests.yaml | grep -v '^---$' | awk '!seen[$0]++')
        if [ -z "$names" ]; then
          echo -e "\033[1;33mWarning: No manifest names found in $d\033[0m"
        else
          for name in $names; do
            mkdir -p "$name" || handle_error "$d" "mkdir -p $name"
          done
        fi

        echo "Replacing wrong apiVersions..";
        names=$(yq eval '.metadata.labels["app.kubernetes.io/instance"] // .metadata.labels["release"] // .metadata.name' manifests.yaml | grep -v '^---$' | awk '!seen[$0]++')
        if [ -n "$names" ]; then
          for name in $names; do
            perl -i -pe 's/apiVersion: apiregistration.k8s.io\/v1beta1/apiVersion: apiregistration.k8s.io\/v1/g' manifests.yaml || handle_error "$d" "perl replace apiVersions"
          done
        fi

        sync;

        echo "Splitting manifest files..";
        yq --split-exp '(.metadata.labels["app.kubernetes.io/instance"] // .metadata.labels["release"] // .metadata.name)  + "/" + (.metadata.name) + "-" + .kind' --no-doc manifests.yaml || handle_error "$d" "yq split manifest files"
        sync;

        echo "Sealing secrets..."
        # Use a temporary file to capture any errors from the find command
        error_file=$(mktemp)

        # Set a trap to ensure the error file is removed
        trap 'rm -f "$error_file"' EXIT

        echo "Sealing secrets in $d"

        # Use set -e inside the bash script to ensure it exits on any error
        if ! find . -type f -iname '*secret*' -exec bash -c '
          set -e
          if ! kubeseal -f "$1" --allow-empty-data --scope namespace-wide --cert "$2" -w "$1.sealed.yml" 2>/tmp/kubeseal_error; then
            echo -e "\033[1;31m┌─────────────────────────────────────────────────────────────────┐\033[0m"
            echo -e "\033[1;31m│                     KUBESEAL ERROR                              │\033[0m"
            echo -e "\033[1;31m└─────────────────────────────────────────────────────────────────┘\033[0m"
            echo -e "\033[1;31mFailed to seal secret: $1\033[0m"
            echo -e "\033[1;31m──────────────────── ERROR DETAILS ────────────────────\033[0m"
            cat /tmp/kubeseal_error
            echo -e "\033[1;31m──────────────────── END OF ERROR ────────────────────\033[0m"
            exit 1
          else
            rm "$1"
          fi
        ' -- {} "$KUBESEAL_CERTIFICATE_PATH" \; 2>"$error_file"; then
          echo -e "\033[1;31m┌─────────────────────────────────────────────────────────────────┐\033[0m"
          echo -e "\033[1;31m│                     SECRET SEALING ERROR                        │\033[0m"
          echo -e "\033[1;31m└─────────────────────────────────────────────────────────────────┘\033[0m"
          echo -e "\033[1;31mAn error occurred while sealing secrets:\033[0m"
          cat "$error_file"
          rm -f "$error_file"
          exit 1
        fi

        rm -f "$error_file"

        rm manifests.yaml;
        sync;
  else
    echo "Skipping manifest processing for $d (no manifests or Fleet-only component)";
    # Clean up empty or invalid manifests.yaml if it exists
    [ -e "manifests.yaml" ] && rm -f manifests.yaml
  fi;


  cd ..;
done

rm -rf $KUBESEAL_CERTIFICATE_PATH

sync;
cd "$SKAFFOLD_ROOT_DIR" || exit 1;
echo -e "\033[1;32m┌─────────────────────────────────────────────────────────────────┐\033[0m"
echo -e "\033[1;32m│                MANIFEST GENERATION COMPLETED                    │\033[0m"
echo -e "\033[1;32m└─────────────────────────────────────────────────────────────────┘\033[0m"
echo -e "\033[1;32m✓ All manifests have been successfully generated and processed.\033[0m"
