# Corso Kubernetes 2026 - Demo Microservizi

Questo progetto contiene una demo composta da:

- `services/catalog-service`: microservizio Java Spring Boot per il catalogo prodotti (PostgreSQL).
- `services/order-service`: microservizio Java Spring Boot per la gestione ordini (MongoDB).
- `frontend`: interfaccia web statica servita da Nginx.
- `k8s`: manifest Kubernetes per deploy completo dell'applicazione.

## Struttura principale

```text
.
├── services/
│   ├── catalog-service/
│   └── order-service/
├── frontend/
└── k8s/
```

## Prerequisiti

- Docker
- `kubectl`
- `k3d`

## Build delle immagini Docker

Dalla root del repository:

```bash
docker build -t catalog-service:latest ./services/catalog-service
docker build -t order-service:latest ./services/order-service
docker build -t frontend:latest ./frontend
```

## Import immagini nel cluster k3d

Se hai gia' un cluster (es. `corso-demo`), importa le immagini locali:

```bash
k3d image import catalog-service:latest -c corso-demo
k3d image import order-service:latest -c corso-demo
k3d image import frontend:latest -c corso-demo
```

Per verificare il nome del cluster:

```bash
k3d cluster list
```

## Deploy su Kubernetes

Applica tutti i manifest:

```bash
kubectl apply -f k8s
```

Verifica risorse nel namespace `corso-demo`:

```bash
kubectl get all -n corso-demo
```
