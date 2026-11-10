# Tenant identity provider

The tenant identity provider (IdP) is the OIDC issuer that signs in organization users, to the Org UI and to MaaS: MaaS
on every ingress or combined site validates its tokens and reads the user's organization and groups from them. Any
OIDC provider that meets the contract on this page works. The provider console also creates organizations in it, which
requires Keycloak with Organizations.

| | |
|---|---|
| Runs on | hub, or the cluster labelled `ai-grid/external-services=true`, or anywhere you run your own IdP |
| Library component | None for the contract. The library's Keycloak is one implementation: see [Keycloak](./keycloak.md) |
| Choices | Use ours ([Keycloak](./keycloak.md)) · Bring your own, any OIDC provider (the verified path). The [provider console](./console.md) needs Keycloak. |

Whichever you choose, the 8 `idp*` inputs connect it to AI Grid ([Inputs](../appendix-a-inputs.md)). The library reads
nothing else about your IdP.

## Use ours

The library's Keycloak (`apps/keycloak`) meets this contract. Its page, [Keycloak](./keycloak.md), gives the
components to select and the `idp*` values to set.

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
| Organizations, for the console | Keycloak with Organizations turned on in the realm, Route `keycloak` and Secret `keycloak-secrets` (`KC_BOOTSTRAP_ADMIN_USERNAME`, `KC_BOOTSTRAP_ADMIN_PASSWORD`) in its namespace. Community Keycloak 26.8.0 works; Red Hat build of Keycloak 26.4 and 26.6 don't ([Keycloak known issues](./keycloak.md#known-issues)) |

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
   care which product your IdP is.
5. Check a user's access token. Save one to `TOKEN_FILE` and decode its claims:

   ```sh
   jq -R 'split(".")[1] | @base64d | fromjson | {iss, azp, aud, token_use, org_id, org_name, groups, roles}' TOKEN_FILE
   ```

   You should see your issuer, `azp` equal to `idpClientID`, `token_use` `access`, an `org_id`, and plain group names.

## Skip

You can't skip it. Without an IdP, no organization user can sign in, and the console can't create organizations.

## Upgrade

Your own IdP upgrades on your schedule; re-run the token check after each upgrade. The library's Keycloak moves with
the library pin; see [Keycloak](./keycloak.md#upgrade).

## Known issues

Keycloak-specific issues are on the [Keycloak](./keycloak.md#known-issues) page.

- **Symptom:** Every model call returns 403, "access denied to requested subscription".
  **Cause:** The token's groups are already prefixed with the organization ID, and MaaS drops them.
  **Workaround:** Emit plain group names.
- **Symptom:** Calls fail with 401 or 503 after the IdP was down or its keys changed, though the IdP is back.
  **Cause:** Authorino on the site cached the failed discovery or the old keys.
  **Workaround:** Restart Authorino on each ingress or combined site:
  `oc --context SITE_CONTEXT rollout restart deployment/authorino -n kuadrant-system`. Replace `SITE_CONTEXT` with
  the site's kubeconfig context.
