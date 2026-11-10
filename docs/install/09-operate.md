# Operate

## Upgrade AI Grid

An upgrade is one commit to your deployment repository that moves the library pin.

1. Read the library's commits between your pin and the new one, for anything that needs a new input, values file or
   manual step.

2. In `root/kustomization.yaml`, replace the old SHA with the new one in all three places: the remote base
   (`?ref=`), the generator `revision`, and `values.libraryRevision`.

   ```sh
   sed -i.bak "s/OLD_SHA/NEW_SHA/g" root/kustomization.yaml && rm root/kustomization.yaml.bak
   git -C ../library fetch -q && git -C ../library checkout -q NEW_SHA
   ../library/scripts/check-deployment.sh .
   git commit -am "root: move the library pin to NEW_SHA_SHORT" && git push
   ```

3. Wait for Argo CD. `deployment-root` applies the new root, and every component follows, including the Applications
   that nested ApplicationSets generate on the sites.

   ```sh
   ../library/scripts/check-revisions.sh --deployment . --kubeconfig HUB_KUBECONFIG
   ```

   You should see `0 not at NEW_SHA7`. On the tested hub, 28 library sources moved in about 6 minutes with no manual
   step.

4. Rerun the checks from [step 4](06-join-grid.md#3-verify) and a tenant call from [first use](08-first-use.md#6-call-the-model-as-a-tenant).

Before a pin that changes the Keycloak version, read
[Keycloak](components/keycloak.md#known-issues): Keycloak's import-then-start layout can't migrate
an older database.

## Add a site

Follow [step 3](05-prepare-site.md) and [step 4](06-join-grid.md) for the new site.

## Change a site's role

Change the label: `oc label managedcluster SITE ai-grid/role=NEW_ROLE --overwrite`. Moving to `ingress` or
`combined` needs the site's values file first. Moving an ingress site to `inference` revokes every API key issued
there. *(Unverified.)*

## Remove a site

1. Remove the AI Grid label: `oc label managedcluster SITE ai-grid/enabled-`. Within about 30 seconds the hub
   removes the site's `rhoai`, catalog and policy Applications, and the site's MaaSSubscriptions and MaaSModelRefs; the
   `maas-db` replica goes about 3 minutes later. OpenShift AI and the model servers stay installed, no longer managed,
   and the console shows the site as **Not added**. The site **stays in the grid**: its GridSite remains `Connected`
   and `Available`, and withdrawing it isn't designed yet ([known gaps](appendix-c-gaps.md)). Submariner's
   Application stays until the ManagedCluster goes.

   To add the site back, label it again: on the tested hub all 29 Applications were Synced and Healthy 5½ minutes
   later, with the site's models and subscriptions as before.
2. To remove it from ACM too, delete the ManagedCluster, then any Argo CD cluster Secret and grid identity Secret
   (`redhat-ai-grid/grid-site-SITE`) left on the hub.
3. To reuse the cluster, wipe it ([step 3, part 3](05-prepare-site.md#3-if-the-cluster-ran-ai-grid-before-wipe-it)).

## Rotate credentials

| Credential | How | Verified |
|---|---|---|
| Catalog token | Rerun `apps/console/create-secrets.sh` with the new token file ([provider console](components/console.md)). | No |
| Tenant IdP client secret | Change it in the IdP, then update the hub Secret your `idpClientSecret*` inputs name; the tenant Policy copies it to the sites. | No |
| `quay.io/rhoai` pull secret | Rerun `apps/rhoai-prerequisites/create-hub-secret.sh` ([OpenShift AI prerequisites](components/rhoai-prerequisites.md)). | No |

## Uninstall

Not designed yet ([known gaps](appendix-c-gaps.md)). Removing `deployment-root` or the root ApplicationSet doesn't
remove components: both are set to keep resources when deleted.
