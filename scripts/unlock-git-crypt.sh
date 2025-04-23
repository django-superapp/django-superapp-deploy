#!/bin/bash
set -e;

cat ./secrets/git_crypt.key | base64 -d > /tmp/git-crypt-key

git-crypt unlock /tmp/git-crypt-key

rm /tmp/git-crypt-key
