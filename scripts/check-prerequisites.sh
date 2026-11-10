#!/usr/bin/env bash
# Reports, one line each, whether a cluster has the infrastructure an install
# step needs before AI Grid components go on it. Read only: it never changes
# the cluster and never reads a Secret's data.
#
# Usage: scripts/check-prerequisites.sh --step hub|spoke --context CTX [--expect-idp library|own]
#
#   --step hub     the hub, before and after its infrastructure step: OpenShift
#                  version, a default StorageClass, cert-manager's CRDs, the
#                  quay.io/rhoai pull-secret file ($RHOAI_QUAY_PULL_SECRET_FILE)
#                  and the object-storage Secret (apps/object-storage/README.md)
#   --step spoke   a spoke before it joins ACM: OpenShift version and a default
#                  StorageClass (the hub's policies deliver its pull secret)
#   --expect-idp   the tenant IdP on this cluster: own (the deployment's own,
#                  on the Red Hat build of Keycloak) checks the RHBK CRDs;
#                  library (apps/keycloak, a plain Deployment) adds no check,
#                  since what it needs are components (apps/maas-db,
#                  apps/external-secrets)
#
# Prints OK or MISSING per check and exits 1 if anything is MISSING, 2 on bad
# usage.
set -Eeuo pipefail

usage() { sed -n '5,21p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2; }

step="" context="" idp=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) step=${2:-}; shift 2 ;;
    --context) context=${2:-}; shift 2 ;;
    --expect-idp) idp=${2:-}; shift 2 ;;
    -h|--help) usage ;;
    *) echo "unknown argument: $1" >&2; usage ;;
  esac
done
case "$step" in hub|spoke) ;; *) echo "--step must be hub or spoke" >&2; usage ;; esac
[ -n "$context" ] || { echo "--context is required" >&2; usage; }
case "$idp" in ""|library|own) ;; *) echo "--expect-idp must be library or own" >&2; usage ;; esac

MIN_MINOR=21
missing=0
oc_() { oc --context "$context" "$@"; }
report() { # OK|MISSING what detail
  printf '%-8s %-40s %s\n' "$1" "$2" "${3:-}"
  [ "$1" = OK ] || missing=1
}

# OpenShift 4.21 or later.
version=$(oc_ get clusterversion version -o jsonpath='{.status.desired.version}' 2>/dev/null || true)
minor=$(echo "$version" | awk -F. '$1 == 4 {print $2}')
if [ -n "$minor" ] && [ "$minor" -ge "$MIN_MINOR" ]; then
  report OK "OpenShift 4.$MIN_MINOR or later" "$version"
else
  report MISSING "OpenShift 4.$MIN_MINOR or later" "${version:-unreadable}"
fi

# A default StorageClass: databases, S4 and Loki claim PVCs without naming one.
default_sc=$(oc_ get storageclass -o jsonpath='{range .items[*]}{.metadata.name} {.metadata.annotations.storageclass\.kubernetes\.io/is-default-class}{"\n"}{end}' 2>/dev/null |
  awk '$2 == "true" {print $1}' | paste -sd, - || true)
if [ -n "$default_sc" ]; then report OK "default StorageClass" "$default_sc"; else report MISSING "default StorageClass" "none annotated is-default-class"; fi

crds_present() { local crd; for crd in "$@"; do oc_ get crd "$crd" -o name >/dev/null 2>&1 || return 1; done; }

if [ "$step" = hub ]; then
  # cert-manager: grid enrollment issues its CA and identities with it. The
  # library doesn't install it on a hub unless apps/cert-manager is selected.
  if crds_present certificates.cert-manager.io issuers.cert-manager.io clusterissuers.cert-manager.io; then
    report OK "cert-manager CRDs"
  else
    report MISSING "cert-manager CRDs" "install cert-manager, or select apps/cert-manager"
  fi
  # The pull secret for quay.io/rhoai, which apps/rhoai-prerequisites
  # distributes; never read here, only found.
  if [ -n "${RHOAI_QUAY_PULL_SECRET_FILE:-}" ] && [ -s "$RHOAI_QUAY_PULL_SECRET_FILE" ]; then
    report OK "quay.io/rhoai pull secret file" "\$RHOAI_QUAY_PULL_SECRET_FILE"
  else
    report MISSING "quay.io/rhoai pull secret file" "set RHOAI_QUAY_PULL_SECRET_FILE to a non-empty file"
  fi
  # The object-storage contract. Missing before the infrastructure step.
  if oc_ get secret thanos-object-storage -n open-cluster-management-observability -o name >/dev/null 2>&1; then
    report OK "object storage" "open-cluster-management-observability/thanos-object-storage"
  else
    report MISSING "object storage" "Secret open-cluster-management-observability/thanos-object-storage (apps/object-storage)"
  fi
fi

if [ "$idp" = own ]; then
  if crds_present keycloaks.k8s.keycloak.org keycloakrealmimports.k8s.keycloak.org; then
    report OK "RHBK CRDs"
  else
    report MISSING "RHBK CRDs" "install the Red Hat build of Keycloak operator"
  fi
fi

exit "$missing"
