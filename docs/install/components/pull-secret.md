# Registry pull secret and image mirror

> **Important:** This release installs pre-release OpenShift AI 3.6 builds. Every cluster pulls them from
> `quay.io/rhoai`, and the image mirror the library delivers sends every `registry.redhat.io/rhaii*` image, model
> runtimes included, to `registry.stage.redhat.io` with `NeverContactSource`. You need logins for both registries,
> which Red Hat gives only to early-access partners; ask your Red Hat contact. Without a stage login, model images fail
> to pull on every site. What changes at general availability (the catalog source, the mirror, which logins you need)
> isn't decided in the library yet ([known gaps](../appendix-c-gaps.md)).

OpenShift AI 3.6 pre-release builds come from `quay.io/rhoai`, which needs a login, and their images keep their
`registry.redhat.io` names, so every cluster needs that login and an image mirror. You give the login once, on the hub,
and [OpenShift AI prerequisites](./rhoai-prerequisites.md) delivers it and the mirror to every managed cluster, which
[OpenShift AI](./rhoai.md) and every model image depend on.

| | |
|---|---|
| Runs on | hub (the credential); delivered to the hub and every site |
| Library component | `apps/rhoai-prerequisites` (select `apps/rhoai-prerequisites/application.yaml`); the credential is infrastructure you provide |
| Choices | Use ours · Bring your own |

## Use ours

1. Get a `quay.io` login that can pull the `quay.io/rhoai` repositories. Prefer a robot account scoped to
   `quay.io/rhoai`. Sign in with it so your container auth file holds a `quay.io/rhoai` entry:

   ```sh
   podman login quay.io/rhoai
   ```

2. Select `apps/rhoai-prerequisites` (see its [page](./rhoai-prerequisites.md)):

   ```yaml
   - path: apps/rhoai-prerequisites/application.yaml
   ```

3. Run the library's [`scripts/bootstrap-hub.sh`](../../../scripts/bootstrap-hub.sh) with the auth file, from your
   deployment checkout:

   ```sh
   KUBECONFIG=HUB_KUBECONFIG RHOAI_QUAY_AUTH_FILE=AUTH_FILE ../library/scripts/bootstrap-hub.sh --deployment .
   ```

   Replace the following:

   - `HUB_KUBECONFIG`: a kubeconfig with a `cluster-admin` session on the hub.
   - `AUTH_FILE`: your container auth file, such as `${XDG_RUNTIME_DIR}/containers/auth.json` or
     `~/.config/containers/auth.json`.

   The script reads the `quay.io/rhoai` entry, never prints it, and runs the library's
   [`create-hub-secret.sh`](../../../apps/rhoai-prerequisites/create-hub-secret.sh). That creates Secret
   `rhoai-prerequisites/rhoai-quay-pull-secret` (type `kubernetes.io/dockerconfigjson`, key `.dockerconfigjson`)
   on the hub. Nothing goes into git.

   If your auth file has only a general `quay.io` login, the script stops. To use that login anyway, set
   `RHOAI_QUAY_ALLOW_GENERIC_LOGIN=1`. The hub Secret then holds your general `quay.io` credential, although the
   Policy writes it to each cluster only as a `quay.io/rhoai` entry.

4. Add a `registry.stage.redhat.io` login to the same auth file before you run the bootstrap script:
   `podman login registry.stage.redhat.io`. The mirror sends every `registry.redhat.io/rhaii*` image, model runtimes
   included, there and never contacts the source, so every site needs it. `bootstrap-hub.sh` passes it to
   `create-hub-secret.sh` as `RHOAI_STAGE_PULL_SECRET`, and warns when the auth file has none. *(Unverified: the
   tested site already had the model image.)*

The hub's `rhoai-prerequisites` Policy then delivers, to every cluster in the `global` cluster set, the hub included:

- Secret `openshift-marketplace/rhoai-catalog-pull-secret`, for the OpenShift AI catalog image.
- The hub Secret's registries merged into `openshift-config/pull-secret`. Existing entries stay; the hub's win for
  the registries it holds.
- ImageDigestMirrorSet `quay-registry`: `registry.redhat.io/rhoai` from `quay.io/rhoai`, and
  `registry.redhat.io/rhaii`, `rhaii-early-access` and `rhaii-fast` from `registry.stage.redhat.io`, all with
  `mirrorSourcePolicy: NeverContactSource`.

Delivering the mirror reboots each cluster's nodes once: the Machine Config Operator rolls the change out node by
node. Plan for it when a cluster joins ACM, the hub included. Pull secret updates roll out without a reboot.

### Verify

Check without showing any credential:

```sh
oc -n rhoai-prerequisites get secret rhoai-quay-pull-secret \
  -o custom-columns='NAME:.metadata.name,TYPE:.type'
oc -n rhoai-prerequisites get policies
oc --context SITE_CONTEXT get imagedigestmirrorset quay-registry
oc --context SITE_CONTEXT -n openshift-config get secret pull-secret \
  -o go-template='{{index .data ".dockerconfigjson" | base64decode}}' | jq -r '.auths | keys[]'
oc --context SITE_CONTEXT get machineconfigpool
```

Replace `SITE_CONTEXT` with your kubeconfig context for a site.

You should see the Secret with type `kubernetes.io/dockerconfigjson`, Policy `rhoai-prerequisites` `Compliant`, the
mirror, `quay.io/rhoai` among the registry names (the command prints names only), and every MachineConfigPool
`UPDATED` `True` once the rollout finishes.

## Bring your own

Two cases:

- **You create the hub Secret yourself.** Create `rhoai-prerequisites/rhoai-quay-pull-secret`, type
  `kubernetes.io/dockerconfigjson`, whose `.dockerconfigjson` has an `auths` entry `quay.io/rhoai` or `quay.io`, and
  optionally other registries. Use `create-hub-secret.sh` with `RHOAI_QUAY_PULL_SECRET` (base64 of
  `USERNAME:PASSWORD`) read from the terminal, so the value isn't in your shell history:

  ```sh
  read -s RHOAI_QUAY_PULL_SECRET && export RHOAI_QUAY_PULL_SECRET
  HUB_CONTEXT=HUB_CONTEXT bash LIBRARY_CHECKOUT/apps/rhoai-prerequisites/create-hub-secret.sh
  ```

  Replace `HUB_CONTEXT` with your hub's kubeconfig context and `LIBRARY_CHECKOUT` with a checkout of the library at
  your pinned commit.

- **Your clusters already have the credentials and mirror** (for example, a disconnected install with its own mirror
  registry). The Policy still delivers ImageDigestMirrorSet `quay-registry`, which can conflict with your own mirrors.
  The library has no switch to turn it off. *(Unverified.)*

## Skip

You can't skip it while the library installs OpenShift AI 3.6 pre-release builds: without the login, the catalog
image and operator bundles don't pull, and OpenShift AI never installs on any site. Until the hub Secret exists, the
pull-secret Policy renders nothing and changes no cluster; the mirror is delivered anyway.

## Upgrade

The mirror and Policy move with the library pin. To rotate the credential, run `create-hub-secret.sh` again; ACM
copies the new value to every cluster, and the hub's value wins over the old one. Deleting the hub Secret doesn't
remove credentials already on the clusters.

## Known issues

- **Symptom:** The bootstrap script reports `quay.io/rhoai pull secret file` `MISSING` from the prerequisites check,
  then succeeds.
  **Cause:** `scripts/check-prerequisites.sh` looks for `RHOAI_QUAY_PULL_SECRET_FILE`; the example script uses
  `RHOAI_QUAY_AUTH_FILE`.
  **Workaround:** Ignore that line during bootstrap, or export both variables with the same path.
- **Symptom:** A site's nodes go `SchedulingDisabled` one by one soon after it joins ACM.
  **Cause:** The image mirror's Machine Config rollout.
  **Workaround:** None needed; wait for every MachineConfigPool to report `UPDATED`. Removing the mirror later
  reboots the nodes again.
