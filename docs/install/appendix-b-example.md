# Appendix B: the example deployment

[`cfchase/ai-grid-deployment-proto`](https://github.com/cfchase/ai-grid-deployment-proto) is the deployment this guide
was tested with, on 2026-11-10: one hub (OpenShift 4.22, ACM 2.17) and one combined site (OpenShift 4.21) on AWS. Its
catalog is [`cfchase/ai-grid-catalog-proto`](https://github.com/cfchase/ai-grid-catalog-proto).

| Path | What it is |
|---|---|
| `root/kustomization.yaml` | The library's `bootstrap/hub` at a pinned SHA; the 16 selected components; the 14 inputs; the ODF generator removed; a generator for `apps/*.yaml` |
| `root/self.yaml` | `deployment-root`, which keeps the root in step with git (no prune) |
| `values/cluster-admins.yaml` | `cluster_admins: [admin]` |
| `values/grid-bootstrap.yaml` | A new grid (`Generate`), with the ClusterSet binding |
| `values/clusters/site-b/rhoai.yaml` | MaaS hostname prefix `maas` and the HTTPS listener on a trusted certificate |
| `apps/tenant-idp.yaml`, `idp/` | Its own tenant Keycloak: community Keycloak 26.8.0 pinned by digest, realm `tenants`, client `ai-grid-tenants`, its own CloudNativePG database, `strategy: Recreate`; the client secret in a namespace of its own |
| `apps/site-b-maas-tls.yaml`, `sites/site-b/maas-tls/` | A DNS-01 certificate for the site's MaaS hostname |
| `bootstrap.sh` | Step 1: GitOps, the root, the pull secret |
| `scripts/render.sh` | Renders the root and fails on unset inputs |
| `scripts/check-revisions.sh` | Checks every library source runs the pinned commit |
| `scripts/add-htpasswd-admin.sh` | The break-glass admin |
| `scripts/wipe-site.sh` | Removes an earlier AI Grid install from a site |
| `scripts/console-call.sh` | One console API call as an OpenShift user |
| `scripts/create-test-tenant.sh` | A test tenant user in its Keycloak |

What it chose: [decision table](README.md#your-choices-component-by-component), last column.
