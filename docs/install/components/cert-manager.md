# cert-manager

cert-manager issues the certificates AI Grid creates for itself: the grid CA and each site's identity certificate
(grid enrollment, `apps/grid-bootstrap`), the library Keycloak's signing keys, and OpenShift AI's monitoring
certificates on the sites. It's also the usual way to give the MaaS gateway a certificate your tenants trust; see
[MaaS gateway certificate](./maas-certificate.md).

| | |
|---|---|
| Runs on | hub; ingress, inference and combined sites |
| Library component | Hub: `apps/cert-manager` (select `apps/cert-manager/application.yaml`). Sites: installed by [OpenShift AI](./rhoai.md) |
| Choices | Use ours · Bring your own (the platform's cert-manager Operator for Red Hat OpenShift) |

## Use ours

On the hub:

1. Add the component to the `files` list in your `root/kustomization.yaml`:

   ```yaml
   - path: apps/cert-manager/application.yaml
   ```

   It reads the `libraryRepoURL` and `libraryRevision` inputs and no file from your deployment repository. It needs no
   Secret.

2. Argo CD creates namespace `cert-manager-operator`, OperatorGroup `openshift-cert-manager-operator` and
   Subscription `openshift-cert-manager-operator` (channel `stable-v1`, catalog `redhat-operators`, automatic
   approval). It creates no ClusterIssuer. *(Unverified: the verified install used the platform's cert-manager.)*

Don't select it on a hub that already runs the cert-manager operator: a second OperatorGroup in
`cert-manager-operator` makes OLM fail every operator in that namespace.

On the sites you do nothing: the OpenShift AI chart installs the same operator as a dependency of KServe and AI
Gateway (`dependencies.certManager.enabled: auto`). A site that already runs the platform's cert-manager keeps it.

What uses it, and what each one creates:

| User | Where | Objects |
|---|---|---|
| Grid enrollment (`apps/grid-bootstrap`) | hub | Issuer `redhat-ai-grid/grid-ca` (CA from `values/grid-bootstrap.yaml`: `Generate` or `Existing`) and each site's identity Certificate |
| Library Keycloak (`apps/keycloak`) | hub | Issuer `maas-db/keycloak-signing-selfsigned` and Certificate `keycloak-saas-signing` |
| OpenShift AI monitoring | sites | OpenTelemetry certificates; [OpenShift AI prerequisites](./rhoai-prerequisites.md) grants the OpenTelemetry operator access |
| MaaS gateway public certificate | ingress and combined sites | Yours: see [MaaS gateway certificate](./maas-certificate.md) |

The library uses only namespaced Issuers. A ClusterIssuer is yours to provide, and you need one only for the MaaS
gateway's public certificate.

### Verify

```sh
oc get crd certificates.cert-manager.io issuers.cert-manager.io clusterissuers.cert-manager.io
oc -n cert-manager get pods
oc -n redhat-ai-grid get issuers.cert-manager.io grid-ca
oc -n redhat-ai-grid get certificates.cert-manager.io
```

You should see all three CRDs, the cert-manager pods `Running`, Issuer `grid-ca` `READY` `True`, and every
Certificate `READY` `True` once grid enrollment is installed. The hub prerequisites check reports `OK` for
`cert-manager CRDs`:

```sh
scripts/check-prerequisites.sh --step hub --context HUB_CONTEXT
```

Replace `HUB_CONTEXT` with your hub's kubeconfig context. Run it from a library checkout at your pinned commit.

## Bring your own

The verified install used the cert-manager Operator for Red Hat OpenShift that the platform had already installed on
the hub (v1.20.1) and on the combined site. The contract:

- The CRDs `certificates.cert-manager.io`, `issuers.cert-manager.io` and `clusterissuers.cert-manager.io` exist, and
  the controller reconciles Issuers and Certificates in every namespace.
- On each site, cert-manager runs in namespace `cert-manager` from the operator in `cert-manager-operator`, which is
  where the OpenShift AI chart and the OpenTelemetry grant expect it. A cert-manager installed another way (another
  namespace, an upstream Helm release) isn't covered. *(Unverified.)*
- For the MaaS gateway: a ClusterIssuer that can issue for your sites' apps domains with a DNS-01 solver
  ([MaaS gateway certificate](./maas-certificate.md)).

Leave `apps/cert-manager` out of your `files` list. Check with the verify commands and:

```sh
oc get clusterissuer
```

## Skip

You can't skip it. Without cert-manager on the hub, grid enrollment can't create the grid CA, so no site joins the
grid. Without it on a site, OpenShift AI doesn't install.

## Upgrade

The operator follows its Subscription (channel `stable-v1`, automatic approval), not the library pin. Moving the pin
changes only the Subscription manifest, if the library changes it.

## Known issues

None specific to cert-manager. The MaaS gateway's certificate issues are on the
[MaaS gateway certificate](./maas-certificate.md#known-issues) page.
