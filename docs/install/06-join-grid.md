# Step 4: join each site to the grid

Labels on the site's ManagedCluster make it a grid site in its role. The hub then installs OpenShift AI, MaaS (on
ingress and combined sites), the grid, and the tenant settings. Use the shell variables from
[step 3](05-prepare-site.md).

## 1. Add the site's values

For an ingress or combined site, add `values/clusters/SITE/rhoai.yaml` to your deployment repository and push it
**before** you label the site. Without it, the site's `rhoai-SITE` Application doesn't render. Inference sites need no
file.

1. Choose the MaaS hostname prefix. Tenants call `https://PREFIX.apps.CLUSTER_DOMAIN`:

   ```yaml
   # values/clusters/SITE/rhoai.yaml
   components:
     aigateway:
       modelsAsAService:
         gateway:
           annotations:
             ai-grid/maas-gateway-hostname-prefix: PREFIX
   ```

2. Give the MaaS gateway a certificate tenants trust. The gateway otherwise presents its in-cluster service
   certificate on the public hostname, and a router Route can't help because OpenShift points the hostname straight at
   the gateway's own load balancer. On the tested site:

   1. A cert-manager `Certificate` for `PREFIX.apps.CLUSTER_DOMAIN` in `openshift-ingress`, from a DNS-01
      ClusterIssuer, delivered by an app in the deployment repository
      ([`sites/site-b/maas-tls/certificate.yaml`](https://github.com/cfchase/ai-grid-deployment-proto/blob/main/sites/site-b/maas-tls/certificate.yaml)
      and [`apps/site-b-maas-tls.yaml`](https://github.com/cfchase/ai-grid-deployment-proto/blob/main/apps/site-b-maas-tls.yaml)).
   2. The gateway's listeners overridden in the same values file, with the HTTPS listener's `certificateRefs` naming
      that Certificate's Secret
      ([`values/clusters/site-b/rhoai.yaml`](https://github.com/cfchase/ai-grid-deployment-proto/blob/main/values/clusters/site-b/rhoai.yaml)).
      Helm replaces lists whole, so copy both listeners.

   An HTTP-01 issuer can't solve for this hostname. The library has no input for this certificate yet
   ([known gaps](appendix-c-gaps.md)).

3. Commit and push.

## 2. Label the site

```sh
oc --context "$HUB_CONTEXT" label managedcluster "$SITE" ai-grid/enabled=true ai-grid/role=ROLE location=LOCATION
```

Replace the following:

- `ROLE`: `ingress`, `inference` or `combined`.
- `LOCATION`: a label for where the site is, such as `us-east`. The console shows it.

You should see `managedcluster.cluster.open-cluster-management.io/SITE labeled`. Within a minute the hub creates the
site's Applications:

```sh
oc --context "$HUB_CONTEXT" get applications.argoproj.io -n openshift-gitops | grep -- "-$SITE"
```

You should see at least `rhoai-SITE-…`, `cluster-config-SITE-…` and `acm-submariner-SITE`, plus `maas-db-SITE` on an
ingress or combined site. OpenShift AI takes 45 to 60 minutes. The site's nodes reboot once when the image mirror
arrives.

## 3. Verify

1. OpenShift AI is ready:

   ```sh
   oc --context "$SITE_CONTEXT" get datasciencecluster -o jsonpath='{.items[0].status.phase}{"\n"}'
   ```

   You should see `Ready`.

   On RHOAI 3.6 nightlies built after 2026-11-06, `KserveReady` can flap to `False` with
   `modelcache: cleanup ... kserve-leader-election-role`, and the phase with it. Models keep serving. Check again, or
   watch for a minute (`oc get datasciencecluster -w`); a site that returns to `Ready` is fine
   ([troubleshooting](10-troubleshooting.md#kserveready-flaps-false-on-a-site)).

2. The site is in the grid:

   ```sh
   oc --context "$SITE_CONTEXT" get gridnetworks,gridsites -A
   ```

   You should see the GridNetwork, and the site's GridSite `Available`.

3. The hub's Policies for the site are Compliant:

   ```sh
   oc --context "$HUB_CONTEXT" get policies -n "$SITE"
   ```

   You should see every Policy `Compliant`.

4. The hub's Applications are all Healthy now, including Submariner, `limitador-redis` and the MaaS database
   ServiceExport, which waited for the first site:

   ```sh
   oc --context "$HUB_CONTEXT" get applications.argoproj.io -n openshift-gitops \
     -o jsonpath='{range .items[*]}{.metadata.name} {.status.sync.status} {.status.health.status}{"\n"}{end}' \
     | grep -v ' Synced Healthy$'
   ```

   You should see no output.

5. On an ingress or combined site, the MaaS hostname answers with a trusted certificate:

   ```sh
   curl -sS -o /dev/null -w '%{http_code}\n' "https://PREFIX.apps.CLUSTER_DOMAIN/v1/models"
   ```

   You should see `401` (no token yet) and no certificate error.

## Checkpoint

- Every site's DataScienceCluster is `Ready` and its GridSite `Available`.
- Every hub Policy for the site is `Compliant`, and every hub Application is `Synced` and `Healthy`.
- Each ingress or combined site's MaaS hostname answers `401` over trusted TLS.
