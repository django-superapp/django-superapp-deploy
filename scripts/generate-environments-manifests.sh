#!/bin/bash

set -e;

environments=$(find environments -mindepth 2 -maxdepth 2 -type f -name Makefile -print | xargs -I {} dirname {})

# Iterate over each directory and run 'make generate-manifests'
for dir in $environments; do
  echo "Generating manifests for: $dir"
  (
    cd "$dir" && make generate-manifests
  )
done
