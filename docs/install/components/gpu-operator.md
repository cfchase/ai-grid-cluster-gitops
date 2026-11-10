# NVIDIA GPU Operator and Node Feature Discovery

The NVIDIA GPU Operator installs the drivers and device plugin that let models request NVIDIA GPUs, and Node Feature
Discovery (NFD) labels the nodes it needs. Models that run on GPUs depend on both; CPU-only sites serve small sample
models without them.

| | |
|---|---|
| Runs on | inference and combined sites with NVIDIA GPUs |
| Library component | None directly. [OpenShift AI](./rhoai.md) (`apps/rhoai`) subscribes both operators on inference and combined sites; their configuration is yours |
| Choices | Use ours (operators from `apps/rhoai`, configuration yours) · Bring your own · Skip (CPU-only sites) |

Most of this page is unverified: the verified install ran a CPU model on a site without GPUs.

## Use ours

The OpenShift AI chart that `apps/rhoai` installs (`rhai-on-openshift-chart`, profile `ai-grid-inference`, which the
`ai-grid-combined` profile extends) turns on two dependencies on every inference and combined site:

| Operator | Package | Namespace | Channel | Catalog |
|---|---|---|---|---|
| NFD | `nfd` | `openshift-nfd` | `stable` | `redhat-operators` |
| NVIDIA GPU Operator | `gpu-operator-certified` | `nvidia-gpu-operator` | `v25.10` | `certified-operators` |

The chart creates the `NodeFeatureDiscovery` and `ClusterPolicy` resources only when you give their spec, and the
library doesn't. Until you do, the operators run but no driver is installed and no node offers `nvidia.com/gpu`.
Ingress sites get neither operator.

1. Make sure each GPU site can pull from the `certified-operators` catalog.
2. Give each GPU site the two specs in its file in your deployment repository, `values/clusters/SITE/rhoai.yaml`,
   which the `rhoai` Application reads after the role's values. *(Unverified.)*

   ```yaml
   dependencies:
     nfd:
       config:
         spec: {}            # your NodeFeatureDiscovery spec
     nvidiaGPUOperator:
       config:
         spec: {}            # your ClusterPolicy spec
   ```

   Replace `SITE` with the ManagedCluster name, and each `{}` with a spec from the
   [NFD](https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/specialized_hardware_and_driver_enablement/psap-node-feature-discovery-operator)
   and [NVIDIA GPU Operator on OpenShift](https://docs.nvidia.com/datacenter/cloud-native/openshift/latest/)
   documentation. The chart renders `NodeFeatureDiscovery` `nfd-instance` and `ClusterPolicy` `gpu-cluster-policy`
   once the operators' CRDs exist, so the first sync after a site joins may need a second sync.

   Alternatively, create those two resources yourself on each site, outside the library.

### Verify

```sh
oc --context SITE_CONTEXT -n openshift-nfd get csv
oc --context SITE_CONTEXT -n nvidia-gpu-operator get csv,clusterpolicy
oc --context SITE_CONTEXT get nodes -l nvidia.com/gpu.present=true \
  -o custom-columns='NODE:.metadata.name,GPUS:.status.allocatable.nvidia\.com/gpu'
```

Replace `SITE_CONTEXT` with your kubeconfig context for the site.

You should see both operators' CSVs `Succeeded`, ClusterPolicy `gpu-cluster-policy` `ready`, and each GPU node with a
non-zero GPU count. *(Unverified.)*

## Bring your own

If a site already runs NFD and the GPU Operator, the contract is: nodes with GPUs advertise allocatable
`nvidia.com/gpu`, and the operators are installed in `openshift-nfd` and `nvidia-gpu-operator` with the package names
in the table. The chart's Subscriptions use the same package names and namespaces, so OLM sees one operator; a
Subscription with another name for the same package in the same namespace can conflict. *(Unverified.)*

To stop the chart from managing them on a site, set both off in that site's `values/clusters/SITE/rhoai.yaml`. The
chart lets explicit values override the profile, but the library doesn't test this ([gaps](../appendix-c-gaps.md)).
*(Unverified.)*

```yaml
dependencies:
  nfd:
    enabled: false
  nvidiaGPUOperator:
    enabled: false
```

Check with the verify commands.

## Skip

A site without GPUs works for CPU models: the verified install served SmolLM2-135M-Instruct on CPU through the grid.
The operators are still subscribed on inference and combined sites, and with no `ClusterPolicy` they install nothing
on the nodes. What stops working: any model whose runtime asks for `nvidia.com/gpu` stays `Pending` on that site. The
console's model runtime defaults to NVIDIA GPUs, so give CPU-only sites a CPU runtime image when you deploy.

## Upgrade

The chart version, and with it each operator's channel, moves with the library pin. Within a channel, OLM upgrades the
operators automatically. Your specs in `values/clusters/SITE/rhoai.yaml` stay as they are.

## Known issues

- **Symptom:** GPU nodes show no `nvidia.com/gpu` capacity although the GPU Operator is installed.
  **Cause:** The library sets no `ClusterPolicy` spec, so the chart creates none.
  **Workaround:** Give the spec as in [Use ours](#use-ours), or create the `ClusterPolicy` yourself. *(Unverified.)*
