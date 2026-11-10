# External Secrets Operator

The External Secrets Operator generates and copies Secrets on the hub, so no secret value is ever stored in git. Several
library components and the worked example's tenant IdP create their passwords and keys with its `Password` generators
and `ExternalSecret` resources.

| | |
|---|---|
| Runs on | hub (also the external-services cluster, when you use one) |
| Library component | `apps/external-secrets` (select `apps/external-secrets/application.yaml`) |
| Choices | Use ours · Bring your own · Skip (only if nothing in the table needs it) |

What uses it:

| Component | What it generates |
|---|---|
| [Object storage](./object-storage.md), S4 option (`apps/object-storage/s4`) | The S3 access and secret keys and `thanos.yaml` in Secret `open-cluster-management-observability/thanos-object-storage` |
| [Keycloak](./keycloak.md) (`apps/keycloak`), the library's tenant IdP | Keycloak's admin, client, broker, test-user and database passwords, and its keystore password, in namespace `maas-db` |
| [External services](../../../apps/external-services/README.md) | Installs this operator again on the cluster labelled `ai-grid/external-services=true` |
| Your own apps | The worked example's tenant IdP generates its client secret in a dedicated namespace and copies it to Keycloak's namespace with a `kubernetes` `SecretStore` |

Each generated value uses `refreshPolicy: CreatedOnce` and `deletionPolicy: Retain`: it's generated once, never
rotated, and kept if the `ExternalSecret` goes.

## Use ours

1. Add the component to the `files` list in your root's `kustomization.yaml`:

   ```yaml
   - path: apps/external-secrets/application.yaml
   ```

It reads only `libraryRepoURL` and `libraryRevision`, no file from your deployment repository, and no Secret you create.
It installs the Red Hat build of External Secrets Operator cluster-wide: namespace `external-secrets-operator`,
Subscription `openshift-external-secrets-operator` (channel `stable-v1`, catalog `redhat-operators`), and the
`ExternalSecretsConfig` `cluster`. Components that use it retry until its CRDs exist, so install order doesn't matter.

### Verify

```sh
oc get subscription openshift-external-secrets-operator -n external-secrets-operator -o jsonpath='{.status.installedCSV}{"\n"}'
oc get crd externalsecrets.external-secrets.io passwords.generators.external-secrets.io
oc get externalsecrets -A
```

You should see an installed CSV, both CRDs, and every `ExternalSecret` with `READY` `True`.

## Bring your own

If your hub already runs an External Secrets Operator, it must serve these APIs, which the library's manifests use:

- `external-secrets.io/v1`: `ExternalSecret` (with `dataFrom.sourceRef.generatorRef`, `target.template` engine `v2`,
  `mergePolicy: Merge`) and `SecretStore`
- `generators.external-secrets.io/v1alpha1`: `Password`

Leave `apps/external-secrets/application.yaml` out of `files`, and check your operator serves them:

```sh
oc api-resources --api-group=external-secrets.io
oc api-resources --api-group=generators.external-secrets.io
```

You should see `externalsecrets` and `secretstores` in the first list and `passwords` in the second. A community
operator that serves the same API versions should work. *(Unverified.)*

## Skip

You can skip it only if you select neither the S4 object-storage option nor the library's Keycloak, and your own apps
don't use it. Otherwise their `ExternalSecret` resources never become Ready: S4 has no keys, so ACM observability
doesn't start, and the library's Keycloak has no admin or client secrets.

## Upgrade

The Subscription follows channel `stable-v1` with automatic approval, so updates within it install as they're
published. Because every generated value is `CreatedOnce`, an operator upgrade doesn't regenerate a password.

## Known issues

- **Symptom:** After you edit an `ExternalSecret`'s template, the Secret doesn't change.
  **Cause:** `refreshPolicy: CreatedOnce` writes the Secret once.
  **Workaround:** Delete the Secret so it's generated again, only when nothing depends on the old value. For the
  library Keycloak, see [`apps/keycloak/README.md`](../../../apps/keycloak/README.md), "Generated Secrets".
