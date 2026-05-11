## Lab: LAB7

Laboratorio **capstone**: come lab5, parte da zero e richiede di **creare risorse Kubernetes** invece di correggere manifest rotti, ma su scala maggiore. L'obiettivo e mettere in piedi una mini applicazione multi-tier `shop-lite`, combinando in un unico namespace gli argomenti dei lab precedenti (lab1-lab6).

Architettura da realizzare nel namespace `lab7`:

```
                       Ingress (Traefik)
                           |
                +----------+----------+
                |                     |
            Service web           Service api
            (ClusterIP)           (ClusterIP)
                |                     |
        Deployment web          Deployment api  ----> StatefulSet cache
        (nginx + ConfigMap)     (http-echo +    headless Service +
        + HPA + PDB              env da CM/Secret) PVC dinamica
                                       
                          ServiceAccount + Role + RoleBinding
                          Pod inspector (kubectl get pods/svc)
```

Argomenti coperti (cumulativo dei lab precedenti):

- ConfigMap, Secret, `envFrom`, `secretKeyRef`, volume da ConfigMap (lab5)
- StatefulSet con `serviceName` headless e `volumeClaimTemplates` (lab2/lab3)
- Deployment con probe, `resources` e strategia di rollout (lab1/lab6)
- Ingress con Traefik + routing su path multipli (lab6)
- HPA `autoscaling/v2` su CPU (lab6)
- PodDisruptionBudget e rolling update senza downtime (lab6)
- ServiceAccount + RBAC namespaced per chiamate alla Kubernetes API (lab4)

### Prerequisito k3d

Cluster k3d standard, con Traefik e metrics-server gia inclusi:

```bash
k3d cluster create lab7 --agents 1
```

Verifica:

```bash
kubectl cluster-info
kubectl get nodes
kubectl get storageclass
kubectl get deploy -n kube-system metrics-server
kubectl get svc -n kube-system traefik
kubectl top nodes
```

Nota: il lab assume la presenza della StorageClass `local-path` (default su k3d/k3s).

### Setup iniziale

Applica solo il namespace e portati nel contesto:

```bash
kubectl apply -f labs/lab7/00-namespace.yaml
kubectl config set-context --current --namespace lab7
```

Il namespace `lab7` ha le label `pod-security.kubernetes.io/audit: baseline` e `warn: baseline`: i Pod che violano il profilo `baseline` non saranno bloccati ma genereranno un warning in `kubectl apply` e un evento di audit. Tienilo a mente.

### Obiettivo

Crea, sotto `labs/lab7/`, i manifest necessari per portare in `Running` tutta l'architettura sopra. Devi seguire l'ordine logico delle dipendenze (config -> cache -> api -> web -> hpa/pdb -> rbac).

Il flusso suggerito e quello della `cheatsheet.md`: parti da `kubectl create/run/expose --dry-run=client -o yaml`, poi modifica solo dove serve.

### Attivita

#### 1. ConfigMap, Secret e pagina HTML

Crea nel namespace `lab7`:

- `ConfigMap` `web-page` da un file locale `index.html` (puoi usare quello fornito con il lab)
- `ConfigMap` `api-config` con almeno: `APP_MODE=production`, `CACHE_HOST=cache-0.cache.lab7.svc.cluster.local`, `CACHE_PORT=6379`
- `Secret` generic `api-secret` con `API_TOKEN=lab7-supersecret`

Comandi di partenza:

```bash
kubectl create configmap web-page \
  --from-file=index.html=labs/lab7/index.html \
  -n lab7 --dry-run=client -o yaml > labs/lab7/10-config-secret.yaml

kubectl create configmap api-config \
  --from-literal=APP_MODE=production \
  --from-literal=CACHE_HOST=cache-0.cache.lab7.svc.cluster.local \
  --from-literal=CACHE_PORT=6379 \
  -n lab7 --dry-run=client -o yaml >> labs/lab7/10-config-secret.yaml

kubectl create secret generic api-secret \
  --from-literal=API_TOKEN=lab7-supersecret \
  -n lab7 --dry-run=client -o yaml >> labs/lab7/10-config-secret.yaml
```

#### 2. Cache: StatefulSet + headless Service + PVC dinamica

Crea un `Service` headless (`clusterIP: None`) `cache` che esponga la porta `6379` (porta `redis` per nome).

Crea uno `StatefulSet` `cache` con:

- `serviceName: cache` (per peer discovery DNS)
- 1 replica, label `app: cache`
- container `busybox:1.36` che esegua un loop scrivendo in `/data/start.log`
- `volumeClaimTemplates` con `storageClassName: local-path` e `100Mi`
- `resources.requests` minime ma presenti

L'obiettivo e che il pod si chiami `cache-0` e sia risolvibile come `cache-0.cache.lab7.svc.cluster.local`.

#### 3. Backend api: Deployment + Service

Crea un `Deployment` `api` (2 repliche) con:

- immagine `hashicorp/http-echo:1.0.0` che risponde `lab7-api-ok` sulla porta `8080`
- `containerPort` con `name: http`
- `envFrom` da `api-config` e variabile `API_TOKEN` da `api-secret`
- `readinessProbe` e `livenessProbe` HTTP sulla porta `http`
- `resources.requests` e `limits` impostati

Crea poi un `Service` `api` di tipo `ClusterIP` che esponga la porta `80` verso `targetPort: http`.

Comandi di partenza:

```bash
kubectl create deployment api \
  --image=hashicorp/http-echo:1.0.0 \
  --replicas=2 -n lab7 \
  --dry-run=client -o yaml > labs/lab7/30-api.yaml

kubectl expose deployment api --port=80 --target-port=8080 \
  -n lab7 --dry-run=client -o yaml >> labs/lab7/30-api.yaml
```

Dovrai modificare il manifest generato per impostare `args`, named port, envFrom, secretKeyRef, probe e resources.

#### 4. Frontend web: Deployment + Service + Ingress

Crea un `Deployment` `web` (2 repliche) con:

- immagine `nginx:1.27`
- `containerPort` `http: 80`
- volume da `ConfigMap` `web-page` montato su `/usr/share/nginx/html/index.html` con `subPath`
- probe HTTP, `resources.requests` e `limits`
- `strategy.rollingUpdate` con `maxUnavailable: 0` (necessario per il PDB del punto 5)

Crea un `Service` `ClusterIP` `web` sulla porta `80` -> `targetPort: http`.

Crea un `Ingress` `shop` (`ingressClassName: traefik`) con host `shop.lab7.local` e due path:

- `/api` -> Service `api`, port `80`
- `/` -> Service `web`, port `80`

#### 5. HPA + PDB sul frontend

Crea un `HorizontalPodAutoscaler` `web` (`autoscaling/v2`) che scali il `Deployment` `web` tra 2 e 5 repliche, soglia CPU 50%.

Crea un `PodDisruptionBudget` `web` con `minAvailable: 1` e selector `app: web`.

Verifica che il rollout del frontend rispetti il budget (`kubectl rollout restart deploy/web -n lab7`).

#### 6. RBAC e Pod inspector

Crea:

- `ServiceAccount` `inspector`
- `Role` `inspector` con permessi `get/list/watch` su `pods`, `services`, `endpoints` (apiGroup `""`) e su `deployments`, `statefulsets` (apiGroup `apps`)
- `RoleBinding` `inspector` che lega il SA al Role
- `Pod` `inspector` con `serviceAccountName: inspector` e immagine `bitnami/kubectl:1.30.2` che, in loop, esegua `kubectl get pods -n lab7` e `kubectl get svc -n lab7`

### Comandi utili

```bash
kubectl apply -f labs/lab7
kubectl get all -n lab7
kubectl get configmap,secret,sa,role,rolebinding,pdb,hpa,ingress -n lab7
kubectl get pods -n lab7 -o wide --show-labels

kubectl rollout status deploy/web -n lab7
kubectl rollout status deploy/api -n lab7
kubectl rollout status statefulset/cache -n lab7

# DNS e service discovery
kubectl run dnsutils --rm -it --restart=Never -n lab7 \
  --image=registry.k8s.io/e2e-test-images/jessie-dnsutils:1.7 -- \
  nslookup cache-0.cache.lab7.svc.cluster.local

# Test end-to-end via Ingress
kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.8.0 -n lab7 -- \
  curl -sS -H "Host: shop.lab7.local" http://traefik.kube-system.svc.cluster.local/
kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.8.0 -n lab7 -- \
  curl -sS -H "Host: shop.lab7.local" http://traefik.kube-system.svc.cluster.local/api/

# RBAC
kubectl logs -n lab7 inspector --tail=20
kubectl auth can-i list pods -n lab7 --as=system:serviceaccount:lab7:inspector
kubectl auth can-i delete pods -n lab7 --as=system:serviceaccount:lab7:inspector

# HPA + PDB
kubectl get hpa web -n lab7
kubectl describe hpa web -n lab7
kubectl get pdb web -n lab7
kubectl rollout restart deploy/web -n lab7
kubectl rollout status deploy/web -n lab7
```

### Verifica finale

Tutte le risorse devono essere presenti e sane:

```bash
kubectl get deploy,svc,ingress,statefulset,pdb,hpa,sa,role,rolebinding,pods -n lab7
```

1. **Cache**: pod `cache-0` `Running`, PVC `data-cache-0` `Bound`, DNS funzionante:

   ```bash
   kubectl get pod cache-0 -n lab7
   kubectl get pvc -n lab7
   kubectl run dnsutils --rm -it --restart=Never -n lab7 \
     --image=registry.k8s.io/e2e-test-images/jessie-dnsutils:1.7 -- \
     nslookup cache-0.cache.lab7.svc.cluster.local
   ```

2. **API**: 2/2 pod `Ready`, env iniettate da ConfigMap e Secret:

   ```bash
   kubectl get deploy api -n lab7
   kubectl exec -n lab7 deploy/api -- env | grep -E '^(APP_MODE|CACHE_|API_TOKEN)='
   ```

3. **Web + Ingress**: il frontend serve l'HTML del ConfigMap, l'Ingress instrada `/` e `/api`:

   ```bash
   kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.8.0 -n lab7 -- \
     curl -sS -H "Host: shop.lab7.local" http://traefik.kube-system.svc.cluster.local/
   kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.8.0 -n lab7 -- \
     curl -sS -H "Host: shop.lab7.local" http://traefik.kube-system.svc.cluster.local/api/
   ```

4. **HPA + PDB**: HPA con `TARGETS` numerici e rolling update senza scendere sotto `minAvailable`:

   ```bash
   kubectl get hpa web -n lab7
   kubectl rollout restart deploy/web -n lab7
   kubectl rollout status deploy/web -n lab7
   ```

5. **RBAC**: il pod `inspector` legge i pod e i Service del namespace:

   ```bash
   kubectl logs -n lab7 inspector --tail=20
   kubectl auth can-i list pods -n lab7 --as=system:serviceaccount:lab7:inspector
   kubectl auth can-i delete pods -n lab7 --as=system:serviceaccount:lab7:inspector
   ```

   Il primo `auth can-i` deve restituire `yes`, il secondo `no`.

### Soluzione

I manifest di riferimento sono in:

```bash
labs/lab7/solution
```

Per applicare direttamente le soluzioni:

```bash
kubectl apply -f labs/lab7/solution
```

### Cleanup

```bash
kubectl delete namespace lab7
```

Per rimuovere anche il cluster k3d dedicato:

```bash
k3d cluster delete lab7
```
