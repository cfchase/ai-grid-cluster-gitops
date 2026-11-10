# Provider console

This component runs the cloud provider's admin console and its backend on the hub, in one pod with an OpenShift
sign-in proxy. Provider admins use it to add clusters to the grid, create organizations in Keycloak, and deploy models
and subscriptions as commits to the catalog repository, which [model delivery](./model-delivery.md) delivers and
[AI Grid Policies](./ai-grid-policies.md) report on.

| | |
|---|---|
| Runs on | hub |
| Library component | `apps/console` (select `apps/console/application.yaml`) |
| Choices | Use ours. Bring your own isn't an option. Skip: yes, see [Skip](#skip). |
| Requires | `apps/acm-models`; a **Keycloak** tenant IdP with Organizations. With any other OIDC provider, skip the console. |

## Use ours

1. Add the component to the root's `files` list:

   ```yaml
   - path: apps/console/application.yaml
   ```

   It reads the inputs `catalogRepoURL`, `catalogRevision`, `libraryRepoURL` and `libraryRevision`. It installs the
   console's Helm chart from `ai-grid-cloud/ai-grid-provider-console` at a pinned commit, with images by digest, into
   namespace `ai-grid-provider-console`, and binds the backend to ACM Search and to Policy
   `ai-grid-policies/ai-grid-ready`.

2. Create a fine-grained GitHub token with **Contents: Read and write** on the catalog repository only, and save it
   to a file outside any repository. Whoever holds this token can change every site's models and subscriptions. Never
   give it access to your deployment repository or the library: Argo CD applies those with cluster-admin rights.

3. Wait until Argo CD has created the console's Route:

   ```sh
   oc -n ai-grid-provider-console get route ai-grid-provider-console
   ```

4. As a hub cluster-admin, from a checkout of the library at your pinned commit, create the console's Secrets:

   ```sh
   AI_GRID_GIT_TOKEN_FILE=TOKEN_FILE \
   KEYCLOAK_NAMESPACE=KEYCLOAK_NAMESPACE KEYCLOAK_REALM=KEYCLOAK_REALM \
     bash apps/console/create-secrets.sh
   ```

   Replace the following:

   - `TOKEN_FILE`: the path to the token file from step 2. Required.
   - `KEYCLOAK_NAMESPACE`: the hub namespace that holds your Keycloak's Route `keycloak` and Secret `keycloak-secrets`.
     Defaults to `maas-db`, where the library's Keycloak runs.
   - `KEYCLOAK_REALM`: the realm whose organizations the console manages. Defaults to `saas`, the library's realm.

   Other optional variables: `HUB_CONTEXT` (kubeconfig context), `NAMESPACE` (defaults to
   `ai-grid-provider-console`), `KEYCLOAK_BACKEND_USER` (defaults to `ai-grid-console-backend`),
   `KEYCLOAK_BACKEND_URL` (defaults to Keycloak's public Route), `ADOPT_KEYCLOAK_USER_ID`, and `CURL_CA_BUNDLE` for
   a Keycloak Route behind a private CA. The script prints no secret value and is safe to rerun.

   The script creates or updates, in `ai-grid-provider-console`:

   - OAuthClient `ai-grid-provider-console` and Secret `ai-grid-provider-console-oauth`: OpenShift sign-in.
   - Secret `ai-grid-backend-keycloak`: the backend's Keycloak URL, realm, user and password. The script creates that
     Keycloak user in the realm with only the realm-management roles it needs, signing in with the admin login in
     `KEYCLOAK_NAMESPACE/keycloak-secrets`.
   - Secret `ai-grid-backend-git`: the catalog token.

   Then it restarts the console. The [README](../../../apps/console/README.md) explains the Keycloak user and the
   private-CA options.

5. Sign in at the Route's URL with an OpenShift user that may patch ManagedClusters, such as a cluster-admin. Provider
   admins sign in with OpenShift users, not with tenant IdP accounts.

### Verify

On the hub:

```sh
oc -n ai-grid-provider-console get pods
oc -n ai-grid-provider-console get route ai-grid-provider-console -o jsonpath='{.spec.host}{"\n"}'
oc -n ai-grid-provider-console get secrets \
  ai-grid-provider-console-oauth ai-grid-backend-keycloak ai-grid-backend-git
```

You should see one pod `3/3 Running` (sign-in proxy, console and backend), the console's host name, and the three
Secrets. Open `https://HOST` and sign in; the **Clusters** page lists your ManagedClusters, each site Provisioning or
Provisioned.

## Bring your own

Not an option: the library has no contract for another console. The console works only with Keycloak: it creates
organizations through Keycloak's admin API. With a tenant IdP that isn't Keycloak, skip the console. You choose which
Keycloak: the console works with any Keycloak that has a Route named `keycloak` and a Secret `keycloak-secrets` with keys `KC_BOOTSTRAP_ADMIN_USERNAME`
and `KC_BOOTSTRAP_ADMIN_PASSWORD` in one namespace, and a realm for organizations; point `KEYCLOAK_NAMESPACE` and
`KEYCLOAK_REALM` at them. The example deployment uses its own community Keycloak 26.8.0 in namespace `tenant-idp`, realm
`tenants`.

## Skip

You can skip it. Without it you add sites by labelling ManagedClusters by hand, manage organizations in Keycloak
directly, and commit models and subscriptions to the catalog yourself ([model delivery](./model-delivery.md)). You can
then also skip [AI Grid Policies](./ai-grid-policies.md). *(Unverified.)*

## Upgrade

The chart commit and both image digests are pinned in the library, so they move with the library pin, and the console
and backend always move together. Rerun `create-secrets.sh` after you change the Keycloak URL or rotate the catalog token, or when the console's
README at the new pin asks for it, such as after a change to the backend's Keycloak roles.

## Known issues

**Symptom:** creating an organization in the console fails with Bad Request.
**Cause:** the backend sends `autoRedirect` in organization domains, which Red Hat build of Keycloak 26.4 and 26.6
reject.
**Workaround:** run community Keycloak 26.8.0 for the realm the console manages, as the library's Keycloak and the
example deployment do.

**Symptom:** the script stops on a rerun and prints a Keycloak user ID.
**Cause:** a backend user exists that no Secret records, such as one an older script version created.
**Workaround:** check that the user is the console's, then rerun with `ADOPT_KEYCLOAK_USER_ID=USER_ID`.

**Symptom:** the console can't reach Keycloak on a cluster whose ingress certificate a private CA signs.
**Cause:** the backend image trusts only the system roots, and the chart has no setting for another CA.
**Workaround:** rerun the script with `KEYCLOAK_BACKEND_URL` set to Keycloak's in-cluster Service URL, such as
`http://keycloak.KEYCLOAK_NAMESPACE.svc:8080`, and `CURL_CA_BUNDLE` set to the ingress CA file. *(Unverified.)*
