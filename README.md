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
- (Opzionale, per Gateway API) Helm 3

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

## Esposizione HTTP: Ingress **oppure** Gateway API

Scegli **un** ingresso principale sulla porta 80 per evitare conflitti tra controller. La demo include sia `k8s/07-ingress.yaml` (Ingress) sia `k8s/09-gateway-api.yaml` (`Gateway` + `HTTPRoute`); il routing (host `corso-k8s.local`, path `/api/catalog`, `/api/orders`, `/`) e' equivalente.

### Prerequisito comune: CRD Gateway API

Per poter applicare `k8s/09-gateway-api.yaml`, installa le CRD del [Gateway API](https://gateway-api.sigs.k8s.io/) (channel **standard**), ad esempio dalla stessa versione supportata da NGINX Gateway Fabric:

```bash
kubectl kustomize "https://github.com/nginx/nginx-gateway-fabric/config/crd/gateway-api/standard?ref=v2.5.0" | kubectl apply -f -
```

Se non usi affatto Gateway API, puoi omettere questo passaggio e applicare i manifest `k8s` tranne `09-gateway-api.yaml`.

### Opzione A: Ingress NGINX

Il cluster viene creato con Traefik disabilitato. Installa `ingress-nginx`:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
kubectl rollout status deployment/ingress-nginx-controller -n ingress-nginx
```

### Opzione B: Gateway API (NGINX Gateway Fabric)

Installa il controller che espone la `GatewayClass` **`nginx`** (documentazione ufficiale: [Install with Helm](https://docs.nginx.com/nginx-gateway-fabric/install/helm/)):

```bash
helm install ngf oci://ghcr.io/nginx/charts/nginx-gateway-fabric --create-namespace -n nginx-gateway
kubectl wait --timeout=5m -n nginx-gateway deployment/ngf-nginx-gateway-fabric --for=condition=Available
```

Verifica la classe:

```bash
kubectl get gatewayclass
```

In questo flusso **non** installare ingress-nginx. Il data plane NGINX viene creato nel namespace del `Gateway` (`corso-demo` quando applichi `k8s/09-gateway-api.yaml`).


## Import immagini nel cluster k3d

Se hai gia' un cluster (es. `corso-demo`), importa le immagini locali:

```bash
k3d image import catalog-service:latest -c corso-demo
k3d image import order-service:latest -c corso-demo
k3d image import frontend:latest -c corso-demo
```

```bash
k3d image import catalog-service:latest -c corso-demo-calico
k3d image import order-service:latest -c corso-demo-calico
k3d image import frontend:latest -c corso-demo-calico
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

Assicurati di aver installato le CRD Gateway API se includi `k8s/09-gateway-api.yaml` (vedi sopra). Il file `k8s/07-ingress.yaml` e `k8s/09-gateway-api.yaml` non vanno usati contemporaneamente come unici ingressi HTTP: installa solo il controller scelto (Ingress NGINX **o** NGINX Gateway Fabric).

### NetworkPolicy

Il file `k8s/08-networkpolicies.yaml` limita il traffico nel namespace `corso-demo`:

- Il traffico HTTP verso frontend e API passa dai pod del controller **ingress-nginx** (namespace `ingress-nginx`) oppure dai pod del data plane **NGINX Gateway Fabric** (`app.kubernetes.io/name: nginx-gateway-fabric` nello stesso namespace della demo).
- **catalog-service** puo' raggiungere solo **postgres** sulla porta 5432; **order-service** solo **mongo** sulla porta 27017.
- I database accettano connessioni solo dai rispettivi microservizi.

Richiede un CNI che applichi le NetworkPolicy (il cluster **k3d** con K3s le supporta). Un controller di ingresso (Ingress o Gateway) deve essere gia' disponibile prima di testare le API.

Per NetworkPolicy avanzate con k3d e **Calico**, vedi la [documentazione k3d + Calico](https://k3d.io/v5.8.3/usage/advanced/calico/#1-create-the-cluster-without-flannel) e il file `k3d/cluster-demo-calico.yaml`.

Verifica (dopo il deploy):

```bash
kubectl get networkpolicy -n corso-demo
```

### Gateway API (verifica)

```bash
kubectl get gateway,httproute -n corso-demo
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

1. Apri il frontend nel browser:

- aggiungi una entry in `/etc/hosts`:

```bash
echo "127.0.0.1 corso-k8s.local" | sudo tee -a /etc/hosts
```

- URL: [http://corso-k8s.local](http://corso-k8s.local)

Esito atteso:

- caricamento pagina con titolo "Corso Kubernetes 2026"
- i pulsanti di test API (`Carica Catalogo` e `Carica Ordini`) sono visibili

