# Manifest Kubernetes

I file sono ordinati per prefisso numerico e possono essere applicati tutti insieme:

```bash
kubectl apply -f k8s
```

Ordine logico:

1. `00-namespace.yaml`: namespace dedicato.
2. `01-secrets.yaml`: credenziali DB.
3. `02-postgres-statefulset.yaml`: PostgreSQL con `StatefulSet` + PVC.
4. `03-mongo-statefulset.yaml`: MongoDB con `StatefulSet` + PVC.
5. `04-catalog-service.yaml`: deployment + service catalog.
6. `05-order-service.yaml`: deployment + service order.
7. `06-frontend.yaml`: deployment + service frontend.
8. `07-ingress.yaml`: routing HTTP esterno.
