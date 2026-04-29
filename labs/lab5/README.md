## Lab: LAB5

Questo laboratorio e diverso dai precedenti: non parte da manifest rotti da correggere, ma richiede di **creare risorse Kubernetes da zero** usando il workflow della `cheatsheet.md`: `kubectl create/run/expose --dry-run=client -o yaml`, modifica mirata dei manifest, `kubectl apply`, verifica con `get`, `describe`, `logs`, DNS e JSONPath.

Argomenti coperti:

- Generazione di manifest per `ConfigMap`, `Secret`, `Deployment` e `Service`
- Uso di `envFrom`, `secretKeyRef` e volume da `ConfigMap`
- Test DNS e Service discovery con Pod temporanei
- Creazione di `Job`, `CronJob` e Job manuale da CronJob
- Uso di JSONPath per estrarre valori utili dalle risorse create

### Prerequisito k3d

Un cluster standard e sufficiente:

```bash
k3d cluster create lab5 --agents 1
```

Se hai gia un cluster, verifica che sia raggiungibile:

```bash
kubectl cluster-info
kubectl get nodes
```

### Setup iniziale

Applica solo il namespace del lab:

```bash
kubectl apply -f labs/lab5/00-namespace.yaml
kubectl config set-context --current --namespace lab5
```

### Obiettivo

Crea i manifest richiesti sotto `labs/lab5/` usando comandi imperativi con `--dry-run=client -o yaml`, poi modificali solo dove serve. Alla fine dovrai avere:

- una piccola app web `portal` configurata con `ConfigMap` e `Secret`
- un `Service` `portal` raggiungibile via DNS interno
- un `Job` `report-once` completato con successo
- un `CronJob` `report-schedule` valido, da cui creare un Job manuale
- un Pod `toolbox` per test interni e comandi di debug

### Attivita

#### 1. ConfigMap e Secret per l'app

Crea questi oggetti nel namespace `lab5`:

- `ConfigMap` `portal-env` con `APP_MODE=training` e `LOG_LEVEL=debug`
- `ConfigMap` `portal-page` partendo da un file locale `index.html` con contenuto a scelta
- `Secret` generic `portal-secret` con la chiave `API_TOKEN=lab5-token`

Comandi di partenza:

```bash
kubectl create configmap portal-env \
  --from-literal=APP_MODE=training \
  --from-literal=LOG_LEVEL=debug \
  --dry-run=client -o yaml > labs/lab5/10-config.yaml

kubectl create secret generic portal-secret \
  --from-literal=API_TOKEN=lab5-token \
  --dry-run=client -o yaml > labs/lab5/11-secret.yaml
```

Per `portal-page`, crea prima un file temporaneo `index.html`, poi genera il manifest con `--from-file`.

#### 2. Deployment `portal`

Crea un `Deployment` `portal` con immagine `nginx:1.27` e 2 repliche.

Modifica il manifest generato per aggiungere:

- label coerenti `app: portal`
- `envFrom` da `portal-env`
- variabile `API_TOKEN` letta dal `Secret` `portal-secret`
- volume da `ConfigMap` `portal-page`
- mount del file `index.html` in `/usr/share/nginx/html/index.html` con `subPath`

Comando di partenza:

```bash
kubectl create deployment portal \
  --image=nginx:1.27 \
  --replicas=2 \
  --dry-run=client -o yaml > labs/lab5/20-portal-deploy.yaml
```

#### 3. Service e verifica DNS

Crea un `Service` `ClusterIP` chiamato `portal` che esponga il Deployment sulla porta 80.

```bash
kubectl expose deployment portal \
  --port=80 \
  --target-port=80 \
  --type=ClusterIP \
  --dry-run=client -o yaml > labs/lab5/30-portal-service.yaml
```

Crea poi un Pod `toolbox` con `busybox` per i test:

```bash
kubectl run toolbox \
  --image=busybox:1.36 \
  --restart=Never \
  --command -- sleep 3600 \
  --dry-run=client -o yaml > labs/lab5/40-toolbox.yaml
```

#### 4. Job `report-once`

Crea una `ConfigMap` `report-script` con uno script shell che stampi almeno:

- data corrente
- nome del namespace
- valore di `APP_MODE`

Poi crea un `Job` `report-once` che monti lo script e lo esegua. Il Job deve terminare in `Complete`.

Comando di partenza:

```bash
kubectl create job report-once \
  --image=busybox:1.36 \
  --dry-run=client -o yaml > labs/lab5/50-report-job.yaml
```

#### 5. CronJob e Job manuale

Crea un `CronJob` `report-schedule` che usi lo stesso script ogni 10 minuti.

```bash
kubectl create cronjob report-schedule \
  --image=busybox:1.36 \
  --schedule='*/10 * * * *' \
  --dry-run=client -o yaml > labs/lab5/60-report-cronjob.yaml
```

Dopo aver applicato il CronJob, crea un Job manuale:

```bash
kubectl create job report-manual --from=cronjob/report-schedule
```

### Comandi utili

```bash
kubectl apply -f labs/lab5
kubectl get all
kubectl get configmap,secret
kubectl get pods -o wide --show-labels
kubectl describe deploy portal
kubectl logs -l app=portal --tail=20

kubectl exec toolbox -- nslookup portal.lab5.svc.cluster.local
kubectl exec toolbox -- wget -qO- http://portal

kubectl get jobs,cronjobs
kubectl logs job/report-once
kubectl logs job/report-manual

kubectl get svc portal -o jsonpath='{.spec.clusterIP}{"\n"}'
kubectl get secret portal-secret -o jsonpath='{.data.API_TOKEN}' | base64 -d; echo
```

### Verifica finale

Tutte le risorse principali devono essere presenti:

```bash
kubectl get deploy,svc,pods,job,cronjob -n lab5
```

Il Deployment deve avere 2 repliche pronte:

```bash
kubectl rollout status deploy/portal -n lab5
kubectl get deploy portal -n lab5
```

Il Service deve rispondere dal Pod `toolbox`:

```bash
kubectl exec -n lab5 toolbox -- nslookup portal.lab5.svc.cluster.local
kubectl exec -n lab5 toolbox -- wget -qO- http://portal
```

Il Job e il Job manuale devono completare:

```bash
kubectl get jobs -n lab5
kubectl logs -n lab5 job/report-once
kubectl logs -n lab5 job/report-manual
```

### Soluzione

I manifest di riferimento sono in:

```bash
labs/lab5/solution
```

Per applicare direttamente le soluzioni:

```bash
kubectl apply -f labs/lab5/00-namespace.yaml
kubectl apply -f labs/lab5/solution
kubectl create job report-manual --from=cronjob/report-schedule -n lab5
```

### Cleanup

```bash
kubectl delete namespace lab5
```

Per rimuovere anche il cluster k3d dedicato:

```bash
k3d cluster delete lab5
```
