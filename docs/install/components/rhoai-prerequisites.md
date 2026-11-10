# OpenShift AI prerequisites

This component delivers, through ACM Policies on the hub, what every managed cluster needs before OpenShift AI installs
there: protected namespaces, the model namespace and its NetworkPolicies, the image mirror, the catalog pull secret and
the merged cluster pull secret. [OpenShift AI](./rhoai.md), [model delivery](./model-delivery.md) and the shared
Limitador counters (`apps/limitador-redis`) depend on it.

| | |
|---|---|
| Runs on | hub (Policies); delivered to every managed cluster in the `global` cluster set |
| Library component | `apps/rhoai-prerequisites` (select `apps/rhoai-prerequisites/application.yaml`) |
| Choices | Use ours. Bring your own and Skip aren't options. |

## Use ours

1. Add the component to the root's `files` list in your deployment's `root/kustomization.yaml`:

   ```yaml
   - path: apps/rhoai-prerequisites/application.yaml
   ```

   It reads the `libraryRepoURL` and `libraryRevision` inputs only, and no file from your deployment repository.

2. Create the hub Secret that holds the registry credentials. The [pull secret](./pull-secret.md) page explains which
   login you need and how to create it with `apps/rhoai-prerequisites/create-hub-secret.sh`. The result is Secret
   `rhoai-prerequisites/rhoai-quay-pull-secret` with key `.dockerconfigjson`. Until it exists, the pull-secret Policy
   renders nothing and changes no cluster; the image mirror is delivered anyway.

Argo CD creates namespace `rhoai-prerequisites` on the hub, a `global` ManagedClusterSetBinding, Placements and these
Policies:

| Policy | Where | What it delivers |
|---|---|---|
| `rhoai-prerequisites` | every managed cluster, hub included | Namespaces `redhat-ai-grid`, `redhat-ods-operator` and `ai-grid-internal-models`; the model namespace's NetworkPolicies; the model-publisher RBAC; ImageDigestMirrorSet `quay-registry`; Secret `openshift-marketplace/rhoai-catalog-pull-secret`; the hub's registry entries merged into `openshift-config/pull-secret`; the service CA as Secret `redhat-ai-grid/openshift-service-ca` |
| `rhoai-limitador-redis` | ingress and combined sites other than the hub | Namespace `limitador-redis`, Secret `kuadrant-system/limitador-redis`, and the `Limitador` Redis storage reference, so MaaS rate-limit counters are shared through Submariner |
| `rhoai-maas-api-metrics` | ingress and combined sites | Compatibility monitors for MaaS metrics |
| `rhoai-otel-cert-manager-compat` | AI Grid sites | Temporary cert-manager permissions for the OpenTelemetry operator |
| `rhoai-metrics-addon`, `rhoai-metrics-network` | hub; AI Grid sites | Metrics add-on registration; NetworkPolicy admitting ACM's agents to the collector on port 8889 |

The pull-secret merge keeps every credential the cluster already has. A bare `quay.io` entry in the hub Secret lands
only as `quay.io/rhoai`, so the cluster's own `quay.io` login stays. Changing the cluster pull secret or the mirror
makes the Machine Config Operator roll every node once, so expect each new cluster's nodes to reboot after it joins
ACM.

The [README](../../../apps/rhoai-prerequisites/README.md) has the details, including the OpenTelemetry workaround.

### Verify

On the hub, check that the Secret exists without showing its data, and that the Policies are compliant:

```sh
oc -n rhoai-prerequisites get secret rhoai-quay-pull-secret \
  -o custom-columns='NAME:.metadata.name,TYPE:.type'
oc -n rhoai-prerequisites get policies
oc -n SITE get policies | grep rhoai-prerequisites
```

Replace `SITE` with the ManagedCluster name of a site.

You should see Secret type `kubernetes.io/dockerconfigjson`, and each Policy `Compliant`. A cluster's
`rhoai-prerequisites` Policy stays `NonCompliant` while its nodes roll out the new pull secret.

On the site, check that the namespaces and the mirror exist:

```sh
oc get namespace redhat-ai-grid redhat-ods-operator ai-grid-internal-models
oc get imagedigestmirrorset quay-registry
oc get mcp
```

You should see the three namespaces `Active`, the mirror present, and every MachineConfigPool `UPDATED=True`.

## Bring your own

Not an option: the OpenShift AI and model components rely on the namespaces, NetworkPolicies and RBAC these Policies
create, by name. You can supply the credentials another way: if every cluster's `openshift-config/pull-secret`
already holds a `quay.io/rhoai` login and each cluster has its own `openshift-marketplace/rhoai-catalog-pull-secret`,
leave the hub Secret out and the pull-secret Policy changes nothing. *(Unverified.)*

## Skip

You can't skip it. Without it, OpenShift AI can't pull its catalog or bundles, and models have no namespace to run in.

## Upgrade

The component moves with the library pin and needs no manual step. Rotating the registry login means rerunning
`create-hub-secret.sh`; the Policy then merges the new credential, and the nodes roll once more. Removing the hub
Secret never deletes a pull secret already delivered to a cluster.

## Known issues

**Symptom:** a new site's nodes reboot shortly after it joins ACM.
**Cause:** the merged pull secret and the ImageDigestMirrorSet are node configuration, which the Machine Config
Operator applies by draining and rebooting each node.
**Workaround:** none needed; wait for every MachineConfigPool to report `UPDATED=True` before you label the site.
