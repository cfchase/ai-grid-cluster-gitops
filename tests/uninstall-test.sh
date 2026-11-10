#!/usr/bin/env bash
# Tests for scripts/uninstall.sh's safety checks and dry run, with stub oc and
# curl. Nothing here reaches a cluster.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
T=$(cd "$(mktemp -d)" && pwd -P); trap 'rm -rf "$T"' EXIT
total=0 fails=0
mkdir -p "$T/bin"
cp tests/fixtures/uninstall-applications.json "$T/apps.json"
echo hunter2-test > "$T/pw"; touch "$T/hub.kc" "$T/site.kc"

# Stub oc. The world: $STUB/<kubeconfig basename>.* files.
cat > "$T/bin/oc" <<'STUB'
#!/usr/bin/env bash
kc="" ; args=()
while [ $# -gt 0 ]; do case "$1" in --kubeconfig) kc=$(basename "$2"); shift 2 ;; *) args+=("$1"); shift ;; esac; done
set -- "${args[@]}"; w="$STUB/$kc"
echo "oc $kc $*" >> "$STUB/calls"
case "$*" in
  "whoami --show-server") cat "$w.api" ;;
  "get oauth cluster -o jsonpath="*) cat "$w.idps" ;;
  "get route oauth-openshift -n openshift-authentication -o jsonpath={.spec.host}") echo "oauth.$kc" ;;
  "config view --minify --raw -o json") echo '{"users":[{"user":{}}]}' ;;
  "auth can-i * * --all-namespaces") cat "$STUB/can-i" ;;
  "get clusterrolebindings -o json") cat "$w.crbs" ;;
  "get applications.argoproj.io -n openshift-gitops -o json") cat "$STUB/apps.json" ;;
  "get managedclusters -o jsonpath="*) cat "$w.managed" 2>/dev/null ;;
  "get managedcluster local-cluster -o jsonpath="*) echo "" ;;
  "get managedcluster site-b") [ -s "$w.managed" ] && grep -qx site-b "$w.managed" ;;
  "get klusterlet klusterlet -o jsonpath="*) cat "$w.klusterlet" 2>/dev/null ;;
  "get klusterlet klusterlet") [ -s "$w.klusterlet" ] ;;
  get\ ns\ *) grep -qx "$3" "$w.ns" 2>/dev/null ;;
  get\ applicationsets.argoproj.io*) echo "applicationset.argoproj.io/apps" ;;
  get\ applications.argoproj.io\ -n\ openshift-gitops\ -o\ name) echo "application.argoproj.io/acm" ;;
  get\ secrets*) echo '{"items":[]}' ;;
  delete*|patch*|label*) echo "WRITE: $*" >> "$STUB/writes" ;;
  get*" -o "*|get*--no-headers*) exit 0 ;;   # an empty list
  *) exit 1 ;;                                # not found
esac
STUB
cat > "$T/bin/curl" <<'STUB'
#!/usr/bin/env bash
nf=""; while [ $# -gt 0 ]; do [ "$1" = --netrc-file ] && nf=$2; shift; done
grep -q "password hunter2-test" "$nf" && printf 'https://x/#access_token=sha256~stubtoken&x=1' || printf 'https://x/#error=denied'
STUB
chmod +x "$T/bin/oc" "$T/bin/curl"

world() { # hub and site clusters that pass every check
  rm -f "$T/calls" "$T/writes"
  for c in hub site; do
    echo "https://api.$c.example.com:6443" > "$T/$c.kc.api"
    printf 'OpenID\nHTPasswd\n' > "$T/$c.kc.idps"
    echo '{"items":[{"metadata":{"name":"cluster-admin-0"},"roleRef":{"name":"cluster-admin"},"subjects":[{"kind":"User","name":"admin"}]}]}' > "$T/$c.kc.crbs"
  done
  echo site-b > "$T/hub.kc.managed"; echo site-b > "$T/site.kc.klusterlet"; echo yes > "$T/can-i"
}
run() { env -i PATH="$T/bin:/usr/bin:/bin" HOME="$T" STUB="$T" WIPE_PROTECT_NAMESPACES="${WPN:-}" bash scripts/uninstall.sh "$@" 2>&1; }
HUB=(--hub-kubeconfig "$T/hub.kc" --expect-hub-api https://api.hub.example.com:6443 --admin-password-file "$T/pw")
SITE=(--site site-b --site-kubeconfig "$T/site.kc" --expect-site-api https://api.site.example.com:6443)
t() { # name want_rc expect_grep args...
  local name=$1 want=$2 expect=$3; shift 3; local rc out
  total=$((total+1)); out=$(run "$@") && rc=0 || rc=$?
  if [ "$rc" = "$want" ] && grep -qE -- "$expect" <<<"$out"; then echo "   ok   $name"
  else fails=$((fails+1)); echo "   FAIL $name (rc=$rc, wanted $want; output:)"; echo "$out" | tail -15; fi
}

world; t "wrong hub refused" 1 "doesn't point at https://api.other" --step hub --dry-run --hub-kubeconfig "$T/hub.kc" --expect-hub-api https://api.other.example.com:6443 --admin-password-file "$T/pw"
world; t "wrong site refused" 1 "doesn't point at" --step site --dry-run "${HUB[@]}" --site site-b --site-kubeconfig "$T/site.kc" --expect-site-api https://api.hub.example.com:6443
world; printf 'OpenID\n' > "$T/site.kc.idps"; t "a site with no htpasswd provider is refused" 1 "site-b: no HTPasswd" --step site --dry-run "${HUB[@]}" "${SITE[@]}"
world; echo wrong > "$T/pw2"; t "a password that doesn't sign in is refused" 1 "can't sign in" --step hub --dry-run --hub-kubeconfig "$T/hub.kc" --expect-hub-api https://api.hub.example.com:6443 --admin-password-file "$T/pw2"
world; echo no > "$T/can-i"; t "an admin without cluster-admin is refused" 1 "isn't cluster-admin" --step hub --dry-run "${HUB[@]}"
world; echo '{"items":[{"metadata":{"name":"cluster-admin-admin"},"roleRef":{"name":"cluster-admin"},"subjects":[{"kind":"User","name":"admin"}]}]}' > "$T/hub.kc.crbs"
t "refused when the admin's only binding is one it deletes" 1 "only cluster-admin binding" --step hub --dry-run "${HUB[@]}"
world; echo site-a > "$T/site.kc.klusterlet"; t "a site whose klusterlet names another cluster is refused" 1 "klusterlet says it's site-a" --step site --dry-run "${HUB[@]}" "${SITE[@]}"
world; t "local-cluster as a site is refused" 1 "isn't supported yet" --step site --dry-run "${HUB[@]}" --site local-cluster --site-kubeconfig "$T/site.kc" --expect-site-api https://api.site.example.com:6443
world; t "the hub refuses while sites are managed" 1 "sites are still managed" --step hub "${HUB[@]}"
world; t "the hub dry run warns about managed sites and lists the plan" 0 "would delete: MultiClusterHub" --step hub --dry-run "${HUB[@]}"
world; out=$(run --step hub --dry-run "${HUB[@]}"); total=$((total+1))
if [ ! -s "$T/writes" ] && grep -q "dry run: nothing deleted" <<<"$out"; then echo "   ok   the dry run writes nothing"; else fails=$((fails+1)); echo "   FAIL the dry run wrote: $(cat "$T/writes" 2>/dev/null)"; fi
total=$((total+1)); if grep -q stubtoken "$T/calls"; then fails=$((fails+1)); echo "   FAIL the admin's token reached an oc command line"; else echo "   ok   the admin's token never reaches a command line"; fi
world; t "the site dry run plans the detach, then the site's objects" 0 "would delete: managedcluster site-b" --step site --dry-run "${HUB[@]}" "${SITE[@]}"
world; t "a cluster-scoped object is deleted without a namespace" 0 "would delete: Namespace redhat-ods-applications\$" --step site --dry-run "${HUB[@]}" "${SITE[@]}"
world; t "a namespaced object is deleted in its namespace" 0 "would delete: Cluster.v1.postgresql.cnpg.io maas-db -n maas-db" --step hub --dry-run "${HUB[@]}"
world; echo hunter2-test > "$T/site-pw"; echo wrong > "$T/pw-hub-only"
t "the site's own password file is used for the site" 1 "site-b: admin can't sign in" --step site --dry-run --hub-kubeconfig "$T/hub.kc" --expect-hub-api https://api.hub.example.com:6443 --admin-password-file "$T/pw" --site-admin-password-file "$T/pw-hub-only" "${SITE[@]}"
world; printf 'ai-tenants\nopen-cluster-management\n' > "$T/site.kc.ns"; out=$(run --step site --dry-run "${HUB[@]}" "${SITE[@]}"); total=$((total+1))
k=$(grep -n "would delete: klusterlet klusterlet" <<<"$out" | cut -d: -f1); n=$(grep -n "would delete: ns open-cluster-management\$" <<<"$out" | cut -d: -f1)
if [ -n "$k" ] && [ -n "$n" ] && [ "$k" -lt "$n" ]; then echo "   ok   the site's leftover namespaces are swept, after its Klusterlet"
else fails=$((fails+1)); echo "   FAIL the site's leftover namespaces are swept, after its Klusterlet"; fi
world; printf 'ai-tenants\n' > "$T/site.kc.ns"; out=$(run --step site --dry-run "${HUB[@]}" "${SITE[@]}"); total=$((total+1))
if grep -q "would delete: ns ai-tenants" <<<"$out" && ! grep -q "would delete: ns redhat-ai-gateway-infra" <<<"$out"; then echo "   ok   only leftover namespaces that exist are swept"
else fails=$((fails+1)); echo "   FAIL only leftover namespaces that exist are swept"; fi
world; printf 'ai-tenants\n' > "$T/site.kc.ns"; WPN=ai-tenants t "a deployment's protected namespace isn't swept" 0 "kept \(protected namespace\): ai-tenants" --step site --dry-run "${HUB[@]}" "${SITE[@]}"
world; printf 'default-broker\n' > "$T/hub.kc.ns"; t "the hub's leftover namespaces are swept" 0 "would delete: ns default-broker" --step hub --dry-run "${HUB[@]}"
world; printf 'custom-resources\tCluster.v1.postgresql.cnpg.io\tmaas-db\tsaved-plan-object\n' > "$T/plan.tsv"
t "a saved plan file is reused" 0 "would delete: Cluster.v1.postgresql.cnpg.io saved-plan-object -n maas-db" --step site --dry-run "${HUB[@]}" "${SITE[@]}" --plan-file "$T/plan.tsv"
world; rm -f "$T/plan2.tsv"; run --step site --dry-run "${HUB[@]}" "${SITE[@]}" --plan-file "$T/plan2.tsv" >/dev/null; total=$((total+1))
if [ ! -e "$T/plan2.tsv" ]; then echo "   ok   a dry run doesn't write the plan file"; else fails=$((fails+1)); echo "   FAIL a dry run wrote the plan file"; fi
world; t "the site's Submariner add-on goes before the detach" 0 "would delete: managedclusteraddons.addon.open-cluster-management.io submariner -n site-b" --step site --dry-run "${HUB[@]}" "${SITE[@]}"
world; printf 'acm\tMultiClusterHub.v1.operator.open-cluster-management.io\topen-cluster-management\tsaved-mch\n' > "$T/hubplan.tsv"
t "the hub step reuses a saved plan file" 0 "would delete: MultiClusterHub.v1.operator.open-cluster-management.io saved-mch" --step hub --dry-run "${HUB[@]}" --plan-file "$T/hubplan.tsv"
echo "uninstall tests: $((total-fails)) ok, $fails failed"; exit "$fails"
