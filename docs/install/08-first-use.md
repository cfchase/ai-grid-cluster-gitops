# First use: deploy a model and call it

In this section you create an organization, deploy a model to a site, subscribe the organization's users to it, and
call it as a tenant. The provider console writes the model and subscription to your catalog repository, and Argo CD
delivers them to the site.

The tested run made each console call through the console's API, the same calls its pages make, with the example's
[`scripts/console-call.sh`](https://github.com/cfchase/ai-grid-deployment-proto/blob/main/scripts/console-call.sh).
The page steps are given too, and are *(Unverified.)* in this release of the guide.

`console-call.sh` signs in as an OpenShift user through the htpasswd provider and makes one call:

```sh
scripts/console-call.sh --kubeconfig HUB_KUBECONFIG --password-file HUB_ADMIN_PASSWORD_FILE METHOD 'JSON'
```

## 1. Sign in to the console

Open `https://CONSOLE_HOST` (from [step 2](04-hub-components.md#3-verify)) and sign in as a cluster admin. You should
see the **Clusters** page with your sites. *(Unverified.)*

## 2. Create an organization

In the console, go to **Organizations**, click **Create**, and enter a name and an email domain. *(Unverified.)*

Or through the API:

```sh
scripts/console-call.sh --kubeconfig HUB_KUBECONFIG --password-file HUB_ADMIN_PASSWORD_FILE \
  ai_grid.v1.Tenants/Create '{"object":{"metadata":{"name":"ORG_NAME"},"spec":{"domains":["ORG_DOMAIN"]}}}'
```

You should see `HTTP 200` and the organization's `id`. Keep the `id` as `ORG_ID`. It's the Keycloak organization's ID,
and tokens carry it as `org_id`.

If you see `HTTP 400` with a Keycloak error, your Keycloak is the Red Hat build 26.4 or 26.6, which rejects the
console's request; see [troubleshooting](10-troubleshooting.md#organization-create-fails-with-bad-request).

Linking the organization to the tenant's own identity provider is done in the console's organization form or in
Keycloak. *(Unverified.)*

## 3. Deploy a model

Use a chat model: the MaaS gateway sends completions to the chat endpoint, so a model without a chat template, such
as OPT-125m, answers `400`. The tested model is SmolLM2-135M-Instruct on CPU.

In the console, go to **Models**, click **Deploy**, choose the model URI, the runtime image, resources and the site.
*(Unverified.)*

Or through the API:

```sh
scripts/console-call.sh --kubeconfig HUB_KUBECONFIG --password-file HUB_ADMIN_PASSWORD_FILE ai_grid.v1.Models/Create '{
  "object": {
    "id": "smollm2-chat",
    "metadata": {"name": "smollm2-chat", "annotations": {"openshift.io/display-name": "SmolLM2 135M Instruct"}},
    "spec": {
      "model": {"uri": "hf://HuggingFaceTB/SmolLM2-135M-Instruct"},
      "replicas": 1,
      "main": {
        "image": "registry.redhat.io/rhaii/vllm-cpu-rhel9@sha256:0ec0f5ff9a5ff263f58db0cfb19e3d7eef24b94c2d8629fe5145f5a8747e28c9",
        "env": [{"name": "OMP_NUM_THREADS", "value": "4"}, {"name": "VLLM_CPU_KVCACHE_SPACE", "value": "4"}],
        "requests": {"cpu": "4", "memory": "8Gi"}
      },
      "placement": {"label_selector": {"match_expressions": [{"key": "name", "operator": "In", "values": ["SITE"]}]}}
    }
  }
}'
```

You should see `HTTP 200`, and a new commit in your catalog repository under the site's directory.

## 4. Subscribe the organization

A subscription gives an organization's group access to models, with a token rate limit. Give the group name as
plain text, such as `ai-grid-users`; MaaS prefixes it with the organization ID.

In the console, go to **Subscriptions**, click **Create**, choose the organization, the group and the model.
*(Unverified.)*

Or through the API:

```sh
scripts/console-call.sh --kubeconfig HUB_KUBECONFIG --password-file HUB_ADMIN_PASSWORD_FILE ai_grid.v1.Subscriptions/Create '{
  "object": {
    "id": "SUBSCRIPTION_ID",
    "metadata": {"name": "SUBSCRIPTION_ID"},
    "spec": {
      "organization": {"id": "ORG_ID"},
      "owner": {"groups": ["ai-grid-users"]},
      "model_refs": [{"name": "smollm2-chat", "token_rate_limits": [{"limit": 100000, "window": "1m"}]}]
    }
  }
}'
```

You should see `HTTP 200` and another catalog commit.

## 5. Check the delivery

Within about two minutes the hub's catalog ApplicationSets create the site's model Applications:

```sh
oc --context "$HUB_CONTEXT" get applications.argoproj.io -n openshift-gitops | grep catalog
oc --context "$SITE_CONTEXT" get llminferenceservices,maassubscriptions,maasauthpolicies -A
```

You should see the model `Ready` and the subscription and its auth policy on the site. If no catalog Applications
appear after the catalog's first commits, refresh the ApplicationSets once
([model delivery](components/model-delivery.md)).

## 6. Call the model as a tenant

You need a tenant user: a member of the organization, in group `ai-grid-users`. In your own IdP, the tenant's admin
creates users. To make a test user in the example's Keycloak, use
[`scripts/create-test-tenant.sh`](https://github.com/cfchase/ai-grid-deployment-proto/blob/main/scripts/create-test-tenant.sh),
which generates the password into a file.

1. Get the user's access token from the issuer and write it into a header file. The client secret and password are
   read from files, so neither appears on a command line:

   ```sh
   T=$(mktemp -d); (umask 077
   curl -sS "IDP_ISSUER_URL/protocol/openid-connect/token" \
     --data-urlencode grant_type=password --data-urlencode client_id=IDP_CLIENT_ID \
     --data-urlencode client_secret@CLIENT_SECRET_FILE --data-urlencode username=TENANT_USER \
     --data-urlencode password@TENANT_PASSWORD_FILE --data-urlencode scope=openid \
     | jq -r '"Authorization: Bearer " + .access_token' > "$T/auth")
   ```

   The password grant must be enabled on the client (the example's realm enables it for testing). Tenants
   normally get an API key from the Org UI instead. *(API keys: unverified.)*

2. List the models:

   ```sh
   curl -sS -H @"$T/auth" https://MAAS_HOST/v1/models | jq -c '[.data[].id]'
   ```

   You should see `["smollm2-chat"]`.

3. Call the model, and see which site served it:

   ```sh
   curl -sS -D "$T/h" -H @"$T/auth" -H 'X-MaaS-Subscription: SUBSCRIPTION_ID' -H 'Content-Type: application/json' \
     -d '{"model":"smollm2-chat","messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":20}' \
     https://MAAS_HOST/v1/chat/completions | jq -r '.choices[0].message.content'
   grep -i '^x-grid-site' "$T/h"
   ```

   You should see a short reply and `x-grid-site: SITE`.

4. Check the refusals:

   ```sh
   curl -sS -o /dev/null -w '%{http_code}\n' https://MAAS_HOST/v1/models
   curl -sS -o /dev/null -w '%{http_code}\n' -H @"$T/auth" -H 'X-MaaS-Subscription: OTHER_SUBSCRIPTION' \
     -H 'Content-Type: application/json' -d '{"model":"smollm2-chat","messages":[{"role":"user","content":"Hi"}]}' \
     https://MAAS_HOST/v1/chat/completions
   rm -rf "$T"
   ```

   You should see `401` without a token, and `403` with a subscription that doesn't cover the model.

Replace the following throughout:

- `IDP_ISSUER_URL`, `IDP_CLIENT_ID`: your `idpIssuerURL` and `idpClientID` inputs.
- `CLIENT_SECRET_FILE`: a file holding the client's secret.
- `TENANT_USER`, `TENANT_PASSWORD_FILE`: the tenant user and a file holding their password.
- `MAAS_HOST`: the ingress site's MaaS hostname, `PREFIX.apps.CLUSTER_DOMAIN`.
- `SUBSCRIPTION_ID`, `OTHER_SUBSCRIPTION`: the subscription you created, and one that doesn't include the model.

## Checkpoint

- A tenant's chat call returns `200` with an `x-grid-site` header.
- Calls without a token get `401`, and calls under the wrong subscription get `403`.
