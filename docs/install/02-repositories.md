# Create your deployment and catalog repositories

Your hub installs from two repositories you own: a **deployment repository** with your choices and inputs, and a
**catalog repository** that the provider console writes models and subscriptions to. Start from the
[example deployment](appendix-b-example.md); this section changes it into yours.

## 1. Create the repositories

1. Create two empty repositories on your git host, for example `my-org/ai-grid-deployment` and
   `my-org/ai-grid-catalog`. Make them readable by the hub's Argo CD.

2. Add a README to the catalog repository, so it has a `main` branch. The console's git writer adds everything else.

   ```sh
   git clone CATALOG_REPO_URL catalog && cd catalog
   echo "# AI Grid catalog: written by the provider console" > README.md
   git add README.md && git commit -m "catalog: start" && git push origin HEAD:main && cd ..
   ```

3. Copy the example deployment into your deployment repository:

   ```sh
   git clone https://github.com/cfchase/ai-grid-deployment-proto.git example
   git clone DEPLOYMENT_REPO_URL deployment
   cp -R example/root example/values example/apps deployment/
   rm -rf deployment/values/clusters/* deployment/apps/*
   ```

   Replace the following:

   - `CATALOG_REPO_URL`: your catalog repository's clone URL.
   - `DEPLOYMENT_REPO_URL`: your deployment repository's clone URL.

   You removed the example's per-site values and its own apps (its tenant IdP and one site's certificate); you add
   your own in later steps. If you'll run your own Keycloak the way the example does, also copy `example/idp` and
   `example/apps/tenant-idp.yaml` ([tenant identity provider](components/tenant-idp.md)).

## 2. Pin the library commit

The root takes the library's `bootstrap/hub` at one commit. Every component then reads the library at that commit.

1. Choose the library commit:

   ```sh
   git ls-remote LIBRARY_REPO_URL refs/heads/LIBRARY_BRANCH
   ```

   Replace `LIBRARY_REPO_URL` and `LIBRARY_BRANCH` with the library's repository and branch. Until the library lands
   upstream, they are `https://github.com/cfchase/ai-grid-cluster-gitops` and `proto/library`.

2. In `deployment/root/kustomization.yaml`, set the full 40-character SHA and the library URL in all three places:
   the remote base (`//bootstrap/hub?ref=SHA`), the generator `revision`, and `values.libraryRevision`; and
   `values.libraryRepoURL` plus the generator `repoURL`.

   ```sh
   cd deployment
   grep -n -e 'ref=' -e 'revision:' -e libraryRevision -e libraryRepoURL root/kustomization.yaml
   ```

   You should see the same SHA on every `ref=`, generator `revision` and `libraryRevision` line.

3. Check out the library at that commit, next to your deployment checkout. The scripts this guide runs come from it,
   so they always match your pin:

   ```sh
   git clone -q LIBRARY_REPO_URL ../library && git -C ../library checkout -q LIBRARY_SHA
   ```

   Replace `LIBRARY_SHA` with the full SHA. After an upgrade, check out the new SHA here too.

## 3. Select components

Your root has three generators. The first is the library's components; the second is ODF (keep it only if you select
ODF); the third, which the example adds, reads your own `apps/*.yaml`. Keep the third: the tenant IdP, site
certificates and any other app of your own go there, and its `repoURL` and `revision` reuse your
`deploymentRepoURL` and `deploymentRevision` values through YAML aliases (generator fields can't take `@NAME@`).

In `root/kustomization.yaml`, the patch that replaces `/spec/generators/0/git/files` is your component list: one
`- path: apps/NAME/application.yaml` line per "use ours" row in your [decision table](README.md#your-choices-component-by-component).
`cluster-config` is the exception: its line is `- path: cluster-config/application.yaml`.

- If you select ODF object storage, keep generator 1 and set its `repoURL`, `revision` and `values` the same way.
  Otherwise keep the example's `remove` of `/spec/generators/1`.
- Your own apps go in `apps/*.yaml` in your deployment repository, one Argo CD Application each; the example's last
  patch adds a generator for them.

## 4. Set every input

The library writes each deployment value as `@NAME@`; your root's `values` set them once. Set all 14 in the `values`
patch (the example uses a YAML anchor, `&inputs`, so its own-apps generator gets the same values).

| Input | Meaning | Example | Read by |
|---|---|---|---|
| `libraryRepoURL` | The library's repository | `https://github.com/cfchase/ai-grid-cluster-gitops.git` | every component (self-references) |
| `libraryRevision` | The pinned commit, a full SHA | `edf8e09fb0de642ff739e0ecbb99605a297035b5` | every component |
| `deploymentRepoURL` | Your deployment repository | `https://github.com/my-org/ai-grid-deployment.git` | `cluster-config`, `grid-bootstrap`, `rhoai` (the `values/` files) |
| `deploymentRevision` | Its branch or commit | `main` | the same |
| `catalogRepoURL` | Your catalog repository | `https://github.com/my-org/ai-grid-catalog.git` | `acm-models`, `console` (git writer) |
| `catalogRevision` | Its branch: the git writer pushes to it, so use a branch | `main` | `acm-models`, `console` |
| `idpIssuerURL` | The tenant OIDC issuer | `https://keycloak-tenant-idp.apps.HUB_DOMAIN/realms/tenants` | `rhoai` (the tenant Policy and the sites' AITenant) |
| `idpClientID` | The tenant client; MaaS matches the token's `azp` against it | `ai-grid-tenants` | `rhoai` |
| `idpClientSecretNamespace` | Namespace of the hub Secret with that client's secret | `tenant-idp-client` | `rhoai` (the tenant Policy) |
| `idpClientSecretName` | That Secret's name | `tenant-idp-client` | `rhoai` (the tenant Policy) |
| `idpClientSecretKey` | Its key | `client-secret` | `rhoai` (the tenant Policy) |
| `idpCANamespace` | Namespace of the hub ConfigMap with the CA that signs the issuer's certificate | `openshift-config-managed` | `rhoai` (the tenant Policy) |
| `idpCAName` | That ConfigMap's name | `default-ingress-cert` | `rhoai` (the tenant Policy) |
| `idpCAKey` | Its key | `ca-bundle.crt` | `rhoai` (the tenant Policy) |

Rules:

- A value must be non-empty and must not contain `"`, `'`, `\` or `@`. Otherwise the root reports
  `invalid input: NAME` and creates no Applications.
- An input you don't set reports `missing input: NAME`.
- A bare render of the library's `bootstrap/hub` shows 33 lines with `REQUIRED-`: these 14 inputs in the `values` of
  both generators (28), the library URL and revision in each generator's own `repoURL` and `revision` (4), and the
  root's own check for leftover markers (1). Every one of the 32 markers is set by the steps in this section.
- If you bring your own tenant identity provider, the `idp*` inputs point at it. If you use ours (`apps/keycloak`),
  use the values its page gives ([tenant identity provider](components/tenant-idp.md)).

## 5. Fill in the values files

Your deployment repository holds three kinds of values file. The library reads them from
`deploymentRepoURL` at `deploymentRevision`.

1. `values/cluster-admins.yaml` (required): the users bound to `cluster-admin` on every cluster.

   ```yaml
   cluster_admins:
     - ADMIN_USER
   ```

   Use `cluster_admins: []` for none. If the file is missing, `cluster-config` fails rather than removing every
   binding ([cluster sign-in and admins](components/cluster-sign-in.md)).

2. `values/grid-bootstrap.yaml`: `Generate` starts a new grid with a new CA; `Existing` keeps a CA you already have
   ([grid bootstrap](components/grid-bootstrap.md)).

   ```yaml
   external:
     certManager:
       ca:
         mode: Generate
   managedClusters:
     createClusterSetBinding: true
   ```

   `createClusterSetBinding: true` is the library's default since commit `8aa65d7`: grid-bootstrap binds the ACM
   ClusterSet `global` into namespace `redhat-ai-grid`, and the root removes the `rhoai` component's copy of that
   binding. Keep the line so the choice is visible in your repository.

3. `values/clusters/SITE/rhoai.yaml`: one per ingress or combined site. You add these in
   [step 4](06-join-grid.md#1-add-the-sites-values), before you label the site.

## 6. Render and push

1. Render the root and check for unset inputs:

   ```sh
   ../library/scripts/check-deployment.sh .
   ```

   You should see `root renders; every input is set; every repository is an input.`

   - `unset inputs:` lists each `REQUIRED-NAME` you still have to set.
   - `repositories that aren't your library, deployment or catalog input:` lists a `repoURL` left over from the
     example, in `root/self.yaml` or `apps/*.yaml`. Change it to your repository, or to `'@deploymentRepoURL@'`.

2. Point `root/self.yaml` (Application `deployment-root`) at your deployment repository: set `spec.source.repoURL`.
   Your own `apps/*.yaml` must use `'@deploymentRepoURL@'` and `'@deploymentRevision@'`, never a literal URL.

3. Commit and push:

   ```sh
   git add -A && git commit -m "deployment: first selection and inputs" && git push origin HEAD:main
   ```

## Checkpoint

- `../library/scripts/check-deployment.sh .` prints `root renders; every input is set; every repository is an input.`
- `root/self.yaml` points at your deployment repository.
- Both repositories are pushed, and the catalog repository has a `main` branch.
