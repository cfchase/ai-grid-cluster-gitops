# MaaS database

The MaaS database is the PostgreSQL system of record for every organization's API keys and subscriptions: a writable
primary on the hub and a read replica on each ingress or combined site. MaaS (`maas-api`) on every ingress or combined
site depends on it, and so does the library's Keycloak, which keeps its own database in the same cluster.

| | |
|---|---|
| Runs on | hub (primary); ingress and combined sites (read replicas) |
| Library component | `apps/maas-db` (select `apps/maas-db/application.yaml`) |
| Choices | Use ours · Bring your own (not supported yet) |

## Use ours

1. Add the component to the `files` list in your root's `kustomization.yaml`:

   ```yaml
   - path: apps/maas-db/application.yaml
   ```

2. Select [ACM](./acm.md) and `apps/argo-registration`. Replicas reach the primary through Submariner, and the
   ApplicationSet picks sites from Argo CD's cluster Secrets.
3. Make sure the hub and every ingress or combined site have a default StorageClass. Each database instance claims
   20 GiB.

The component reads only `libraryRepoURL` and `libraryRevision`, no file from your deployment repository, and no
Secret you create: CloudNativePG generates every credential on the hub. It creates:

| Where | What |
|---|---|
| Hub, namespace `maas-db` | The CloudNativePG operator (`cloudnative-pg`, channel `stable-v1`, catalog `certified-operators`, in `cnpg-system`); `Cluster` `maas-db`, 3 instances, database `maas`, owner `maas_api`; ServiceExport `maas-db-rw`; read Services `maas-read-ro` and `maas-read-r` |
| Each ingress or combined site, namespace `maas-db` | The operator and `Cluster` `maas-read`, one instance, streaming from `maas-db-rw.maas-db.svc.clusterset.local` with `sslmode=verify-full` |
| Each ingress or combined site, namespace `redhat-ai-gateway-infra` | Secret `maas-db-config` with `DB_CONNECTION_URL` (the primary, through Submariner) and `DB_READ_CONNECTION_URL` (the local replica, `maas-read-r`), written by Policy `maas-db-api-credentials` |

ACM Policy `maas-db-replication-secrets` copies the replication certificate, CA and application credentials from the
hub to each remote site. The primary, its operator and its ServiceExport carry `Delete=false`, so removing the
Application or the hub's labels never deletes the database. A site's replica goes with the site's Application when the
site leaves the grid or the ingress role. Details: [`apps/maas-db/README.md`](../../../apps/maas-db/README.md).

### Verify

On the hub:

```sh
oc get clusters.postgresql.cnpg.io -n maas-db
oc get policies.policy.open-cluster-management.io -n maas-db
oc get applications.argoproj.io -n openshift-gitops | grep maas-db
```

On each ingress or combined site:

```sh
oc --context SITE_CONTEXT get cluster maas-read -n maas-db -o jsonpath='{.status.phase}{"\n"}'
oc --context SITE_CONTEXT get secret maas-db-config -n redhat-ai-gateway-infra -o custom-columns=NAME:.metadata.name,TYPE:.type
```

Replace `SITE_CONTEXT` with the site's kubeconfig context.

You should see `maas-db` with 3 ready instances, both Policies `Compliant`, Applications `maas-db`,
`maas-db-local-cluster` and `maas-db-<site>` Synced and Healthy, `Cluster in healthy state` on the site, and the
`maas-db-config` Secret. Until the first site joins, `maas-db-local-cluster` stays unhealthy: its ServiceExport gets no
global IP without a Submariner connection. This is expected.

## Bring your own

Not supported yet. MaaS reads only Secret `redhat-ai-gateway-infra/maas-db-config` on each ingress or combined site,
with two keys:

- `DB_CONNECTION_URL`: a `postgresql://` URL to the writable database, with `sslmode=require`
- `DB_READ_CONNECTION_URL`: a `postgresql://` URL to a read-only endpoint close to the site, with `sslmode=require`

The library writes that Secret from its own CloudNativePG cluster, and has no input that points it at another database.
To use your own PostgreSQL, leave `apps/maas-db` out and deliver `maas-db-config` to each ingress or combined site
yourself, for example with your own ACM Policy reading your credentials. The library's Keycloak still needs
`apps/maas-db`. Nothing in the library has run against a user-owned database. See [Gaps](../appendix-c-gaps.md).
*(Unverified.)*

## Skip

You can't skip it. Without `maas-db-config`, `maas-api` on the ingress and combined sites has no database, and no
organization can create API keys or call a model.

## Upgrade

The database moves with the library pin like any other component. The operator follows channel `stable-v1` with
automatic approval. The library configures no backups or point-in-time recovery; add them before you hold production
data. To move an existing database into this one, export and restore it into the primary before the credentials Policy
points `maas-api` at it ([`apps/maas-db/README.md`](../../../apps/maas-db/README.md), "Rollout").

## Known issues

- **Symptom:** `maas-db-local-cluster` reports a ServiceExport without a global IP on a new hub.
  **Cause:** Submariner has no connection until a site joins.
  **Workaround:** None needed. It turns Healthy after the first site joins.
- **Symptom:** On a fresh install, a site's `maas-api` can't read for a few minutes.
  **Cause:** The credentials Policy can write `maas-db-config` before the replica's `maas-read-r` Service exists.
  **Workaround:** None needed. Reads succeed once the replica is up.
