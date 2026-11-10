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

## Follow these in order

| Page | What happens | Time |
|---|---|---|
| [Before you start](01-before-you-start.md) | Clusters, network, credentials and tools you need | 15 minutes |
| [Create your deployment and catalog repositories](02-repositories.md) | Your component choices and inputs, the library pinned | 30 minutes |
| [Step 1: prepare the hub](03-prepare-hub.md) | Infrastructure checks, OpenShift GitOps, your root applied | 15 minutes |
| [Step 2: install the hub components](04-hub-components.md) | Argo CD installs ACM, the grid bootstrap, the MaaS database, the console | 30 minutes |
| [Step 3: prepare each site and join it to ACM](05-prepare-site.md) | Infrastructure checks, import into ACM | 15 minutes per site |
| [Step 4: join each site to the grid](06-join-grid.md) | Labels install OpenShift AI in the site's role and enrol it | 45 to 60 minutes per site |
| [First use: deploy a model and call it](08-first-use.md) | A model from the provider console, a tenant calling it | 30 minutes |

"Step 1" to "step 4" in this guide always mean the four install pages in this table.

## Three repositories

| Repository | What it holds | Who changes it |
|---|---|---|
| The **library** (this repository) | Components only. Every value a deployment supplies is a named input. | Red Hat. You pin one commit. |
| Your **deployment repository** | Which components run, every input, per-site values, your own apps | You |
| Your **catalog repository** | Models and subscriptions | Only the provider console's git writer |

Your hub's Argo CD reads all three. Upgrading AI Grid is one commit to your deployment repository that moves the
library pin.

## Your choices, component by component

Components come in three kinds:

- **Infrastructure:** often yours already, such as cert-manager or object storage. The library can install some.
- **Shared services:** ours, or yours connected through a contract, such as the tenant identity provider.
- **AI Grid itself:** always ours, configured by inputs.

Fill in the following table before you start. Your "use ours" rows become the component list in your deployment
repository ([repositories, part 3](02-repositories.md#3-select-components)).

| Component | Runs on | Use ours (select) | Bring your own | Skip | Requires | Example chose |
|---|---|---|---|---|---|---|
| [OpenShift GitOps](components/openshift-gitops.md) | hub | `apps/gitops-config` | Yes | No | | ours |
| [OpenShift AI prerequisites: pull secret and mirror](components/rhoai-prerequisites.md) | all | `apps/rhoai-prerequisites` | Credentials only | No | pre-release registry access (see [before you start](01-before-you-start.md)) | ours |
| [cert-manager](components/cert-manager.md) | all | `apps/cert-manager` | Yes | No | | the platform's |
| [MaaS gateway certificate](components/maas-certificate.md) | ingress, combined | none yet | Yes, required | No | a DNS-01 ClusterIssuer or your own certificate | DNS-01 Certificate as its own app |
| [Object storage](components/object-storage.md) | hub | `apps/object-storage/s4` or `odf` | Yes | No | S4: `apps/external-secrets` | S4 |
| [Load balancers](components/load-balancers.md) | all | `apps/metallb` | Yes (cloud) | No | | AWS |
| [GPU operator and NFD](components/gpu-operator.md) | inference, combined | installed by `apps/rhoai` (operators only) | Yes | CPU-only sites | | operators only, no GPU model |
| [Cluster sign-in and admins](components/cluster-sign-in.md) | all | `cluster-config` | Yes | No | | ours |
| [ACM](components/acm.md) | hub | `apps/acm` | Yes | No | object storage; Submariner: `apps/argo-registration` | ours |
| [Submariner](components/submariner.md) | all | part of `apps/acm` | Only with your own ACM | No | load balancers; gateway nodes (`cluster-config`) | ours |
| [External Secrets](components/external-secrets.md) | hub | `apps/external-secrets` | Yes | No | | ours |
| [MaaS database](components/maas-db.md) | hub, ingress | `apps/maas-db` | No | No | replicas: `apps/ai-grid-spokes` | ours |
| [Rate-limit counters (Redis)](components/limitador-redis.md) | hub | `apps/limitador-redis` | No | No | Submariner (`apps/acm`) | ours |
| [External services site](../../apps/external-services/README.md) | one labelled site | `apps/external-services` | No | Yes | a cluster labelled `ai-grid/external-services=true`; without one it installs nothing | selected, no site labelled |
| [Tenant identity provider](components/tenant-idp.md) | hub | [Keycloak](components/keycloak.md) (`apps/keycloak`) | Yes, any OIDC provider; the console needs Keycloak | No | ours: `apps/maas-db`, `apps/external-secrets`, cert-manager | our own Keycloak |
| [Observability and usage logs](components/observability.md) | hub, sites | `apps/ai-grid-o11y`, `apps/ai-grid-usage-logs` | No | Yes | ODF object storage | skipped |
| [OpenShift AI with MaaS](components/rhoai.md) | sites | `apps/rhoai` | No | No | `apps/rhoai-prerequisites`, `apps/grid-bootstrap`, a trusted MaaS certificate per ingress site | ours |
| [Grid bootstrap and enrollment](components/grid-bootstrap.md) | hub | `apps/grid-bootstrap` | No | No | cert-manager | ours |
| [Status policies](components/ai-grid-policies.md) | hub | `apps/ai-grid-policies` | No | No | | ours |
| [Spoke delivery](components/spoke-delivery.md) | hub | `apps/ai-grid-spokes`, `apps/argo-registration` | No | No | `apps/ai-grid-policies` (namespace) | ours |
| [Model delivery](components/model-delivery.md) | hub | `apps/acm-models` | No | No | a catalog repository | ours |
| [Provider console](components/console.md) | hub | `apps/console` | No | Yes | `apps/acm-models`; a **Keycloak** tenant IdP with Organizations. With another IdP, skip the console and write the catalog yourself | ours |

All component pages: [components](components/README.md).

## Reference

Open these when a page sends you there, or after the install:

- [Components in detail](components/README.md): one page per row of the preceding table.
- [Operate](09-operate.md): upgrade, add and remove sites, rotate credentials, uninstall.
- [Troubleshooting](10-troubleshooting.md).
- Appendices: [A. Inputs and values reference](appendix-a-inputs.md) ·
  [B. The example deployment](appendix-b-example.md) · [C. Known gaps](appendix-c-gaps.md)
