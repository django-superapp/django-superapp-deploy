
## Databases
### How to do a manual backup
https://access.crunchydata.com/documentation/postgres-operator/latest/tutorials/backups-disaster-recovery/backup-management
```bash
kubectl annotate -n easywindows postgrescluster main-db-pg --overwrite \
  postgres-operator.crunchydata.com/pgbackrest-backup="$(date)"
  ```
### How to restore a backup
https://access.crunchydata.com/documentation/postgres-operator/latest/tutorials/backups-disaster-recovery/disaster-recovery#perform-an-in-place-point-in-time-recovery-pitr
https://pgbackrest.org/command.html#command-restore
- bootstrap a new cluster:
```bash
kubectl patch -n easywindows postgrescluster/main-db-pg --type merge --patch '{"spec":{"datasource": {"postgresCluster": {"clusterName": "main-db-pg", "repoName": "repo2"}}}}'

```
- use `pgbackrest info` on `repo` pod to determine the latest backup name (eg: `20240202-200549F`)
```yaml
kubectl patch -n easywindows postgrescluster/main-db-pg --type merge --patch '{"spec":{"backups": {"pgbackrest": {"restore": {"enabled": true, "repoName": "repo1", "options": ["--type=time", "--target=\"2023-01-25 09:18:04\""]}}}}}'
# or
kubectl patch -n easywindows postgrescluster/main-db-pg --type merge --patch '{"spec":{"backups": {"pgbackrest": {"restore": {"enabled":true, "repoName": "repo2", "options": ["--set=20240721-231502F", "--type=immediate"]}}}}}'
```
- or if you want to restore back to the latest backup:
```yaml
kubectl patch -n easywindows postgrescluster/main-db-pg --type merge --patch '{"spec":{"backups": {"pgbackrest": {"restore": {"enabled":true, "repoName": "repo1", "options": ["--type=immediate"]}}}}}'
```
- trigger restore:
```bash
kubectl annotate -n easywindows postgrescluster main-db-pg --overwrite \
  postgres-operator.crunchydata.com/pgbackrest-restore="$(date)"
```
- from a `.dmp` file:
```bash
DATABASE_URI=postgres://dbuser:aXXXX10.5.100.163:31432/defaultdb
# Make sure all migrations are applied
/opt/homebrew/Cellar/postgresql@16/16.3/bin/pg_restore --verbose --clean -d $DATABASE_URI --schema=public pg-dump-postgres-1717363714.dmp ;
```

### Shutdown a cluster
```kubectl
kubectl patch -n easywindows postgrescluster/main-db-pg --type merge --patch '{"spec":{"shutdown": true}}'
```