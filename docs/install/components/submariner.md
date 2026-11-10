# Submariner

Submariner connects the hub and the sites so the sites reach the hub's grid enrollment, MaaS database primary and Redis
through `*.svc.clusterset.local` names. The [MaaS database](./maas-db.md) replicas and the
[rate-limit counters](./limitador-redis.md) depend on it.

| | |
|---|---|
| Runs on | hub and every site |
| Library component | Part of `apps/acm`: selecting [ACM](./acm.md) installs it. There's no separate component to select. |
| Choices | Use ours. Bring your own only with your own ACM ([ACM](./acm.md#bring-your-own)). |

## Use ours

[ACM](./acm.md)'s component creates a `Broker` in `default-broker` with Globalnet (`242.0.0.0/8`), and ApplicationSet
`acm-submariner`, which installs the Submariner add-on with 2 gateways behind a LoadBalancer Service on every cluster
registered in Argo CD, the hub included. The add-on's settings are in
[`apps/acm/submariner`](../../../apps/acm/submariner).

On each site, and on the hub:

1. Make sure two nodes can act as gateways (the component asks for `gateways: 2`). The
   [`cluster-config`](./cluster-sign-in.md) Policy `submariner-gateway-nodes` labels `submariner.io/gateway=true` only
   on nodes whose only role is `worker`. Compact clusters, where every node is also a control-plane node, and
   single-node OpenShift get no gateway node from it, so you label them by hand. Check which nodes carry the gateway
   label:

   ```sh
   oc --context CLUSTER_CONTEXT get nodes -l submariner.io/gateway=true
   ```

   If none are listed after the add-on installs, label two nodes by hand. *(Unverified.)*

   ```sh
   oc --context CLUSTER_CONTEXT label node NODE_NAME submariner.io/gateway=true
   ```

2. Give the gateways a load balancer. On a cloud, the provider creates it; on bare metal, you need MetalLB
   ([load balancers](./load-balancers.md)).
3. Allow the Submariner tunnel traffic to the gateways' load balancer: UDP 4500 (IPsec NAT traversal) and UDP 4490
   (NAT discovery), from every other cluster in the grid. ACM can't open cloud ports for you unless it has cloud
   credentials for the cluster. *(Unverified.)*

Replace `CLUSTER_CONTEXT` with the kubeconfig context of the site or hub, and `NODE_NAME` with a node's name.

### Verify

```sh
oc get managedclusteraddon -A | grep submariner
oc get applications.argoproj.io -n openshift-gitops | grep acm-submariner
oc --context CLUSTER_CONTEXT -n submariner-operator get svc --field-selector spec.type=LoadBalancer
```

You should see one `submariner` add-on per cluster, Applications `acm-submariner-<cluster>` Synced and Healthy, and an
`EXTERNAL-IP` on the gateway Service. Until the first site joins, `acm-submariner-local-cluster` stays unhealthy: the
hub's gateway has no peer to connect to. This is expected.

## Bring your own

If you leave `apps/acm` out, you also leave out its Submariner configuration. Create the broker with Globalnet and the
add-on on every cluster yourself, from [`apps/acm/submariner`](../../../apps/acm/submariner). See
[ACM](./acm.md#bring-your-own). *(Unverified.)*

## Skip

You can't skip it. Without it, the sites can't reach the hub's MaaS database primary or Redis.

## Upgrade

The add-on's settings move with the library pin; the Submariner version follows ACM's.

## Known issues

- **Symptom:** `acm-submariner-<cluster>`, `limitador-redis` and the `maas-db` ServiceExport are unhealthy on a new hub.
  **Cause:** Submariner has no gateway connection, and no global IP to export, until a site joins.
  **Workaround:** None needed. They turn Healthy after the first site joins.
- **Symptom:** After you remove a site's AI Grid labels, `acm-submariner-<cluster>` stays.
  **Cause:** Submariner goes to every cluster registered in Argo CD, not only AI Grid sites.
  **Workaround:** It goes when you detach the ManagedCluster.
- **Symptom:** No `submariner.io/gateway=true` node on a compact cluster or single-node OpenShift, and the gateway
  never connects.
  **Cause:** The `submariner-gateway-nodes` Policy labels only nodes whose only role is `worker`.
  **Workaround:** Label the gateway nodes by hand, as in step 1.
