### Cloning the repository
```bash
cd my_superapp;
django_superapp bootstrap-project \
    --template-repo https://github.com/django-superapp/django-superapp-deploy ./deploy;
```


### Quick setup
0. Run `make setup-git-crypt`
0. If you have a git-crypt key palce it in `./secrets/git_crypt.key` and then run `make unlock-git-crypt`
0. If you don't have a git-crypt key, you can generate one using `make generate-git-crypt` to save it in a 1Password note
1. `make install-ci-requirements`
2. create your environment in `./environments/production` from `./environments/sample_environment`
2. setup your `deploy/environments/production/secrets/kube_config.yaml` file
3. `make setup-sealed-secrets`
4. Make sure to setup your secrets in `deploy/environments/production/secrets/config_env.yaml`
  - for registry credentials, please create another Github user and invite it into bringes organization and grant access to the repository
5. `make connect-remote-docker` (optional, if you configure remote docker)
6. `make build-all-docker-images`
7. `make generate-manifests`
8. (optionally, you can deploy using skaffold) `make deploy-using-skaffold`


### Useful Guides
- [Harvester Cluster](./guides/harvester-cluster.md)
- [Hetzner Cluster](./guides/hetzner-cluster.md)
- [Kubernetes Cluster](./guides/kubernetes-cluster.md)
- [Github Runners](./guides/github-runners.md)
- [Deployments](./guides/deployments.md)
- [Databases](./guides/databases.md)
- [Git Crypt](./guides/git-crypt.md)
- [Kubeseal](./guides/kubeseal.md)
- [Longhorn](./guides/longhorn.md)