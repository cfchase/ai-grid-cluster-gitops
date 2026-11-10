# OpenShift GitOps

OpenShift GitOps (Argo CD) on the hub installs every AI Grid component from git: the library at your pinned commit,
your deployment repository, and the catalog. Every other component depends on it, and ACM's GitOps integration
(`apps/argo-registration`) uses it to reach the sites.

| | |
|---|---|
| Runs on | hub |
| Library component | Operator: the library's `bootstrap/` files, applied once by your bootstrap script. Configuration: `apps/gitops-config` (select `apps/gitops-config/application.yaml`) |
| Choices | Use ours · Bring your own |

## Use ours

1. Install the operator and the root with the example deployment's
   [`scripts/bootstrap-hub.sh`](../../../scripts/bootstrap-hub.sh), described in
   [Prepare the hub](../03-prepare-hub.md). For OpenShift GitOps it does the following, from the library at the
   commit your root pins:

   1. Applies `bootstrap/namespace.yaml`, `bootstrap/gitops-operator-group.yaml` and
      `bootstrap/openshift-gitops-sub.yaml`: namespace `openshift-gitops-operator` and Subscription
      `openshift-gitops-operator` (channel `latest`, catalog `redhat-operators`, automatic approval).
   2. Waits for the `applications.argoproj.io` and `applicationsets.argoproj.io` CRDs, and for the default instance,
      ArgoCD `openshift-gitops` in namespace `openshift-gitops`, to reach phase `Available`.
   3. Applies `bootstrap/openshift-gitops-admin.yaml`: ClusterRoleBinding `openshift-gitops-admin`, which binds
      `cluster-admin` to ServiceAccount `openshift-gitops/openshift-gitops-argocd-application-controller`.
   4. Applies your `root/` (the root ApplicationSet `apps`). From then on Argo CD follows git.

2. Add the configuration component to the `files` list in your `root/kustomization.yaml`:

   ```yaml
   - path: apps/gitops-config/application.yaml
   ```

   It reads the `libraryRepoURL` and `libraryRevision` inputs and no file from your deployment repository. It
   server-side applies these fields onto ArgoCD `openshift-gitops`, and owns only them:

   - The application controller's memory: request `2Gi`, limit `8Gi`. The controller caches the in-cluster
     destination and every site, and runs out of memory with less during start-up and fan-out.
   - `resourceHealthChecks` for the kinds AI Grid deploys, such as CloudNativePG `Cluster`, `ExternalSecret`,
     OLM `Subscription`, `DataScienceCluster`, `GridNetwork`, `InferenceProvider`, `ManagedClusterAddOn`,
     `LLMInferenceService`, `ExternalModel` and `MaaSModelRef`. Without them, Argo CD reports these as Healthy before
     they are ready, and sync waves don't wait.

   It also creates ManagedClusterSetBinding `openshift-gitops/global`, so Placements in `openshift-gitops` can
   select clusters from the `global` cluster set. That object needs ACM's CRDs, so the Application retries until
   [ACM](./acm.md) is installed.

The Application never prunes, so removing it doesn't delete the ArgoCD instance.

### Verify

On an ACM hub, `oc get application` resolves to ACM's kind, so name the Argo CD kind in full:

```sh
oc -n openshift-gitops get argocd openshift-gitops -o jsonpath='{.status.phase}{"\n"}'
oc -n openshift-gitops get argocd openshift-gitops \
  -o jsonpath='{.spec.controller.resources.limits.memory}{"\n"}'
oc -n openshift-gitops get applications.argoproj.io gitops-config
oc -n openshift-gitops get applicationset apps \
  -o jsonpath='{.status.conditions[?(@.type=="ParametersGenerated")].status}{"\n"}'
```

You should see `Available`, `8Gi`, `gitops-config` `Synced` and `Healthy`, and `True`.

## Bring your own

You can use an Argo CD instance you already run, if it meets this contract. Every library Application and
ApplicationSet is written for it. *(Unverified.)*

- **Namespace and name.** The instance is ArgoCD `openshift-gitops` in namespace `openshift-gitops`, managed by the
  OpenShift GitOps operator. Every library Application names `namespace: openshift-gitops`, and `apps/gitops-config`
  patches the ArgoCD CR by that name.
- **Permissions.** The application controller can create any resource on the hub. The library grants
  `cluster-admin` to `openshift-gitops-argocd-application-controller`; a narrower role fails on cluster-scoped
  objects such as ClusterRoleBindings, Policies and Subscriptions.
- **ApplicationSet controller.** Enabled, with Go templates, `templatePatch` and the `clusterDecisionResource`,
  `matrix`, `clusters` and `git` generators. The root fails with `missing input: <name>` through `templatePatch`, so
  an older controller that ignores it creates broken Applications instead of failing.
- **ACM integration.** `apps/argo-registration` creates a GitOpsCluster that writes one cluster Secret per managed
  cluster into `openshift-gitops`, labelled `apps.open-cluster-management.io/acm-cluster=true`. The
  `clusterDecisionResource` generators read ConfigMap `openshift-gitops/acm-placement`.
- **Health checks and sizing.** Select `apps/gitops-config` so it applies the controller memory and health checks
  onto your instance. If your instance isn't operator-managed, copy the `resourceHealthChecks` from
  [`apps/gitops-config/manifests/argocd.yaml`](../../../apps/gitops-config/manifests/argocd.yaml) into its
  configuration yourself.
- **Repository access.** The instance can read the library, your deployment repository and your catalog repository.

Check the instance and the controller's permissions:

```sh
oc -n openshift-gitops get argocd openshift-gitops -o jsonpath='{.status.phase}{"\n"}'
oc auth can-i '*' '*' --all-namespaces \
  --as=system:serviceaccount:openshift-gitops:openshift-gitops-argocd-application-controller
oc -n openshift-gitops get configmap acm-placement
```

You should see `Available` and `yes`. The ConfigMap appears after ACM and `apps/argo-registration` are installed.

## Skip

You can't skip it. Without Argo CD on the hub, no component installs.

## Upgrade

The operator follows its Subscription (channel `latest`, automatic approval), not the library pin: OLM upgrades it
when Red Hat publishes a new version. The bootstrap files aren't applied again after the first install. Moving the pin
updates `apps/gitops-config`'s health checks and sizing with no manual step.

## Known issues

- **Symptom:** `oc get application gitops-config` returns `NotFound` or an ACM object.
  **Cause:** ACM also defines a kind named `Application`.
  **Workaround:** Use `applications.argoproj.io`.
- **Symptom:** The application controller restarts with `OOMKilled` as sites join.
  **Cause:** The controller caches every destination.
  **Workaround:** Select `apps/gitops-config`. A hub with many sites can need more than `8Gi`; raise the limit with a
  patch in your deployment. *(Unverified.)*
