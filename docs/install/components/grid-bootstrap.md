# Grid bootstrap

This component creates the grid on the hub: its persistent grid ID, its certificate authority, and the enrollment
that gives each labelled cluster a site identity certificate and its `GridNetwork` through ACM. The grid operator on
every site, and so all cross-site routing, depends on it.

| | |
|---|---|
| Runs on | hub (CA, Certificates, Policies); delivers to ingress, inference and combined sites |
| Library component | `apps/grid-bootstrap` (select `apps/grid-bootstrap/application.yaml`) |
| Choices | Use ours. Bring your own: only the CA (mode `Existing`). Skip isn't an option. |

## Use ours

1. Add the component to the root's `files` list:

   ```yaml
   - path: apps/grid-bootstrap/application.yaml
   ```

   It reads the inputs `libraryRepoURL`, `libraryRevision`, `deploymentRepoURL` and `deploymentRevision`. It installs
   the `grid-enrollment` chart from `opendatahub-io/odh-gitops` at a commit the library pins, in external mode, with
   cert-manager. cert-manager must already run on the hub.

2. Add `values/grid-bootstrap.yaml` to your deployment repository. For a new grid:

   ```yaml
   external:
     certManager:
       ca:
         mode: Generate
   ```

   The file is required. `Generate` creates the CA once, in Secret `redhat-ai-grid/grid-ca-key`; bootstrap never
   regenerates it. For another mode, see [Bring your own](#bring-your-own).

   The library's `apps/grid-bootstrap/values.yaml` sets the rest, including
   `managedClusters.createClusterSetBinding: true`: this release owns ManagedClusterSetBinding
   `redhat-ai-grid/global`, which the grid's Placements select through. The root ApplicationSet removes the copy that
   `apps/rhoai` carries, so exactly one Application owns it.

Argo CD then creates, in namespace `redhat-ai-grid` on the hub:

- the CA Issuer `grid-ca` and the immutable ConfigMap `grid-bootstrap-state`, which holds the grid ID;
- one site identity `Certificate` per cluster labelled `ai-grid/enabled=true`, with its Secret `grid-site-SITE`
  (`SITE` is the ManagedCluster name, which is also the site's grid identity);
- Policies that deliver to each site its identity Secret `grid-site-identity`, the public CA bundle, and the complete
  `GridNetwork` (Local membership, poll transport, SPIFFE trust);
- a read-only GridSite observer per site, which distributes each site's public endpoints to its peers;
- the library's extra Policies (`apps/grid-bootstrap/policies`): the operator's config RBAC, the CRD hand-back, and
  the local-endpoints Policy that publishes the signals Route on inference and combined sites.

The CA's signing key never leaves the hub. The [README](../../../apps/grid-bootstrap/README.md) covers rollback and
recovery; read it before you change the CA or the network.

### Verify

On the hub:

```sh
oc -n redhat-ai-grid get managedclustersetbinding global
oc -n redhat-ai-grid get issuers.cert-manager.io grid-ca
oc -n redhat-ai-grid get certificates.cert-manager.io
oc -n redhat-ai-grid get configmap grid-bootstrap-state
oc -n redhat-ai-grid get policies
```

You should see one binding `global`, the Issuer `Ready`, one `Ready` Certificate per labelled site, and every Policy
`Compliant`.

On each site:

```sh
oc get gridnetworks.grid.praxis.fast,gridsites.grid.praxis.fast -A
oc -n redhat-ai-grid get secret grid-site-identity \
  -o custom-columns='NAME:.metadata.name,CERT:.metadata.annotations.cert-manager\.io/certificate-name'
```

You should see the `GridNetwork` `grid` and a `GridSite` for the site that is `Available`; on more than one site,
each site also lists its peers. Every site shows the same grid ID.

## Bring your own

You can't replace enrollment, but you can bring the grid's CA. To keep the CA of an existing grid, or to use one your
PKI issued, set the mode to `Existing` in `values/grid-bootstrap.yaml` and create the CA Secret on the hub first:

```sh
oc -n redhat-ai-grid create secret tls grid-ca-key --cert=CA_CERT_FILE --key=CA_KEY_FILE
```

Replace the following:

- `CA_CERT_FILE`: the PEM file of a CA certificate (`CA:TRUE`).
- `CA_KEY_FILE`: its private key.

`Existing` never writes the CA Secret. To use another Secret name, set `external.certManager.ca.secretName` too.
*(Unverified.)*

## Skip

You can't skip it. Without it, no site gets an identity or a `GridNetwork`, and the grid operator routes nothing
between sites.

## Upgrade

The chart's commit and the enrollment image digest are pinned in the library, so they move with the library pin, with
no manual step. The grid ID and the CA persist across upgrades. Never switch the CA mode to `Generate` as a recovery
step, and never delete the `GridNetwork` or `grid-bootstrap-state` to roll back.

## Known issues

**Symptom:** on a hub installed from an older library commit, the grid's invite Placements select no cluster and no
site gets a `GridNetwork`.
**Cause:** no ManagedClusterSetBinding `redhat-ai-grid/global` existed: the root removed the `apps/rhoai` copy before
grid-bootstrap created its own.
**Workaround:** pin a library commit that includes `8aa65d7` or later, which sets `createClusterSetBinding: true`, and
keep that setting if you override `managedClusters` in `values/grid-bootstrap.yaml`.

