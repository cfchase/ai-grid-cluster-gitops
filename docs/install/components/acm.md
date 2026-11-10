# Red Hat Advanced Cluster Management

ACM is the hub's control plane: it imports the sites, places components on them by label, and runs the Policies that
copy credentials and configuration to them. Almost every other component depends on it; the library's ACM component
also configures the add-ons that the [MaaS database](./maas-db.md), [Limitador's Redis](./limitador-redis.md), the
provider console and the [observability](./observability.md) components rely on.

| | |
|---|---|
| Runs on | hub (add-ons run on every managed cluster) |
| Library component | `apps/acm` (select `apps/acm/application.yaml`) |
| Choices | Use ours · Bring your own (partly; see the gaps) |

## Use ours

1. Add the component to the `files` list in your root's `kustomization.yaml`:

   ```yaml
   - path: apps/acm/application.yaml
   ```

2. Provide object storage for ACM observability before you push: Secret `thanos-object-storage`, key `thanos.yaml`, in
   namespace `open-cluster-management-observability`. Select a library option or bring your own bucket; see
   [Object storage](./object-storage.md). MultiClusterObservability waits until that Secret exists.
3. Make sure the hub has a default StorageClass. Observability claims a 101 GiB compactor volume and other PVCs without
   naming a class. Run `scripts/check-prerequisites.sh --step hub --context HUB_CONTEXT` from the library checkout.

   Replace `HUB_CONTEXT` with your hub's kubeconfig context.

The component reads only `libraryRepoURL` and `libraryRevision`, and no file from your deployment repository. It
creates the following, in sync-wave order:

| What | Details |
|---|---|
| Operator | Subscription `acm-operator-subscription`, package `advanced-cluster-management`, channel `release-2.17`, automatic approval, in `open-cluster-management` |
| `MultiClusterHub` | `multiclusterhub`, default spec |
| Governance add-ons | ClusterManagementAddOns `governance-policy-framework`, `config-policy-controller` and `governance-standalone-hub-templating`, installed on every cluster in ManagedClusterSet `global` through Placement `policy-addons-clusters` |
| Search collector | Policy `search-collector` creates the `search-collector` add-on on every managed cluster except the hub and clusters that have a `KlusterletAddonConfig`. The console's backend reads a site's GPUs and MaaS subscriptions through Search. |
| Observability | `MultiClusterObservability` `observability`: size `minimal`, 2 receive replicas, 7-day raw and 14-day downsampled retention, platform and user-workload metrics |
| Submariner | `Broker` in `default-broker` with Globalnet (`242.0.0.0/8`), and ApplicationSet `acm-submariner`, which installs the Submariner add-on with 2 gateways behind a LoadBalancer Service on every cluster registered in Argo CD, the hub included |

### Prepare each site for Submariner

Submariner connects the hub and the sites so the sites reach the hub's database and Redis through
`*.svc.clusterset.local` names. On each site, and on the hub:

1. Make sure two nodes can act as gateways (the component asks for `gateways: 2`). Check which nodes carry the gateway
   label:

   ```sh
   oc --context CLUSTER_CONTEXT get nodes -l submariner.io/gateway=true
   ```

   If none are listed after the add-on installs, label two worker nodes `submariner.io/gateway=true`. *(Unverified.)*
2. Allow the Submariner tunnel traffic to the gateways' load balancer: UDP 4500 (IPsec NAT traversal) and UDP 4490
   (NAT discovery), from every other cluster in the grid. ACM can't open cloud ports for you unless it has cloud
   credentials for the cluster. *(Unverified.)*

Replace `CLUSTER_CONTEXT` with the kubeconfig context of the site or hub.

### Verify

```sh
oc get multiclusterhub multiclusterhub -n open-cluster-management -o jsonpath='{.status.currentVersion} {.status.phase}{"\n"}'
oc get multiclusterobservability observability -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
oc get policy search-collector -n open-cluster-management -o jsonpath='{.status.compliant}{"\n"}'
oc get managedclusteraddon -A | grep -E 'search-collector|submariner'
oc get applications.argoproj.io -n openshift-gitops | grep acm
```

You should see `2.17.x Running`, `True`, `Compliant`, one `search-collector` add-on per site, one `submariner` add-on
per cluster, and Applications `acm` and `acm-submariner-<cluster>` Synced and Healthy. Until the first site joins,
`acm-submariner-local-cluster` stays unhealthy: the hub's gateway has no peer to connect to. This is expected.

## Bring your own

If your hub already runs ACM, the library expects:

- ACM 2.17. The install was verified on ACM 2.17.4; other versions are untested.
- ManagedClusterSet `global` (ACM creates it by default). Components bind it in their own namespaces.
- Argo CD integration through `GitOpsCluster` (the library's `apps/argo-registration` creates it).
- Hub templating on managed clusters (`governance-standalone-hub-templating`), the search collector on every site,
  MultiClusterObservability reading `thanos-object-storage`, and the Submariner broker with Globalnet and the add-on on
  every cluster.

The library has no input to skip only the operator and `MultiClusterHub` while keeping the add-on configuration, so
leaving `apps/acm` out also leaves out the add-ons in the list. Create the equivalents yourself from
[`apps/acm/manifests`](../../../apps/acm/manifests) and [`apps/acm/submariner`](../../../apps/acm/submariner).
Selecting `apps/acm` on a hub where ACM is already installed under a different Subscription name is untested. See
[Gaps](../appendix-c-gaps.md). *(Unverified.)*

Check that your ACM version and add-ons match:

```sh
oc get multiclusterhub -A -o jsonpath='{.items[0].status.currentVersion}{"\n"}'
oc get clustermanagementaddon governance-standalone-hub-templating search-collector submariner
oc get managedclusterset global
```

## Skip

You can't skip ACM. Without it no site joins, and nothing reaches the sites.

## Upgrade

The operator channel is fixed in the library at `release-2.17` with automatic install-plan approval, so z-stream
updates install as Red Hat publishes them. A new minor version comes with a library pin that changes the channel.

## Known issues

- **Symptom:** `acm-submariner-<cluster>`, `limitador-redis` and the `maas-db` ServiceExport are unhealthy on a new hub.
  **Cause:** Submariner has no gateway connection, and no global IP to export, until a site joins.
  **Workaround:** None needed. They turn Healthy after the first site joins.
- **Symptom:** After you remove a site's AI Grid labels, `acm-submariner-<cluster>` stays.
  **Cause:** Submariner goes to every cluster registered in Argo CD, not only AI Grid sites.
  **Workaround:** It goes when you detach the ManagedCluster.
