# AI Grid Policies

This component creates the inform-only ACM Policies that report each site's state back to the hub: whether the site
is provisioned, and whether the catalog's models and subscriptions came up. The [provider console](./console.md)
reads them to show a cluster as Provisioning or Provisioned and a model or subscription as ready.

| | |
|---|---|
| Runs on | hub (Policies); evaluated on ingress, inference and combined sites |
| Library component | `apps/ai-grid-policies` (select `apps/ai-grid-policies/application.yaml`) |
| Choices | Use ours. Bring your own and Skip aren't options when you run the console. |

## Use ours

1. Add the component to the root's `files` list:

   ```yaml
   - path: apps/ai-grid-policies/application.yaml
   ```

   It reads the inputs `libraryRepoURL` and `libraryRevision`, and no file from your deployment repository. It binds
   its Policies to the Placements that [spoke delivery](./spoke-delivery.md) creates in the same namespace, so select
   `apps/ai-grid-spokes` too.

Argo CD creates namespace `ai-grid-policies` on the hub, a `global` ManagedClusterSetBinding there, and three
Policies. All three are `inform`: they change nothing on a site.

| Policy | Placed on | Compliant when |
|---|---|---|
| `ai-grid-ready` | every AI Grid site (`ai-grid-spokes`) | The site's DataScienceCluster `default-dsc` reports `AIGridReady=True` and the role's KServe state (`KserveReady=False` on ingress, `True` on inference and combined), and Deployment `redhat-ai-grid/grid-operator` is `Available` |
| `ai-grid-models-status` | inference and combined sites (`ai-grid-inference`) | Every LLMInferenceService in `ai-grid-internal-models` is `Ready` |
| `ai-grid-catalog-status` | ingress and combined sites (`ai-grid-ingress`) | Every ExternalModel and MaaSModelRef in `models-as-a-service` is `Ready`, and every MaaSSubscription and MaaSAuthPolicy there is `Active` |

The status Policies look up every object of a kind, so they need no change when the catalog changes, and a namespace
with no such objects is `Compliant`. The console's backend reads the per-site copies (namespace `SITE`, name
`ai-grid-policies.POLICY`). Those namespace, Policy and ConfigurationPolicy names are the backend's contract: don't
rename them.

The tenant settings (the AITenant and its OIDC client) aren't here: [OpenShift AI](./rhoai.md) delivers them with
Policy `redhat-ai-grid/rhoai-ingress-clusters`.

### Verify

On the hub:

```sh
oc -n ai-grid-policies get policies
oc -n SITE get policies | grep ai-grid-policies
```

Replace `SITE` with a site's ManagedCluster name.

You should see the three Policies. `ai-grid-ready` turns `Compliant` for a site once OpenShift AI and the grid
operator are up there, 45 to 60 minutes after you label it. The two status Policies are `Compliant` on a site with an
empty catalog, and turn `NonCompliant` while a new model or subscription is coming up.

To see which objects a status Policy found, read its message:

```sh
oc -n SITE get policy ai-grid-policies.ai-grid-catalog-status \
  -o jsonpath='{range .status.details[*].history[0]}{.message}{"\n"}{end}'
```

You should see lines such as `maassubscriptions [...] found as specified in namespace models-as-a-service`.

## Bring your own

Not an option while you run the provider console: its backend reads these Policies by name. Without the console, the
Policies are only a convenience; your own monitoring can check the same conditions.

## Skip

You can skip it only if you don't select the [provider console](./console.md). With the console and without this
component, the console shows every cluster as Provisioning and no model or subscription status. *(Unverified.)*

## Upgrade

The component moves with the library pin and needs no manual step.
