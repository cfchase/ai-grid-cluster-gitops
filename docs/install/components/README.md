# Components in detail

Every page has the same parts: what the component does, where it runs, **Use ours**, **Bring your own**, **Skip**,
**Upgrade** and **Known issues**. Use them with the [decision table](../README.md#your-choices-component-by-component).

## Infrastructure

- [OpenShift GitOps (Argo CD)](openshift-gitops.md)
- [cert-manager and issuers](cert-manager.md)
- [MaaS gateway certificate](maas-certificate.md)
- [Object storage](object-storage.md)
- [Load balancers](load-balancers.md)
- [GPU operator and NFD](gpu-operator.md)
- [Cluster sign-in and admins](cluster-sign-in.md)

## Shared services

- [ACM: Search and observability](acm.md)
- [Submariner](submariner.md)
- [External Secrets](external-secrets.md)
- [MaaS database](maas-db.md)
- [Rate-limit counters (Redis)](limitador-redis.md)
- [Tenant identity provider](tenant-idp.md)
- [Keycloak (the library's tenant IdP)](keycloak.md)
- [Observability and usage logs](observability.md)

## AI Grid

- [OpenShift AI prerequisites: pull secret and image mirror](rhoai-prerequisites.md)
- [OpenShift AI with MaaS](rhoai.md)
- [Grid bootstrap and enrollment](grid-bootstrap.md)
- [Status policies](ai-grid-policies.md)
- [Spoke delivery](spoke-delivery.md)
- [Model delivery](model-delivery.md)
- [Provider console](console.md)
