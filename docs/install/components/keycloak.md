# Keycloak

The library's Keycloak is one way to provide the [tenant identity provider](./tenant-idp.md): an OIDC issuer for
organization users, with Organizations turned on so the [provider console](./console.md) can create organizations in
it. It's community Keycloak 26.8.0 as a plain Deployment (no operator) in namespace `maas-db`, with a `saas` realm
that brokers each organization's own IdP and client `tenant-demo`.

| | |
|---|---|
| Runs on | hub, or the cluster labelled `ai-grid/external-services=true` |
| Library component | `apps/keycloak` (hub) or `apps/keycloak-external-services` |
| Choices | Use ours · Bring your own: any OIDC provider, see [tenant identity provider](./tenant-idp.md#bring-your-own) · Skip, if you bring your own IdP |

## Use ours

The verified install brought its own IdP instead, so every step in this section is *(Unverified.)*

1. Select the components in your root's `files` list, together with `apps/maas-db` (Keycloak's database lives in its
   CloudNativePG cluster) and `apps/external-secrets` (its passwords). The hub also needs cert-manager, for the realm
   signing keys.

   ```yaml
   - path: apps/keycloak/application.yaml
   ```

   This page covers Keycloak on the hub only. `apps/keycloak-external-services` runs it on a site labelled
   `ai-grid/external-services=true` instead, but the tenant Policy reads the client Secret and the CA from the **hub**,
   so that layout also needs both copied to the hub, and the CA is that site's, not the hub's. It isn't covered here.
2. Know what the default profile installs: `apps/keycloak/application.yaml` uses `overlays/default`, which adds two
   example tenant realms with test users. For anything but a test, use `overlays/core` (only the `saas` realm). The
   root reads the library's `application.yaml` as is, so leave `apps/keycloak` out of `files` and add your own
   Application in your deployment's `apps/` (read by your root's own-apps generator,
   [section 2](../02-repositories.md#3-select-components)) with `repoURL: '@libraryRepoURL@'`, `targetRevision: '@libraryRevision@'`
   and `path: apps/keycloak/overlays/core`, otherwise matching the library's.
3. Set the `idp*` inputs in your root's generator `values`:

   ```yaml
   idpIssuerURL: https://keycloak-maas-db.APPS_DOMAIN/realms/saas
   idpClientID: tenant-demo
   idpClientSecretNamespace: maas-db
   idpClientSecretName: keycloak-secrets
   idpClientSecretKey: KEYCLOAK_CLIENT_SECRET
   idpCANamespace: openshift-config-managed
   idpCAName: default-ingress-cert
   idpCAKey: ca-bundle.crt
   ```

   Replace `APPS_DOMAIN` with the ingress domain of the cluster Keycloak runs on, from
   `oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}'`.
4. After the console's Route exists, run `apps/console/create-secrets.sh` from the library checkout. Its defaults,
   `KEYCLOAK_NAMESPACE=maas-db` and `KEYCLOAK_REALM=saas`, are this Keycloak's.

Use MaaS hostname prefix `maas` on every ingress or combined site ([step 4](../06-join-grid.md#1-add-the-sites-values)):
a CronJob keeps `tenant-demo`'s redirect URIs equal to `https://maas.<apps domain>/oauth2/callback` for every ingress or
combined site. Realms are imported on first start only; later edits to `saas-realm.json` reach the realm through
PostSync hooks. Details: [`apps/keycloak/README.md`](../../../apps/keycloak/README.md).

### Verify

```sh
oc rollout status deployment/keycloak -n maas-db
curl -fsS "$(oc get route keycloak -n maas-db -o jsonpath='https://{.spec.host}')/realms/saas/.well-known/openid-configuration" | jq -r .issuer
```

You should see the rollout complete and an issuer equal to your `idpIssuerURL`. Then run the token check on the
[tenant identity provider](./tenant-idp.md#bring-your-own) page.

## Bring your own

Any OIDC provider that meets the [tenant identity provider](./tenant-idp.md#bring-your-own) contract replaces this
component. For the console, your own Keycloak needs Organizations turned on in the realm, Route `keycloak` and Secret
`keycloak-secrets` in its namespace; see Known issues for which Keycloak versions work.

## Skip

Skip it when you bring your own IdP: leave `apps/keycloak` out of your `files` list. The worked example did.

## Upgrade

The library's Keycloak image moves with the library pin. Read Known issues before a pin that changes its version.

## Known issues

- **Symptom:** Creating an organization in the console fails with Bad Request.
  **Cause:** The console backend sends `autoRedirect` in organization domains; Red Hat build of Keycloak 26.4 and 26.6
  reject it.
  **Workaround:** Run community Keycloak 26.8.0, as the library and the worked example do.
- **Symptom:** After a Keycloak version change, Keycloak doesn't start ("database not up to date").
  **Cause:** The pod runs `kc.sh import` before `kc.sh start`, and the import refuses to migrate an older database. A
  rolling update also lets the old pod work on the database beside the new one. The library's Keycloak has this
  layout and uses `RollingUpdate`; so did the worked example's own Keycloak.
  **Workaround:** Use `strategy: Recreate`, and back up the database before a version change.
- **Symptom:** Users' `maas_*` attributes disappear and tokens carry no organization claims.
  **Cause:** Keycloak 26.8 didn't apply the realm import's user profile.
  **Workaround:** Set the realm's `unmanagedAttributePolicy` to `ADMIN_EDIT` through the admin API, as the worked
  example's
  [`scripts/create-test-tenant.sh`](https://github.com/cfchase/ai-grid-deployment-proto/blob/main/scripts/create-test-tenant.sh)
  does.
- **Symptom:** None; a security consideration with the library's Keycloak.
  **Cause:** Its client secret is a key in `maas-db/keycloak-secrets`, which also holds Keycloak's admin password, and
  the tenant Policy may read that whole Secret.
  **Workaround:** None in the library yet. See [Gaps](../appendix-c-gaps.md).
