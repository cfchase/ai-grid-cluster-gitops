# Appendix C: known gaps

What this release of the library doesn't do yet. Each is a candidate for a library change.

| Gap | Effect | Today |
|---|---|---|
| No input for the MaaS gateway's client-facing certificate | Tenants see the in-cluster service certificate | A per-site values override and your own Certificate ([step 4](06-join-grid.md#1-add-the-sites-values)) |
| The MaaS gateway's port 80 listener serves MaaS in cleartext | Calls can be made without TLS | Chart default; not changed |
| No object-storage input for Loki | `ai-grid-o11y` and `ai-grid-usage-logs` need ODF's NooBaa and AWS `gp3-csi` | Skip them ([observability](components/observability.md)) |
| No per-cluster values for MetalLB from the deployment | Bare-metal sites can't set pools from your repository | Labels only ([load balancers](components/load-balancers.md)) |
| Keycloak's import-then-start layout | A Keycloak version change can't migrate its database | `Recreate`, backups ([tenant identity provider](components/tenant-idp.md)) |
| The console can't create organizations on Red Hat build of Keycloak 26.4 or 26.6 | Organizations need community Keycloak 26.8.0 | Community Keycloak |
| The library Keycloak's client secret shares a Secret with its admin password | The tenant Policy can read the admin password | Bring your own IdP with a dedicated Secret |
| No bring-your-own MaaS database or Redis | Both run from the library | Use ours |
| No uninstall procedure | Removing the root leaves everything in place | Wipe each site; rebuild the hub |
| Hub sizing not established | | Size from the tested hub's components |
| No GA catalog path | The OpenShift AI install uses a nightly catalog and `quay.io/rhoai` | |
