# Tenant identity provider

The tenant identity provider (IdP) is the OIDC issuer that signs in organization users, to the Org UI and to MaaS: MaaS
on every ingress or combined site validates its tokens and reads the user's organization and groups from them. The
provider console also creates organizations in it, which requires Keycloak with Organizations.

| | |
|---|---|
| Runs on | hub, or the cluster labelled `ai-grid/external-services=true`, or anywhere you run your own IdP |
| Library component | `apps/keycloak` (hub) or `apps/keycloak-external-services`; or none: your own IdP |
| Choices | Use ours · Bring your own (the verified path) |

Whichever you choose, the 8 `idp*` inputs connect it to AI Grid ([Inputs](../appendix-a-inputs.md)). The library reads
nothing else about your IdP.

## Use ours

The library's Keycloak is community Keycloak 26.8.0 as a plain Deployment (no operator) in namespace `maas-db`, with a
`saas` realm that brokers each organization's own IdP and client `tenant-demo`. The verified install brought its own IdP
instead, so every step in this section is *(Unverified.)*

1. Select the components in your root's `files` list, together with `apps/maas-db` (Keycloak's database lives in its
   CloudNativePG cluster) and `apps/external-secrets` (its passwords). The hub also needs cert-manager, for the realm
   signing keys.

   ```yaml
   - path: apps/keycloak/application.yaml
   ```

   To run it on the cluster that holds MaaS's shared state instead, select `apps/external-services/application.yaml`
   and `apps/keycloak-external-services/application.yaml`, and label that cluster `ai-grid/external-services=true`.
2. Know what the default profile installs: `apps/keycloak/application.yaml` uses `overlays/default`, which adds two
   example tenant realms with test users. For anything but a test, use `overlays/core` (only the `saas` realm). The
   root reads the library's `application.yaml` as is, so leave `apps/keycloak` out of `files` and add your own
   Application in your deployment's `apps/` with `repoURL: '@libraryRepoURL@'`, `targetRevision: '@libraryRevision@'`
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

A CronJob keeps `tenant-demo`'s redirect URIs equal to `https://maas.<apps domain>/oauth2/callback` for every ingress or
combined site. Realms are imported on first start only; later edits to `saas-realm.json` reach the realm through
PostSync hooks. Details: [`apps/keycloak/README.md`](../../../apps/keycloak/README.md).

### Verify

```sh
oc rollout status deployment/keycloak -n maas-db
curl -fsS "$(oc get route keycloak -n maas-db -o jsonpath='https://{.spec.host}')/realms/saas/.well-known/openid-configuration" | jq -r .issuer
```

You should see the rollout complete and an issuer equal to your `idpIssuerURL`.

## Bring your own

The verified install used its own Keycloak: see the worked example's
[`idp/`](https://github.com/cfchase/ai-grid-deployment-proto/tree/main/idp). Your IdP must provide:

| Requirement | Detail |
|---|---|
| Issuer | `idpIssuerURL`, exactly as tokens carry it in `iss`, reachable over HTTPS from every ingress and combined site (Authorino fetches its discovery document and keys) |
| Client | A confidential client named `idpClientID`, with `https://MAAS_HOST/oauth2/callback` for each ingress or combined site among its redirect URIs |
| Access-token claims | `azp` equal to `idpClientID`; `aud` containing `idpClientID`; `token_use: access`; `org_id` and `org_name` for the user's organization; `roles`; and `groups` as plain names, such as `ai-grid-users`. Never `<org_id>/ai-grid-users`: MaaS adds the prefix itself |
| Client secret | A hub Secret named by `idpClientSecretNamespace`, `idpClientSecretName` and `idpClientSecretKey` |
| CA | A hub ConfigMap named by `idpCANamespace`, `idpCAName` and `idpCAKey`, holding the PEM CA that signs the issuer's certificate. For a publicly trusted issuer, any ConfigMap holding that CA |
| Organizations, for the console | Keycloak with Organizations turned on in the realm, Route `keycloak` and Secret `keycloak-secrets` (`KC_BOOTSTRAP_ADMIN_USERNAME`, `KC_BOOTSTRAP_ADMIN_PASSWORD`) in its namespace. Community Keycloak 26.8.0 works; Red Hat build of Keycloak 26.4 and 26.6 don't (see Known issues) |

1. Create the client secret in a namespace that holds nothing else. The tenant Policy's ServiceAccount gets `get`,
   `list` and `watch` on that Secret by name, and each site receives a copy of it. Create both namespaces before the
   `rhoai` component syncs:

   ```sh
   oc create namespace tenant-idp-client
   oc create secret generic tenant-idp-client -n tenant-idp-client --from-file=client-secret=CLIENT_SECRET_FILE
   ```

   Replace `CLIENT_SECRET_FILE` with the path of a file holding only the client's secret. Never commit it.
2. Set the inputs. The worked example's values, for an issuer behind the hub's default ingress certificate:

   ```yaml
   idpIssuerURL: https://keycloak-tenant-idp.APPS_DOMAIN/realms/tenants
   idpClientID: ai-grid-tenants
   idpClientSecretNamespace: tenant-idp-client
   idpClientSecretName: tenant-idp-client
   idpClientSecretKey: client-secret
   idpCANamespace: openshift-config-managed
   idpCAName: default-ingress-cert
   idpCAKey: ca-bundle.crt
   ```

3. For the console, run `apps/console/create-secrets.sh` with your Keycloak's namespace and realm, for example
   `KEYCLOAK_NAMESPACE=tenant-idp KEYCLOAK_REALM=tenants`.
4. Check the hub has both objects, with their keys:

   ```sh
   scripts/check-prerequisites.sh --step hub --context HUB_CONTEXT --expect-idp own \
     --idp-secret tenant-idp-client/tenant-idp-client:client-secret \
     --idp-ca openshift-config-managed/default-ingress-cert:ca-bundle.crt
   ```

   Replace `HUB_CONTEXT` with your hub's kubeconfig context. You should see `OK` for `IdP client secret` and `IdP CA`. The check doesn't
   care which product your IdP is (library commit `12926f9`).
5. Check a user's access token. Save one to `TOKEN_FILE` and decode its claims:

   ```sh
   jq -R 'split(".")[1] | @base64d | fromjson | {iss, azp, aud, token_use, org_id, org_name, groups, roles}' TOKEN_FILE
   ```

   You should see your issuer, `azp` equal to `idpClientID`, `token_use` `access`, an `org_id`, and plain group names.

## Skip

You can't skip it. Without an IdP, no organization user can sign in, and the console can't create organizations.

## Upgrade

The library's Keycloak image moves with the library pin; read Known issues before a pin that changes its version. Your
own IdP upgrades on your schedule; re-run the token check after each upgrade.

## Known issues

- **Symptom:** Creating an organization in the console fails with Bad Request.
  **Cause:** The console backend sends `autoRedirect` in organization domains; Red Hat build of Keycloak 26.4 and 26.6
  reject it.
  **Workaround:** Run community Keycloak 26.8.0, as the library and the worked example do.
- **Symptom:** After a Keycloak version change, Keycloak doesn't start ("database not up to date").
  **Cause:** The pod runs `kc.sh import` before `kc.sh start`, and the import refuses to migrate an older database. A
  rolling update also lets the old pod work on the database beside the new one. The library's Keycloak has the same
  layout and uses `RollingUpdate`.
  **Workaround:** Use `strategy: Recreate`, and back up the database before a version change.
- **Symptom:** Every model call returns 403, "access denied to requested subscription".
  **Cause:** The token's groups are already prefixed with the organization ID, and MaaS drops them.
  **Workaround:** Emit plain group names.
- **Symptom:** Users' `maas_*` attributes disappear and tokens carry no organization claims.
  **Cause:** Keycloak 26.8 didn't apply the realm import's user profile.
  **Workaround:** Set the realm's `unmanagedAttributePolicy` to `ADMIN_EDIT` through the admin API, as the worked
  example's
  [`scripts/create-test-tenant.sh`](https://github.com/cfchase/ai-grid-deployment-proto/blob/main/scripts/create-test-tenant.sh)
  does.
- **Symptom:** Calls fail with 401 or 503 after the IdP was down or its keys changed, though the IdP is back.
  **Cause:** Authorino on the site cached the failed discovery or the old keys.
  **Workaround:** Restart Authorino on each ingress or combined site:
  `oc --context SITE_CONTEXT rollout restart deployment/authorino -n kuadrant-system`. Replace `SITE_CONTEXT` with
  the site's kubeconfig context.
- **Symptom:** None; a security consideration with the library's Keycloak.
  **Cause:** Its client secret is a key in `maas-db/keycloak-secrets`, which also holds Keycloak's admin password, and
  the tenant Policy may read that whole Secret.
  **Workaround:** None in the library yet. See [Gaps](../appendix-c-gaps.md).
