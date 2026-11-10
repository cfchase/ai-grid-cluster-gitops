# OpenShift AI

This component installs OpenShift AI on each AI Grid site, in the site's role, from the `rhai-on-openshift-chart`
Helm chart that the library pins, and delivers the tenant settings (the AITenant and its OIDC client) to every site
that runs MaaS. [Model delivery](./model-delivery.md), [AI Grid Policies](./ai-grid-policies.md) and the
[provider console](./console.md) depend on it.

| | |
|---|---|
| Runs on | hub (ApplicationSet and tenant Policy); ingress, inference and combined sites (OpenShift AI) |
| Library component | `apps/rhoai` (select `apps/rhoai/application.yaml`) |
| Choices | Use ours. Bring your own and Skip aren't options. |

## Use ours

1. Add the component to the root's `files` list:

   ```yaml
   - path: apps/rhoai/application.yaml
   ```

   It reads the inputs `libraryRepoURL`, `libraryRevision`, `deploymentRepoURL`, `deploymentRevision` and all eight
   `idp*` inputs ([Appendix A](../appendix-a-inputs.md)). It needs [OpenShift AI prerequisites](./rhoai-prerequisites.md)
   and [spoke delivery](./spoke-delivery.md).

2. For each site with role `ingress` or `combined`, add `values/clusters/SITE/rhoai.yaml` to your deployment
   repository, and push it **before** you label the site:

   ```yaml
   components:
     aigateway:
       modelsAsAService:
         gateway:
           annotations:
             ai-grid/maas-gateway-hostname-prefix: HOSTNAME_PREFIX
   ```

   Replace the following:

   - `SITE`: the site's ManagedCluster name.
   - `HOSTNAME_PREFIX`: the first label of the MaaS host name. Tenants call `https://HOSTNAME_PREFIX.APPS_DOMAIN`,
     where `APPS_DOMAIN` is the site's ingress domain. The example deployment uses `maas`.

   An `inference` site needs no file. To give the MaaS gateway a publicly trusted certificate, add an HTTPS listener
   override to the same file; see [MaaS gateway certificate](./maas-certificate.md).

3. Create the two hub objects the `idp*` inputs name: the Secret holding the tenant client's secret, and the
   ConfigMap holding the CA that signs the issuer's certificate. [Tenant identity provider](./tenant-idp.md) covers both. The
   component reads only those two objects, by name, through a dedicated ServiceAccount.

4. Label the site ([Join the grid](../06-join-grid.md)). The `rhoai` ApplicationSet then generates one Application
   per site, named `rhoai-SITE-HASH`, from three layers: the library's `apps/rhoai/values.yaml`, the role file
   `apps/rhoai/roles/ROLE.yaml`, and your `values/clusters/SITE/rhoai.yaml`.

What each role installs:

| Role | Installs | Not installed |
|---|---|---|
| `ingress` | OpenShift AI with MaaS, the MaaS gateway `openshift-ingress/maas-default-gateway`, the grid consumer gateway, the MaaS portal and dashboard, the tenant settings | KServe, models *(Unverified.)* |
| `inference` | OpenShift AI with KServe, the grid operator and provider gateway | MaaS, dashboards *(Unverified.)* |
| `combined` | Both | |

On every ingress and combined site, Policy `redhat-ai-grid/rhoai-ingress-clusters` on the hub delivers the tenant
settings from the `idp*` inputs:

| Input | Lands on the site as |
|---|---|
| `idpIssuerURL` | `spec.oidc.issuerUrl` of AITenant `ai-tenants/models-as-a-service` |
| `idpClientID` | `spec.oidc.clientId` and `spec.oidc.audience` of that AITenant; MaaS matches the token's `azp` against it |
| `idpClientSecretNamespace`, `idpClientSecretName`, `idpClientSecretKey` | Secret `models-as-a-service/tenant-oidc-client`, key `clientSecret` |
| `idpCANamespace`, `idpCAName`, `idpCAKey` | ConfigMap `kuadrant-system/home-keycloak-ca`, key `home-keycloak-ca.crt`, mounted into Authorino |

The same Policy creates MaasTenantConfig `models-as-a-service/default-tenant` and the grid `ExternalProvider`
`grid-provider` that sends MaaS traffic into the grid. Each `rhoai-*` Application carries the label
`ai-grid/library-revision` with the library commit the site runs.

### Verify

On the hub, list each site's Application and its library commit, and the tenant Policy's compliance:

```sh
oc -n openshift-gitops get applications.argoproj.io -l ai-grid/library-revision \
  -L ai-grid/library-revision
oc -n SITE get policies | grep rhoai-ingress-clusters
```

You should see each `rhoai-*` Application `Synced` and `Healthy` with your pinned commit, and the Policy `Compliant`.

On the site, check OpenShift AI and, for ingress or combined sites, MaaS:

```sh
oc get datasciencecluster default-dsc
oc -n openshift-ingress get gateway maas-default-gateway
oc -n ai-tenants get aitenant models-as-a-service
```

You should see the DataScienceCluster `Ready`. It takes 45 to 60 minutes after you label the site. On an
inference site, the DataScienceCluster can stay not `Ready` while KServe and the grid are up; use the
`ai-grid-ready` Policy instead ([AI Grid Policies](./ai-grid-policies.md)). *(Unverified.)* The gateway lists the
host name `HOSTNAME_PREFIX.APPS_DOMAIN` on both listeners.

## Bring your own

Not an option: the grid, the catalog and the console expect the chart's profiles, namespaces and object names. You
choose the tenant IdP through the `idp*` inputs, and you can override chart values per site in
`values/clusters/SITE/rhoai.yaml`. Helm replaces lists whole, so an override of a list repeats every entry.

## Skip

You can't skip it: it's what makes a cluster an AI Grid site.

## Upgrade

The chart version (`3.6.0-dev.29.1`) and the OpenShift AI catalog image (`apps/rhoai/nightly.yaml`) are pinned in
the library, so they move only with the library pin. A pin move rolled every site's Application in about 6 minutes
with no manual step; the `ai-grid/library-revision` label shows when each site has moved.

## Known issues

**Symptom:** a site's `rhoai-*` Application fails to render with
`...ai-grid/maas-gateway-hostname-prefix is required`.
**Cause:** the site is ingress or combined and has no `values/clusters/SITE/rhoai.yaml` with the hostname prefix.
**Workaround:** add the file (step 2) and push it; the Application renders on its next refresh.

MaaS gateway certificate errors and the cleartext port 80 listener are on the
[MaaS gateway certificate](./maas-certificate.md#known-issues) page.

**Symptom:** tenant calls fail with 401 or 503 after the IdP was down or rotated its keys, though the IdP is back.
**Cause:** Authorino cached the failed OIDC discovery.
**Workaround:** on the site, restart Authorino: `oc -n kuadrant-system rollout restart deployment authorino`.

**Symptom:** the Org UI signs a tenant in, then can't load models ("Unable to load MaaS models") or API keys; its
calls return 401.
**Cause:** OpenShift AI 3.6 nightlies before FBC `d0ee30a` send the
portal's token in the wrong header ([RHAI-21554](https://redhat.atlassian.net/browse/RHAI-21554)).
**Workaround:** pin FBC `d0ee30a` or later; until then, create API keys through the MaaS API
([troubleshooting](../10-troubleshooting.md#the-org-ui-cant-load-models-or-api-keys)).

**Symptom:** about one call in six fails the TLS handshake or hangs.
**Cause:** an address of the gateway's load balancer is in a zone with no gateway pod (infrastructure).
**Workaround:** fix the load balancer's zones, or run gateway pods in every zone it serves.
