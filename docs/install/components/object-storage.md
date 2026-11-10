# Object storage

ACM observability (Thanos) on the hub stores the fleet's metrics in an S3 bucket. The library treats the bucket as
infrastructure behind a contract, a Secret that [ACM](./acm.md)'s MultiClusterObservability reads; the provider
console's monitoring pages depend on it.

| | |
|---|---|
| Runs on | hub |
| Library component | `apps/object-storage/s4` (select `apps/object-storage/s4/application.yaml`) or `apps/object-storage/odf` (select `apps/object-storage/odf/application.yaml`) |
| Choices | Use ours (S4 or ODF) · Bring your own S3 |

Select at most one option. The [README](../../../apps/object-storage/README.md) has the details.

## The contract

- Secret `thanos-object-storage` in namespace `open-cluster-management-observability`.
- Key `thanos.yaml`: a [Thanos object-store configuration](https://thanos.io/tip/thanos/storage.md/) of
  `type: s3`, with `bucket`, `endpoint`, `insecure`, `access_key` and `secret_key`.
- The bucket exists.

MultiClusterObservability `observability` waits until the Secret exists.

## Use ours

### S4

S4 is one S3 server pod (Ceph RGW, `quay.io/rh-aiservices-bu/s4`) on a 50 GiB PVC in the observability namespace.
It's a single replica: use it for demos and tests, not production. The verified install used S4.

1. Add both lines to the `files` list in your `root/kustomization.yaml`. S4 needs
   [External Secrets](./external-secrets.md) to generate its keys:

   ```yaml
   - path: apps/external-secrets/application.yaml
   - path: apps/object-storage/s4/application.yaml
   ```

2. Make sure the hub has a default StorageClass.

It reads the `libraryRepoURL` and `libraryRevision` inputs and no file from your deployment repository. You create no
Secret: two external-secrets `Password` generators create the S3 keys once on the hub, and ExternalSecret
`thanos-object-storage` writes `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `thanos.yaml` into the contract
Secret (`refreshPolicy: CreatedOnce`, `deletionPolicy: Retain`). Argo CD also creates PVC `s4-data`, Deployment and
Service `s4` (port `7480`, in-cluster only), a NetworkPolicy that admits only the observability namespace, and a Sync
hook Job `thanos-bucket` that creates bucket `thanos`. The Application never prunes, so deleting a file doesn't delete
stored metrics.

### ODF

The ODF option uses the Multicloud Object Gateway of OpenShift Data Foundation. *(Unverified.)*

1. Select the option, and ODF itself unless the hub already runs it with NooBaa:

   ```yaml
   - path: apps/object-storage/odf/application.yaml
   ```

   To have the library install ODF, keep the root's second generator (the ODF generator, `apps/odf/application.yaml`)
   with its `repoURL`, `revision` and `values` patched like the first one. Otherwise remove it, as the example
   deployment does (`- { op: remove, path: /spec/generators/1 }`). The ODF generator waits for the hub's
   `openshiftVersion-major-minor` label and picks the ODF channel `stable-<version>` from it. If
   `openshift-storage` already has an OperatorGroup, label the hub's ManagedCluster
   `ai-grid/odf-operatorgroup=existing`.

2. Argo CD creates ObjectBucketClaim `acm-observability-thanos` (StorageClass `openshift-storage.noobaa.io`) and a Job
   that renders the claim's bucket and keys into the contract Secret.

### Verify

```sh
oc -n open-cluster-management-observability get secret thanos-object-storage \
  -o go-template='{{if index .data "thanos.yaml"}}thanos.yaml present{{"\n"}}{{end}}'
oc -n open-cluster-management-observability get pods -l app=s4
oc get multiclusterobservability observability \
  -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}{"\n"}'
```

You should see `thanos.yaml present`, the `s4` pod `Running` (S4 only), and `True`. The hub prerequisites check also
reports `OK` for `object storage`.

## Bring your own

Use any S3-compatible store your hub can reach. *(Unverified.)*

1. Create the bucket in your store.
2. Before ACM observability starts, create the contract Secret on the hub, from your vault with an ExternalSecret, or
   by hand from a local file you then delete:

   ```sh
   oc create namespace open-cluster-management-observability --dry-run=client -o yaml | oc apply -f -
   oc -n open-cluster-management-observability create secret generic thanos-object-storage \
     --from-file=thanos.yaml=THANOS_YAML_FILE
   ```

   Replace `THANOS_YAML_FILE` with the path of a file with this content:

   ```yaml
   type: s3
   config:
     bucket: BUCKET
     endpoint: HOST:PORT
     insecure: false
     access_key: ACCESS_KEY
     secret_key: SECRET_KEY
   ```

   Replace `BUCKET`, `HOST:PORT`, `ACCESS_KEY` and `SECRET_KEY` with your store's values. Never commit them.

3. Select neither `apps/object-storage/s4` nor `apps/object-storage/odf`.

Check it with the verify commands, and with the prerequisites check:

```sh
scripts/check-prerequisites.sh --step hub --context HUB_CONTEXT
```

Replace `HUB_CONTEXT` with your hub's kubeconfig context.

## Skip

You can't skip it while you select `apps/acm`: MultiClusterObservability waits for the Secret, so the hub collects no
metrics and the console's monitoring pages stay empty.

## Upgrade

Each option moves with the library pin with no manual step. Neither option prunes, and S4's keys never change after
the first sync, because S4 creates its user from them on first start. Switching options doesn't move stored metrics.

## Known issues

- **Symptom:** You can't select the usage-log stack (`apps/ai-grid-o11y`, `apps/ai-grid-usage-logs`) with S4 or your
  own S3.
  **Cause:** Loki claims its own ODF bucket; it has no object-storage input yet ([gaps](../appendix-c-gaps.md)).
  **Workaround:** Leave the usage-log components out, as the example deployment does, or run ODF.
