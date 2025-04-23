
## Deploy the project
### How to deploy the project?
1. Open Rancher and go to `Continous Delivery`
2. Click on `Git Repos` and create a new repo with the following details:
    - Name: `<project_name>-common`
    - Watch Branch: `main/master`
    - Repository URL: `git@github.com:your-organization/your-project`
    - Git Authentication (create a deploy key and paste the private key here)
    - Paths: the content of `common_git_repo_paths.yaml[common_repo_paths.yaml](..%2Fenvironments%2Feasywindows%2Fgenerated_outputs%2Fgenerated_manifests%2Fcommon_repo_paths.yaml)`
    - enable Self-Healing
3. Click `Next` and then select your cluster in `Deploy To` section.
4. Click on `Git Repos` and create a new repo with the following details:
    - Name: `<project_name>`
    - Watch Branch: `production`
    - Repository URL: `git@github.com:your-organization/your-project`
    - Git Authentication (create a deploy key on `bridge-<env_name>-manifests` and paste the private key here)
    - Paths: the content of `git_repo_paths.yaml[main_repo_paths.yaml](..%2Fenvironments%2Feasywindows%2Fgenerated_outputs%2Fgenerated_manifests%2Fmain_repo_paths.yaml)`
5. Click `Next` and then select your cluster in `Deploy To` section.
6. You're done. If a deployment fails, you can click on `Force update` after opening settings of selected Git Repo.