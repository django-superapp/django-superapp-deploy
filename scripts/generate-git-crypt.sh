#!/bin/bash
set -e;

git-crypt export-key - | base64 > ./secrets/git_crypt.key

echo "The git-crypt key has been generated and saved to ./secrets/git_crypt.key"
