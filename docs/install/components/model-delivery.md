# Model delivery

`apps/acm-models` delivers the catalog, the models and subscriptions the [provider console](./console.md) commits to
your catalog repository, to the sites by role. `apps/acm-models-samples` adds the library's sample model for a demo.
The console's model and subscription pages depend on `apps/acm-models`; [AI Grid Policies](./ai-grid-policies.md)
report what it delivered.

| | |
|---|---|
| Runs on | hub (ApplicationSets); models on inference and combined sites, MaaS objects on ingress and combined sites |
| Library component | `apps/acm-models` (select `apps/acm-models/application.yaml`); optional `apps/acm-models-samples` (select `apps/acm-models-samples/application.yaml`) |
| Choices | Use ours. Bring your own: a catalog you write yourself. Skip: samples only. |

## Use ours

1. Create the catalog repository: an empty git repository, such as a new GitHub repository with only a README. Only
   the console's git writer commits to it. Keep it apart from your deployment repository, because whoever holds the
   writer's token can change it.

2. Set the inputs `catalogRepoURL` (the repository's URL) and `catalogRevision` (a branch, such as `main`, because the
   console pushes to it) in your root's `values`.

3. Add the component to the root's `files` list:

   ```yaml
   - path: apps/acm-models/application.yaml
   ```

   It also needs [spoke delivery](./spoke-delivery.md) for its Placements and Argo CD cluster registration.

Argo CD creates, in `openshift-gitops` on the hub, two AppProjects and three ApplicationSets:

| Catalog path | ApplicationSet | Delivers to | Namespace |
|---|---|---|---|
| `catalog/clusters/SITE/` | `acm-models-catalog-models` | that `inference` or `combined` site, once the folder exists | `ai-grid-internal-models` |
| `catalog/ingress/` | `acm-models-catalog-ingress` | every `ingress` or `combined` site | `models-as-a-service` |
| `catalog/subscriptions/` | `acm-models-catalog-subscriptions` | every `ingress` or `combined` site | `models-as-a-service` |

The git writer lays the catalog out this way (see the example catalog,
[`cfchase/ai-grid-catalog-proto`](https://github.com/cfchase/ai-grid-catalog-proto)):

- `catalog/models/MODEL/deployment/`: the LLMInferenceService and its NetworkPolicy.
- `catalog/models/MODEL/catalog/model.yaml`: the model's ExternalModel and MaaSModelRef.
- `catalog/clusters/SITE/kustomization.yaml`: the models placed on that site, as `../../models/MODEL/deployment`.
- `catalog/ingress/kustomization.yaml`: every model's `../models/MODEL/catalog`.
- `catalog/subscriptions/SUBSCRIPTION.yaml`: a MaaSSubscription and its MaaSAuthPolicy `SUBSCRIPTION-policy`.

The catalog's Applications run in AppProjects `acm-models-catalog-models` (LLMInferenceService, NetworkPolicy) and
`acm-models-catalog-maas` (ExternalModel, MaaSModelRef, MaaSSubscription, MaaSAuthPolicy), which admit only the
catalog repository, no cluster-scoped kinds and only those kinds. An empty catalog generates no Applications and shows
no errors.

Deleting a site's folder or the models ApplicationSet leaves its models running. Deleting an ingress or subscriptions
Application deletes its MaaS objects with it, so no tenant access outlives it. The
[README](../../../apps/acm-models/README.md) covers deletion and metrics in depth.

### Verify

After the console's first model and subscription ([First use](../08-first-use.md)), on the hub:

```sh
oc -n openshift-gitops get applicationsets.argoproj.io | grep acm-models-catalog
oc -n openshift-gitops get applications.argoproj.io | grep acm-models-catalog
```

You should see the three ApplicationSets, and Applications `acm-models-catalog-models-SITE`,
`acm-models-catalog-ingress-SITE` and `acm-models-catalog-subscriptions-SITE` `Synced` and `Healthy`. On the site:

```sh
oc -n ai-grid-internal-models get llminferenceservices
oc -n models-as-a-service get externalmodels,maasmodelrefs,maassubscriptions,maasauthpolicies
```

You should see the model `READY` `True` and the MaaS objects `Ready` or `Active`, about 2 minutes after the
Applications appear.

### Sample models (demo only)

`apps/acm-models-samples` delivers `facebook-opt-125m` on CPU to inference and combined sites, its ExternalModel and
MaaSModelRef to ingress and combined sites, and sample subscriptions for organizations that exist only in the library's
own lab. The root drops its second sample (`smollm2-135m-instruct`). Skip it in production: models and subscriptions
belong in the catalog. If you select it for a demo, add `- path: apps/acm-models-samples/application.yaml`.
*(Unverified.)*

## Bring your own

You can write the catalog yourself instead of through the console: commit files in the layout this page describes to
the repository `catalogRepoURL` names. The AppProjects reject any other kind or namespace. A file that collides with
an object another Application manages stops that site's catalog sync (`FailOnSharedResource`). *(Unverified.)*

## Skip

You can skip `apps/acm-models-samples`. You can't skip `apps/acm-models` if you want to serve models: nothing else
delivers the catalog, and the console's writes would reach no site.

## Upgrade

Both components move with the library pin and need no manual step. Models and subscriptions move only when the catalog
changes.

## Known issues

**Symptom:** after the console's first commits, no `acm-models-catalog-*-SITE` Application appears.
**Cause:** the ApplicationSets' git generator kept its cached view of the empty catalog.
**Workaround:** refresh each catalog ApplicationSet once on the hub. *(Unverified.)*

```sh
for a in models ingress subscriptions; do
  oc -n openshift-gitops annotate applicationsets.argoproj.io acm-models-catalog-$a \
    argocd.argoproj.io/application-set-refresh=true --overwrite
done
```

**Symptom:** `facebook-opt-125m` (OPT-125m) is listed in `/v1/models`, but chat calls through MaaS return 400.
**Cause:** OPT-125m has no chat template, and the MaaS gateway sends completions to the chat endpoint.
**Workaround:** deploy a chat model, such as SmolLM2-135M-Instruct, for tests.

**Symptom:** a teardown leaves a model running with no MaaS entry.
**Cause:** model Applications preserve their resources; MaaS Applications delete theirs.
**Workaround:** on the site, delete the model by hand:
`oc -n ai-grid-internal-models delete llminferenceservice MODEL`.
