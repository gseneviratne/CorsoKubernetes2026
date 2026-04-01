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

## Creazione cluster k3d

Crea il cluster usando la configurazione presente nel repository:

```bash
k3d cluster create --config k3d/cluster-demo.yaml
```

## Deploy Ingress Controller

Il cluster viene creato con Traefik disabilitato, quindi installa `ingress-nginx`:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
kubectl rollout status deployment/ingress-nginx-controller -n ingress-nginx
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

## Test frontend

Dopo il deploy, puoi verificare che il frontend funzioni correttamente con questi step:

1. Controlla che i pod del frontend siano in stato `Running`:

```bash
kubectl get pods -n corso-demo -l app=frontend
```

2. Apri il frontend nel browser:

- aggiungi una entry in `/etc/hosts`:

```bash
echo "127.0.0.1 corso-k8s.local" | sudo tee -a /etc/hosts
```

- URL: [http://corso-k8s.local](http://corso-k8s.local)

Esito atteso:
- caricamento pagina con titolo "Corso Kubernetes 2026"
- i pulsanti di test API (`Carica Catalogo` e `Carica Ordini`) sono visibili
