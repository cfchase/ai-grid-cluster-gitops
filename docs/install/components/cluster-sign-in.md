# Cluster sign-in and admins

Cluster administrators sign in to the hub and the sites through OpenShift's own identity providers, and the provider
console uses that same sign-in. The library's `cluster-config` component binds `cluster-admin` to the users you list on
every cluster; before you change any identity provider, you add a break-glass admin so you can't lock yourself out.

| | |
|---|---|
| Runs on | hub and every managed cluster |
| Library component | `cluster-config` (select `cluster-config/application.yaml`); the identity providers are infrastructure you provide |
| Choices | Use ours · Bring your own (your own RBAC) |

## Before you start: a break-glass admin

Add a local sign-in next to your cluster's existing identity providers before you install anything that could change
them, on the hub and on each site. If the identity provider you sign in with fails, this one still works. Never delete
an existing identity provider your platform uses.

The example deployment's
[`scripts/add-htpasswd-admin.sh`](https://github.com/cfchase/ai-grid-deployment-proto/blob/main/scripts/add-htpasswd-admin.sh)
does this:

```sh
scripts/add-htpasswd-admin.sh --kubeconfig KUBECONFIG --password-file PASSWORD_FILE
```

Replace the following:

- `KUBECONFIG`: a kubeconfig with a `cluster-admin` session on the cluster.
- `PASSWORD_FILE`: a path outside any git repository for the admin's password. If the file doesn't exist, the script
  generates a password into it (mode `600`) and never prints it.

The script creates Secret `openshift-config/htpasswd-htpasswd`, appends an `HTPasswd` identity provider named
`htpasswd` (`mappingMethod: add`) to OAuth `cluster` while keeping every existing provider, grants `cluster-admin` to
user `admin`, then waits until `admin` can sign in through the new provider. Use `--user` and `--idp` for other names.

## Use ours

1. Add the component to the `files` list in your `root/kustomization.yaml`:

   ```yaml
   - path: cluster-config/application.yaml
   ```

   It reads the `libraryRepoURL`, `libraryRevision`, `deploymentRepoURL` and `deploymentRevision` inputs.

2. Create `values/cluster-admins.yaml` in your deployment repository. It's required:

   ```yaml
   cluster_admins:
     - USERNAME
   ```

   Replace `USERNAME` with each OpenShift user name to bind, such as the break-glass `admin`. For no admins, write
   `cluster_admins: []`. Each name must be a valid DNS-1123 name (lowercase letters, digits, `-` and `.`), because it's
   part of the binding's name; a name such as `user@example.com` isn't supported yet.

3. Commit and push. No Secret is needed.

Argo CD creates ApplicationSet `cluster-config`, which generates one Application per cluster that ACM registered in
Argo CD (label `apps.open-cluster-management.io/acm-cluster=true`, written by `apps/argo-registration`), the hub
included. Each Application renders ClusterRoleBinding `cluster-admin-USERNAME` (`kind: User`) per listed user, and
prunes the binding of a user you remove. On the hub it also creates the `submariner-gateway-nodes` Policy, which labels
every worker-only node `submariner.io/gateway=true` on every cluster. The
[README](../../../cluster-config/README.md) has the details.

### Verify

```sh
oc -n openshift-gitops get applications.argoproj.io \
  -l argocd.argoproj.io/application-set-name=cluster-config
oc get clusterrolebinding cluster-admin-USERNAME
oc --context SITE_CONTEXT get clusterrolebinding cluster-admin-USERNAME
```

Replace `USERNAME` with a listed user and `SITE_CONTEXT` with your kubeconfig context for a site.

You should see one `cluster-config-...` Application per cluster, `Synced` and `Healthy`, and the binding on the hub
and the site.

## Bring your own

If you manage cluster RBAC another way, you still select `cluster-config` for its Submariner gateway node Policy, and
give it `cluster_admins: []`. Your own contract for the admins:

- Each person who installs or operates AI Grid holds `cluster-admin` on the hub and on every site.
- The provider console signs users in with the hub's OpenShift OAuth, so a provider admin needs a hub user that your
  identity provider can sign in.

Check a user:

```sh
oc auth can-i '*' '*' --all-namespaces --as=USERNAME
```

You should see `yes`.

## Skip

You can't skip `cluster-config`: it also labels the Submariner gateway nodes, and Submariner needs at least two
worker-only nodes per cluster. An empty admin list is fine.

## Upgrade

`cluster-config` moves with the library pin with no manual step. The admin list moves with your deployment
repository: adding or removing a name takes effect on every cluster at the next sync.

## Known issues

- **Symptom:** Every cluster's `cluster-config-...` Application fails to sync with a missing values file.
  **Cause:** `values/cluster-admins.yaml` is missing or misnamed. The library fails on purpose instead of rendering no
  binding and pruning every admin.
  **Workaround:** Add the file, with `cluster_admins: []` for none.
- **Symptom:** You lose cluster access after an identity provider change.
  **Cause:** The provider you signed in with no longer works, and no other one does.
  **Workaround:** Sign in with the break-glass `htpasswd` admin, then repair the provider. Without one, recover with
  the installer's `kubeconfig`.
