# Hub and external dependencies

The hub runs everything the sites share: Argo CD, ACM, the grid's enrollment, MaaS's shared services, the tenant
identity provider and the provider console. It also installs the sites. This part groups what the hub runs into eight
items, in install order. Each item's page says what it is, your options, what the example deployment chose, what it
requires, and the lines that select it in your deployment repository
([select components](../02-repositories.md#3-select-components)).

| Item | What it is | Options | Requires | Example chose |
|---|---|---|---|---|
| [0. Platform services](00-platform-services.md) | OpenShift GitOps (Argo CD), cert-manager, External Secrets, cluster sign-in and admins, a default StorageClass | Each: ours, or the platform's or yours | A git host the hub can read; `cluster-admin` on the hub | Ours, except the platform's cert-manager |
| [1. ACM, the multicluster engine and Submariner](01-acm.md) | The hub's control plane, its observability, and the tunnels to the sites | Ours, or your existing ACM hub (partly) | Object storage (S4, ODF or yours); a load balancer and two gateway nodes per cluster (cloud or MetalLB) | Ours, S4, AWS load balancers |
| [2. Grid](02-grid.md) | Grid bootstrap and enrollment, and the status policies | No choice (you can bring the CA) | cert-manager (0), ACM (1) | Ours, a new CA |
| [3. MaaS shared services](03-maas-shared-services.md) | The MaaS database primary and the rate-limit Redis | No choice | Submariner, to export them (1) | Ours, on the hub |
| [4. Tenant identity](04-tenant-identity.md) | The OIDC issuer for organization users | Our Keycloak, or your OIDC provider | Ours: MaaS database (3), cert-manager and External Secrets (0). Yours: an OIDC issuer, a confidential client and its CA | Its own Keycloak |
| [5. Provider console and model delivery](05-console-and-model-delivery.md) | The provider's admin UI, and delivery of the catalog to the sites | Console optional; model delivery required | Console: Keycloak with Organizations (4) and a token that can write only the catalog repository | Both |
| [6. Site delivery](06-site-delivery.md) | Site Placements, Argo CD registration, OpenShift AI's ApplicationSet, registry access | No choice | ACM (1); the `quay.io/rhoai` and stage logins (pre-release) | Ours |
| [7. Observability and usage logs](07-observability.md) | Dashboards for the console's **Monitoring** page, and MaaS usage logs | On or off | ODF object storage | Off |

What the hub installs on each site is in [Spokes](../spokes/README.md).
