# Limitador's Redis

Limitador's Redis holds the rate-limit counters that every MaaS gateway in the grid shares, so a subscription's token
quota counts across all ingress sites instead of per site. Limitador on each ingress or combined site depends on it,
through a Submariner ServiceExport.

| | |
|---|---|
| Runs on | hub (Redis); ingress and combined sites (Limitador points at it) |
| Library component | `apps/limitador-redis` (select `apps/limitador-redis/application.yaml`) |
| Choices | Use ours · Bring your own (not supported yet) · Skip |

## Use ours

1. Add the component to the `files` list in your root's `kustomization.yaml`:

   ```yaml
   - path: apps/limitador-redis/application.yaml
   ```

2. Select [ACM](./acm.md) (for Submariner) and `apps/rhoai-prerequisites`, whose Policy `rhoai-limitador-redis` points
   each site's Limitador at this Redis.
3. Make sure the hub has a default StorageClass. Each Redis instance claims 10 GiB.

The component reads only `libraryRepoURL` and `libraryRevision`, no file from your deployment repository, and no
Secret you create. It creates:

| Where | What |
|---|---|
| Hub, namespace `limitador-redis` | The OpsTree Redis operator (`redis-operator`, channel `stable`, catalog `community-operators`); `RedisReplication` `limitador-redis` (3 Redis instances with 3 Sentinels, `maxmemory 6gb`, `noeviction`, image `registry.redhat.io/rhel9/redis-7`); NetworkPolicy `limitador-redis-isolation`; ServiceExport `limitador-redis-master` |
| Hub, namespace `kuadrant-system` | Secret `limitador-redis` (key `URL`) and the storage reference on `Limitador` `limitador` |
| Each ingress or combined site (Policy `rhoai-limitador-redis`) | Namespace `limitador-redis` for the ServiceImport, Secret `kuadrant-system/limitador-redis` with `URL: redis://limitador-redis-master.limitador-redis.svc.clusterset.local:6379`, and `Limitador` `limitador` storage set to that Secret |

The NetworkPolicy admits the Redis pods themselves, Limitador on the hub, and Submariner Globalnet addresses
(`242.0.0.0/8`). Redis has no password: any workload that reaches it through Submariner can read and write the
counters. Details: [`apps/limitador-redis/README.md`](../../../apps/limitador-redis/README.md) and
[`apps/rhoai-prerequisites/README.md`](../../../apps/rhoai-prerequisites/README.md), "Shared Limitador Redis".

### Verify

On the hub:

```sh
oc get redisreplication limitador-redis -n limitador-redis
oc get serviceexport limitador-redis-master -n limitador-redis
oc get applications.argoproj.io limitador-redis -n openshift-gitops
```

On each ingress or combined site:

```sh
oc --context SITE_CONTEXT get serviceimport limitador-redis-master -n limitador-redis
oc --context SITE_CONTEXT get limitador limitador -n kuadrant-system -o jsonpath='{.spec.storage.redis.configSecretRef.name}{"\n"}'
```

Replace `SITE_CONTEXT` with the site's kubeconfig context.

You should see the ServiceExport and ServiceImport, `limitador-redis` as the storage Secret, and the Application Synced
and Healthy. Until the first site joins, `limitador-redis` stays unhealthy: the ServiceExport CRD arrives with
Submariner. This is expected.

With two or more ingress sites, exhaust a subscription's token quota through one site's gateway, then call another
site's gateway: the call returns HTTP `429` at once. *(Unverified.)* The verified install had one site.

## Bring your own

Not supported yet. Limitador reads Secret `kuadrant-system/limitador-redis`, key `URL` (a `redis://` URL), on each
ingress or combined site. Policy `rhoai-limitador-redis` writes that Secret with the library's Submariner address, and
the library has no input for another Redis. To use your own, leave `apps/limitador-redis` out and deliver the Secret and
the `Limitador` storage reference to each site yourself; `apps/rhoai-prerequisites` still writes its own, so you'd have
to change that Policy too. See [Gaps](../appendix-c-gaps.md). *(Unverified.)*

## Skip

You can leave it out. Each site's Limitador then needs its storage reference removed, or it points at a Redis that
doesn't exist, because `apps/rhoai-prerequisites` still configures it. With local counters, an organization's quota is
enforced per ingress site, so a user who reaches several sites gets several quotas. *(Unverified.)*

## Upgrade

Redis moves with the library pin. The Redis image is pinned by digest in the library. The operator follows the
community channel `stable` with automatic approval.

## Known issues

- **Symptom:** `limitador-redis` is unhealthy on a new hub.
  **Cause:** The ServiceExport CRD comes with Submariner, which connects only after a site joins.
  **Workaround:** None needed. It turns Healthy after the first site joins.
- **Symptom:** Limitador on a site can't reach Redis.
  **Cause:** Submariner between the hub and the site isn't connected.
  **Workaround:** Check the Submariner add-on and the gateway ports; see [ACM](./acm.md#prepare-each-site-for-submariner).
