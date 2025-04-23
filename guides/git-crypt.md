### Lock git-crypt
1. `cd ./deploy/environments/<your-env>`
2. `make setup-git-crypt`
3. `make extract-git-crypt` and then save it in a 1Password note

### Unlock git-crypt
1. Copy the git-crypt key from 1Password
2. `cd deploy && make unlock-git-crypt`