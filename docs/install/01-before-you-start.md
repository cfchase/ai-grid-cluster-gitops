# Before you start

Gather the following before you run anything. Each item names the section that needs it.

## 1. Clusters

| Cluster | OpenShift | Needs | Verified with |
|---|---|---|---|
| Hub | 4.21 or later (`check-prerequisites.sh` enforces it) | A default StorageClass; room for ACM, Argo CD, the MaaS database primary, Keycloak, Redis and the console | 4.22.18, ACM 2.17.4 |
| Ingress site | 4.21 or later | A default StorageClass (OpenShift AI monitoring claims 20 GiB and 10 GiB; the MaaS database replica claims 20 GiB) | as combined |
| Inference site | 4.21 or later | A default StorageClass; capacity for its models; GPU nodes for GPU models | as combined |
| Combined site | 4.21 or later | Both of the preceding | 4.21.37, 6 nodes, CPU model only |

- Every cluster, the hub included, needs two worker nodes that Submariner can use as gateways
  ([ACM](components/acm.md)).
- A model's size sets a site's capacity. The CPU sample model in [first use](08-first-use.md) requests 4 CPU and
  8 GiB.
- With more than one site, give the hub's Argo CD application controller 8 GiB of memory
  ([OpenShift GitOps](components/openshift-gitops.md)).
- Managed OpenShift (OSD, ROSA) needs extra namespaces created by hand
  ([OpenShift AI prerequisites](components/rhoai-prerequisites.md)). *(Unverified.)*

Exact CPU and memory sizing for a hub isn't established yet ([known gaps](appendix-c-gaps.md)).

## 2. Network

| From | To | Port | Why |
|---|---|---|---|
| Your workstation | Every cluster's API | 6443 | `oc`, the import script |
| Hub's Argo CD | Your git host | 443 | Reads the library, deployment and catalog repositories |
| Every site | Hub, through Submariner | UDP 4500 and 4490 (Submariner IPsec and NAT discovery), through a LoadBalancer Service | Grid enrollment, the MaaS database primary, Redis |
| Ingress sites | Inference sites' default router | 443 (TLS passthrough) | Grid requests over mTLS |
| Tenants | Ingress site's MaaS gateway load balancer | 443 | Model calls |
| Ingress sites | Tenant identity provider's issuer URL | 443 | Token validation (OIDC discovery and keys) |

DNS:

- Each ingress site's MaaS hostname, `PREFIX.apps.CLUSTER_DOMAIN`, resolves to the MaaS gateway's load balancer.
  OpenShift creates this record; you choose `PREFIX` in [step 4](06-join-grid.md).
- Every router name answers `AAAA` queries with an address or an empty answer, never `NXDOMAIN`. Check with
  `dig AAAA router-default.apps.CLUSTER_DOMAIN`. An `NXDOMAIN` answer leaves every GridSite `Connecting`.

## 3. Accounts and credentials

| What | Used in | Notes |
|---|---|---|
| A `quay.io/rhoai` login in a container auth file | [Step 1](03-prepare-hub.md) | Prefer a robot token scoped to `quay.io/rhoai`. A general `quay.io` login is copied to every site, so the bootstrap script refuses it unless you set `RHOAI_QUAY_ALLOW_GENERIC_LOGIN=1`. |
| A git host the hub can read | [Section 2](02-repositories.md) | The example uses public GitHub repositories. |
| A token that can write only the catalog repository | [Step 2](04-hub-components.md) | A GitHub fine-grained token with `contents: write` on that one repository. The console's git writer uses it. |
| A tenant identity provider | [Section 2](02-repositories.md), [tenant identity provider](components/tenant-idp.md) | An OIDC issuer, a confidential client, and Keycloak Organizations if you use the console to create organizations. |
| `cluster-admin` on every cluster | All steps | |

## 4. Tools on your workstation

`oc`, `kustomize` (5.x), `jq`, `git`, `curl`, `python3`, `htpasswd` (from `httpd-tools`) and `clusteradm` (for the
import in [step 3](05-prepare-site.md)).

Check them:

```sh
for c in oc kustomize jq git curl python3 htpasswd clusteradm; do command -v "$c" >/dev/null || echo "missing: $c"; done
```

You should see no output.

## 5. Sign-in safety

Before you change anything on a cluster whose only sign-in is an external identity provider (for example a platform
Keycloak), add a break-glass htpasswd admin and confirm it works. If you lose the external provider later, this is the
only way back in. See [cluster sign-in and admins](components/cluster-sign-in.md).

Never delete an identity provider, or the namespace that runs it, that your platform's sign-in depends on.

## Checkpoint

- You have kubeconfig contexts with `cluster-admin` for the hub and every site.
- Your tools check prints nothing.
- You have the `quay.io/rhoai` auth file, a git host, and an identity provider plan.
