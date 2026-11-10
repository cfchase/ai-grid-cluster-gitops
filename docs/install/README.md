# Install AI Grid

This guide takes you from blank OpenShift clusters to a working AI Grid: a hub, one or more sites, a model deployed
from the provider console, and a tenant calling it. Follow the sections in order. Each section is a list of numbered
steps with a check after each step, and ends with a checkpoint that must be true before you move on.

> **Note:** Steps marked *(Unverified.)* weren't run when this guide was tested. Everything else was run end to end on
> 2026-11-10: a hub on OpenShift 4.22 with ACM 2.17 and one combined site on OpenShift 4.21, on AWS. That install is
> the [example deployment](appendix-b-example.md).

## What AI Grid is

AI Grid serves models from many OpenShift clusters as one service. Tenants call one endpoint, Models-as-a-Service
(MaaS) checks their identity and subscription, and the grid routes each request to a site that runs the model. A hub
cluster runs Red Hat Advanced Cluster Management (ACM), Argo CD and the provider console, and delivers everything else
to the sites.

```text
                tenants (OIDC tokens or API keys)
                              |
                              v
   +---------------- ingress site ----------------+       +---- inference site ----+
   | MaaS gateway, Org UI, grid consumer gateway  | mTLS  | grid provider gateway, |
   | (a combined site is ingress + inference)     |------>| models                 |
   +----------------------------------------------+       +------------------------+
                  ^                                                  ^
                  |  ACM policies, Argo CD applications, Submariner  |
                  +---------------------- hub -----------------------+
        ACM, Argo CD, grid enrollment, MaaS database, tenant identity provider,
        provider console
```

## How the install is organized: two parts

- **[Hub and external dependencies](hub/README.md):** what the hub runs, grouped into eight items in install order, from
  the platform services to observability. Each item's page gives your options, what the example chose, what it
  requires, and the lines that select it in your deployment repository.
- **[Spokes](spokes/README.md):** what each site brings, what you choose per site, and what the hub installs there. The
  hub installs every site from the same Helm chart in the site's role, so a site has almost no component choices.

## Follow these in order

| Page | What happens | Time |
|---|---|---|
| [Before you start](01-before-you-start.md) | Clusters, network, credentials and tools you need | 15 minutes |
| [Create your deployment and catalog repositories](02-repositories.md) | Your hub choices and inputs, the library pinned | 30 minutes |
| [Prepare the hub](03-prepare-hub.md) | Infrastructure checks, OpenShift GitOps, your root applied | 15 minutes |
| [Install the hub components](04-hub-components.md) | Argo CD installs ACM, the grid bootstrap, the MaaS database, the console | 30 minutes |
| [Prepare each site and join it to ACM](05-prepare-site.md) | Infrastructure checks, import into ACM | 15 minutes per site |
| [Join each site to the grid](06-join-grid.md) | Labels install OpenShift AI in the site's role and enrol it | 45 to 60 minutes per site |
| [First use: deploy a model and call it](08-first-use.md) | A model from the provider console, a tenant calling it | 30 minutes |

## Three repositories

| Repository | What it holds | Who changes it |
|---|---|---|
| The **library** (this repository) | Components only. Every value a deployment supplies is a named input. | Red Hat. You pin one commit. |
| Your **deployment repository** | Which components run, every input, per-site values, your own apps | You |
| Your **catalog repository** | Models and subscriptions | Only the provider console's git writer |

Your hub's Argo CD reads all three. Upgrading AI Grid is one commit to your deployment repository that moves the
library pin.

## Your choices

Decide the hub's eight items before you start. Each item's selection lines go in your deployment repository
([select components](02-repositories.md#3-select-components)).

| Item | Options | Requires | Example chose |
|---|---|---|---|
| [0. Platform services](hub/00-platform-services.md): OpenShift GitOps, cert-manager, External Secrets, cluster sign-in and admins, a default StorageClass | Each: ours, or the platform's or yours | A git host the hub can read; `cluster-admin` on the hub | Ours, except the platform's cert-manager |
| [1. ACM, the multicluster engine and Submariner](hub/01-acm.md) | Ours, or your existing ACM hub (partly) | Object storage (S4, ODF or yours); a load balancer and two Submariner gateway nodes per cluster | Ours, with S4 |
| [2. Grid](hub/02-grid.md): bootstrap, enrollment, status policies | No choice | cert-manager (0), ACM (1) | Ours |
| [3. MaaS shared services](hub/03-maas-shared-services.md): MaaS database primary, rate-limit Redis | No choice | Submariner, to export them (1) | Ours |
| [4. Tenant identity](hub/04-tenant-identity.md) | Our Keycloak, or your OIDC provider | Ours: MaaS database (3), cert-manager and External Secrets (0). Yours: an OIDC issuer, a confidential client and its CA | Its own Keycloak |
| [5. Provider console and model delivery](hub/05-console-and-model-delivery.md) | Console optional; model delivery required | Console: Keycloak with Organizations (4); a token that can write only the catalog repository | Both |
| [6. Site delivery](hub/06-site-delivery.md): site Placements, Argo CD registration, registry access | No choice | ACM (1); the `quay.io/rhoai` and stage logins (pre-release) | Ours |
| [7. Observability and usage logs](hub/07-observability.md) | On or off | ODF object storage | Off |

For each site you choose only its role (`ingress`, `inference` or `combined`) and, for an ingress or combined site, the
MaaS hostname prefix and a certificate for it. Each site brings OpenShift 4.21 or later, a default StorageClass, a load
balancer, two Submariner gateway nodes, DNS that never answers `NXDOMAIN` for `AAAA`, and GPUs for GPU models. The hub
installs the rest there: OpenShift AI with MaaS and the grid in the site's role, grid membership, a MaaS database
replica, Submariner, cluster sign-in and admins, and the models. See [Spokes](spokes/README.md).

## Reference

Open these when a page sends you there, or after the install:

- [Hub and external dependencies](hub/README.md) and [Spokes](spokes/README.md): every component in detail.
- [Operate](09-operate.md): upgrade, add and remove sites, rotate credentials, uninstall.
- [Troubleshooting](10-troubleshooting.md).
- Appendices: [A. Inputs and values reference](appendix-a-inputs.md) ·
  [B. The example deployment](appendix-b-example.md) · [C. Known gaps](appendix-c-gaps.md)
