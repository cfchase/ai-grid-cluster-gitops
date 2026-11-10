# Spoke delivery

These two components decide which clusters are AI Grid sites and let Argo CD on the hub reach them. `apps/ai-grid-spokes`
turns the `ai-grid/enabled` and `ai-grid/role` labels on each ManagedCluster into ACM Placements, and
`apps/argo-registration` registers every managed cluster with Argo CD. [OpenShift AI](./rhoai.md),
[model delivery](./model-delivery.md), [AI Grid Policies](./ai-grid-policies.md) and the per-site parts of other
components all select sites through these Placements.

| | |
|---|---|
| Runs on | hub |
| Library component | `apps/ai-grid-spokes` and `apps/argo-registration` (select both `application.yaml` files) |
| Choices | Use ours. Bring your own and Skip aren't options. |

## Use ours

1. Add both components to the root's `files` list:

   ```yaml
   - path: apps/ai-grid-spokes/application.yaml
   - path: apps/argo-registration/application.yaml
   ```

   They read the inputs `libraryRepoURL` and `libraryRevision`, and no file from your deployment repository. Argo
   CD's `global` ManagedClusterSetBinding in `openshift-gitops` comes from `apps/gitops-config`
   ([OpenShift GitOps](./openshift-gitops.md)), so select that too.

2. Make a cluster a site by labelling its ManagedCluster on the hub ([Join the grid](../06-join-grid.md)):

   ```sh
   oc label managedcluster SITE ai-grid/enabled=true ai-grid/role=ROLE location=LOCATION
   ```

   Replace the following:

   - `SITE`: the ManagedCluster name.
   - `ROLE`: `ingress`, `inference` or `combined`.
   - `LOCATION`: a name for where the site runs, such as `us-east`.

   For an `ingress` or `combined` site, push `values/clusters/SITE/rhoai.yaml` first ([OpenShift AI](./rhoai.md)).

How it works:

- `apps/argo-registration` creates GitOpsCluster `argo-registration`, which gives every managed cluster an Argo CD
  cluster Secret carrying its labels. Tolerations keep a briefly unreachable cluster registered.
- `apps/ai-grid-spokes` creates three Placements, each in both `openshift-gitops` (for ApplicationSets) and
  `ai-grid-policies` (for Policies):

  | Placement | Selects `ai-grid/enabled=true` and `ai-grid/role` in |
  |---|---|
  | `ai-grid-spokes` | `ingress`, `inference`, `combined` |
  | `ai-grid-ingress` | `ingress`, `combined` |
  | `ai-grid-inference` | `inference`, `combined` |

- Each ApplicationSet that targets sites, such as `rhoai`, reads a Placement's decisions live and joins them with
  the cluster's Argo CD Secret for its server address and role. It never selects on the Secret's labels alone,
  because ACM copies labels onto that Secret but never removes one.

A cluster with `ai-grid/enabled=true` and no role, or an unknown role, matches no Placement and gets none of the AI
Grid platform. Grid bootstrap reads `ai-grid/enabled` alone, so such a cluster still becomes a grid member whose
enrollment waits for grid CRDs that never arrive: always set both labels. The
[README](../../../apps/ai-grid-spokes/README.md) has the full rules.

### Verify

On the hub:

```sh
oc -n openshift-gitops get placementdecisions \
  -l 'cluster.open-cluster-management.io/placement in (ai-grid-spokes,ai-grid-ingress,ai-grid-inference)' \
  -o custom-columns='PLACEMENT:.metadata.labels.cluster\.open-cluster-management\.io/placement,CLUSTERS:.status.decisions[*].clusterName'
oc -n openshift-gitops get secrets -l apps.open-cluster-management.io/acm-cluster=true
oc -n openshift-gitops get applications.argoproj.io | grep SITE
```

You should see each site under the Placements its role selects, one Argo CD cluster Secret per managed cluster, and
the site's Applications (`rhoai-*` and the others) a minute or two after you label it.

### Remove a site

To remove a site from AI Grid management, remove its `ai-grid/enabled` label (the console's **Remove** does the same):

```sh
oc label managedcluster SITE ai-grid/enabled-
```

The site leaves the Placements, and its Applications go at the next poll: on the tested hub, within 30 seconds, and
the `maas-db` replica's Application about 3 minutes later. The console shows the site as **Not added**.

- Not withdrawn: grid membership. On the tested site the GridSite stayed `Connected` and `Available` for the whole
  7 minutes it was unlabelled. Withdrawing a site from the grid isn't designed yet
  ([known gaps](../appendix-c-gaps.md)).
- Stays installed, no longer managed: OpenShift AI, the provider gateway and the catalog's models, because the
  ApplicationSets set `preserveResourcesOnDeletion`.
- Deleted: the site's `maas-db` replica, and the catalog's MaaS objects and subscriptions on that site, so no tenant
  access outlives the site's membership.
- Stays and needs cleanup: the Secrets Policies delivered (`maas-db-config`, `maas-db-app`, `maas-db-replication`)
  and the tenant objects. Rotate the shared credentials after you remove a site.

Applications that go to every managed cluster, such as Submariner, stay until you detach the cluster from ACM.
Removing only the role has the same effect on the platform; either way the cluster stays a grid member.

## Bring your own

Not an option: the library's ApplicationSets and Policies name these Placements.

## Skip

You can't skip them: without them no cluster becomes a site and Argo CD can't deliver to any cluster.

## Upgrade

Both components move with the library pin and need no manual step.

## Known issues

**Symptom:** a site's Application renders the old role's values for up to a minute after a role change.
**Cause:** the Placements see the new role at once, and the Argo CD cluster Secret's labels follow a few seconds later.
**Workaround:** none needed; the Application converges at the next poll.
