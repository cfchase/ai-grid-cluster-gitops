# Step 1: prepare the hub

In this step you check the hub's infrastructure, install OpenShift GitOps, and apply your root. From then on, Argo CD
installs everything from git.

Set these once in your shell for this section:

```sh
export HUB_CONTEXT=HUB_CONTEXT_NAME
export LIBRARY_SHA=$(sed -n 's#.*bootstrap/hub?ref=\([0-9a-f]\{40\}\).*#\1#p' root/kustomization.yaml)
```

Replace `HUB_CONTEXT_NAME` with the hub's kubeconfig context. Run every command in this section from your deployment
repository's checkout.

## 1. Add a break-glass admin

If the hub's only sign-in is an external identity provider, add an htpasswd admin first
([cluster sign-in and admins](components/cluster-sign-in.md)):

```sh
oc config use-context "$HUB_CONTEXT"
scripts/add-htpasswd-admin.sh --kubeconfig "$KUBECONFIG" --password-file HUB_ADMIN_PASSWORD_FILE
```

Replace `HUB_ADMIN_PASSWORD_FILE` with a path outside any repository, such as `~/.ai-grid/hub-admin`. The script
generates a password into that file (mode 600) if it doesn't exist and never prints it. If your `KUBECONFIG` lists
several files, pass a single kubeconfig file instead.

You should see the script confirm the sign-in. Sign in once in the web console as `admin` with the
`htpasswd` provider to confirm it yourself. The existing providers are unchanged.

## 2. Check the infrastructure

1. Get the library at your pinned commit:

   ```sh
   git clone -q --filter=blob:none LIBRARY_REPO_URL ../library && git -C ../library checkout -q "$LIBRARY_SHA"
   ```

2. Run the hub check:

   ```sh
   RHOAI_QUAY_PULL_SECRET_FILE=QUAY_AUTH_FILE bash ../library/scripts/check-prerequisites.sh --step hub --context "$HUB_CONTEXT"
   ```

   Replace `QUAY_AUTH_FILE` with your container auth file that holds the `quay.io/rhoai` login, such as
   `~/.config/containers/auth.json`. The check reads nothing from it; it only checks the file exists.

   The output is similar to the following:

   ```text
   OK       OpenShift 4.21 or later                  4.22.18
   OK       default StorageClass                     gp3-csi
   OK       cert-manager CRDs
   OK       quay.io/rhoai pull secret file           $RHOAI_QUAY_PULL_SECRET_FILE
   MISSING  object storage                           Secret open-cluster-management-observability/thanos-object-storage (apps/object-storage)
   ```

3. Fix each `MISSING` line that you didn't select a component for:

   | Line | Fix |
   |---|---|
   | OpenShift version | Upgrade the cluster to 4.21 or later. |
   | default StorageClass | Annotate one StorageClass `storageclass.kubernetes.io/is-default-class=true`. |
   | cert-manager CRDs | Install the cert-manager Operator for Red Hat OpenShift, or select `apps/cert-manager` ([cert-manager](components/cert-manager.md)). |
   | quay.io/rhoai pull secret file | Log in: `podman login quay.io` with a `quay.io/rhoai` robot token ([pull secret](components/pull-secret.md)). |
   | object storage | Expected here if you selected `apps/object-storage/s4` or `odf`: it appears in step 2. If you bring your own, create the Secret now ([object storage](components/object-storage.md)). |

4. If you bring your own tenant identity provider, check its two hub objects as well:

   ```sh
   bash ../library/scripts/check-prerequisites.sh --step hub --context "$HUB_CONTEXT" --expect-idp own \
     --idp-secret IDP_SECRET_NAMESPACE/IDP_SECRET_NAME:IDP_SECRET_KEY --idp-ca IDP_CA_NAMESPACE/IDP_CA_NAME:IDP_CA_KEY
   ```

   Replace the placeholders with your `idpClientSecret*` and `idpCA*` inputs. You should see `OK` on the
   `IdP client secret` and `IdP CA` lines. If your IdP runs on the hub from your own apps (as the example's does),
   these appear only after step 2; run this check again then.

## 3. Install OpenShift GitOps and apply your root

`bootstrap.sh` installs OpenShift GitOps from the library at your pinned commit, applies `root/` once, and seeds the
`quay.io/rhoai` pull secret that the prerequisites Policy copies to every site. It reads the credential from the auth
file and never prints it.

```sh
KUBECONFIG=HUB_KUBECONFIG RHOAI_QUAY_AUTH_FILE=QUAY_AUTH_FILE ./bootstrap.sh
```

Replace the following:

- `HUB_KUBECONFIG`: a kubeconfig file whose current context is the hub.
- `QUAY_AUTH_FILE`: the auth file from the previous step.

If the file holds only a general `quay.io` login, the script stops: that login would be copied to every site. Add a
robot token for `quay.io/rhoai`, or accept the risk with `RHOAI_QUAY_ALLOW_GENERIC_LOGIN=1`.

You should see `Bootstrapped.` at the end. The script runs the prerequisites check first and reports what's missing;
the items that this script and step 2 install are expected to be missing.

## 4. Check that Argo CD follows your repository

```sh
oc --context "$HUB_CONTEXT" get applications.argoproj.io -n openshift-gitops deployment-root
oc --context "$HUB_CONTEXT" get applicationset apps -n openshift-gitops \
  -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.message}{"\n"}{end}'
```

On an ACM hub, `oc get application` means ACM's kind; always write `applications.argoproj.io`.

You should see `deployment-root` `Synced`, and the ApplicationSet conditions with `ParametersGenerated=True` and no
`ErrorOccurred=True`. A message `missing input: NAME` or `invalid input: NAME` means an input in your root
([section 2](02-repositories.md#4-set-every-input)); fix it in git and push.

## Checkpoint

- You can sign in to the hub as the break-glass admin.
- The hub check shows `OK` for everything except the items your selected components install.
- `deployment-root` is `Synced`, and the root ApplicationSet `apps` reports no error.
