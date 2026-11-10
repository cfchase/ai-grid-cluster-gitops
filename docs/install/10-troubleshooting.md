# Troubleshooting

Each entry gives the symptom, the cause and the fix. Component pages list more under **Known issues**.

## The root reports `missing input: NAME` or `invalid input: NAME`

**Cause:** your root's `values` don't set input `NAME`, or set it empty or with `"`, `'`, `\` or `@`.

**Fix:** set it in `root/kustomization.yaml` ([section 2](02-repositories.md#4-set-every-input)), run
`../library/scripts/check-deployment.sh .`, and push. Read the message with
`oc get applicationset apps -n openshift-gitops -o jsonpath='{.status.conditions}'`.

## A site's `rhoai-SITE` Application doesn't appear or doesn't render

**Cause:** an ingress or combined site has no `values/clusters/SITE/rhoai.yaml` with its MaaS hostname prefix.

**Fix:** add it ([step 4, part 1](06-join-grid.md#1-add-the-sites-values)) and push.

## Organization create fails with Bad Request

**Cause:** the console backend sends `autoRedirect` in organization domains, which Red Hat build of Keycloak 26.4 and
26.6 reject.

**Fix:** run community Keycloak 26.8.0 for tenants, as the library and the example do
([Keycloak](components/keycloak.md#known-issues)).

## Tenants get certificate errors on the MaaS hostname

**Cause:** the MaaS gateway presents its in-cluster service certificate on the public hostname.

**Fix:** give the gateway a trusted certificate through the site's values file
([step 4, part 1](06-join-grid.md#1-add-the-sites-values); [MaaS gateway certificate](components/maas-certificate.md)).

## Every model call returns `403`, "access denied to requested subscription"

**Cause:** the token's `groups` are already prefixed with the organization ID (`ORG_ID/ai-grid-users`). MaaS adds the
prefix itself and drops groups that already carry one.

**Fix:** emit plain group names from the IdP ([tenant identity provider](components/tenant-idp.md)).

## A chat call returns `400` "Field required: messages" or a template error

**Cause:** the model has no chat template (such as OPT-125m), and the MaaS gateway sends completions to the chat
endpoint.

**Fix:** deploy a chat model.

## Keycloak doesn't start after a version change

**Cause:** the pod runs `kc.sh import` before `kc.sh start`, and the import refuses to migrate an older database.

**Fix:** use `strategy: Recreate`, back up the database before a version change, and see
[Keycloak](components/keycloak.md#known-issues).

## Calls fail with `401` or `503` after the IdP was down

**Cause:** Authorino on the site cached the failed OIDC discovery or the old signing keys.

**Fix:** `oc --context SITE_CONTEXT rollout restart deployment/authorino -n kuadrant-system` on each ingress or combined
site.

## A tenant's users get no organization claims

**Cause:** Keycloak 26.8 didn't apply the realm import's user profile, so it drops admin-set `maas_*` attributes.

**Fix:** set the realm's `unmanagedAttributePolicy` to `ADMIN_EDIT` through the admin API, as the example's
`scripts/create-test-tenant.sh` does.

## `KserveReady` flaps `False` on a site

**Symptom:** the site's DataScienceCluster turns `Not Ready` for a while, with `KserveReady` `False` and a message
naming `modelcache: cleanup` and Role `kserve-leader-election-role`; it returns to `Ready`, then flaps again. Models
keep serving.

**Cause:** a regression in the KServe module operator on RHOAI 3.6 nightlies built after 2026-11-06: it deletes and
recreates its leader-election Role. Tracked as [RHOAIENG-103272](https://redhat.atlassian.net/browse/RHOAIENG-103272);
upstream fix [opendatahub-io/kserve#2175](https://github.com/opendatahub-io/kserve/pull/2175).

**Fix:** none needed; check twice or watch for a minute. Don't pin an older nightly to avoid it: that brings back the
bug kserve#2171 fixed.

## The Monitoring page can't load dashboards

**Symptom:** the console's **Monitoring** page says it's unable to load dashboards because `redhat-ods-monitoring`
doesn't exist.

**Cause:** the dashboards come from the observability components, which you didn't select.

**Fix:** none needed if you skipped observability on purpose; see [observability](components/observability.md) and
[known gaps](appendix-c-gaps.md).

## A model's catalog Applications don't appear

**Cause:** the catalog ApplicationSets' git generator didn't pick up the catalog's first commits.

**Fix:** refresh them once ([model delivery](components/model-delivery.md)).

## About one call in six fails the TLS handshake

**Cause:** one of the MaaS gateway load balancer's addresses doesn't answer, probably a zone with no gateway pod behind
it.

**Fix:** see [load balancers](components/load-balancers.md).

## Hub Applications for Submariner, `limitador-redis` or the MaaS database stay unhealthy

**Cause:** they wait for the first site to join.

**Fix:** none needed before step 4. After a site joins, check the site's Submariner gateways ([Submariner](components/submariner.md)).
