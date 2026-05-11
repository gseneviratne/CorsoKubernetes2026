## Lab: LAB6

Laboratorio di troubleshooting di livello CKA su argomenti tipici di **produzione**, con difficolta superiore a lab1/lab2/lab3 e in linea con lab4. **Ogni manifest contiene piu di un bug da risolvere**: e necessario combinare correttamente i diversi oggetti per portare i workload in stato sano.

Argomenti coperti:

- `HorizontalPodAutoscaler` (autoscaling/v2), `resources.requests`, `metrics-server`
- `Ingress` con Traefik (default in k3d/k3s), `Service` e routing per nome porta
- `PodDisruptionBudget` + strategia di rollout per garantire alta disponibilita durante un drain
- `Pod Security Admission` (label `pod-security.kubernetes.io/enforce`) e `securityContext` per il profilo `restricted`

### Prerequisito k3d

Un cluster con almeno un worker e sufficiente. Su k3d/k3s sono gia presenti `metrics-server` e `Traefik`, indispensabili per due dei quattro punti.

```bash
k3d cluster create lab6 --agents 1
```

Verifica iniziale:

```bash
kubectl cluster-info
kubectl get nodes -o wide
kubectl get deploy -n kube-system metrics-server
kubectl get svc -n kube-system traefik
kubectl top nodes
```

Se `kubectl top nodes` non risponde subito, attendi qualche secondo: `metrics-server` ha bisogno di tempo per popolare le metriche.

### Obiettivo

- Diagnosticare workload rotti combinando `kubectl describe`, `kubectl get events`, `kubectl top pod`, `kubectl rollout`, `kubectl get hpa`, `kubectl get pdb`
- Riconoscere bug *combinati*: una singola correzione non basta, occorre riallineare piu oggetti tra loro
- Correggere i manifest per portare tutti i workload in uno stato sano

### Applica il lab rotto

```bash
kubectl apply -f labs/lab6
```

Nota: l'apply del Deployment `hardened` in `lab6-secure` puo gia fallire al server-side per violazione di `Pod Security Admission` con profilo `restricted`. E un sintomo voluto: l'errore stesso fa parte del lab.

### Sintomo iniziale atteso

```bash
kubectl get all -n lab6
kubectl get hpa -n lab6
kubectl get pdb -n lab6
kubectl get ingress -n lab6
kubectl get all -n lab6-secure
kubectl get events -n lab6-secure --sort-by=.lastTimestamp
```

Ci si aspetta:

- `web-hpa`: HPA con `TARGETS = <unknown>/50%`, `REFERENCE` non valido o evento `FailedGetScale` perche il `scaleTargetRef.name` non esiste
- `shop`: Ingress non risponde, l'`Endpoints` del Service e vuoto e/o il `backend.service.name` punta a un Service inesistente
- `payments`: PDB con `ALLOWED DISRUPTIONS = 0` e `STATUS` che mostra zero pod selezionati; un `kubectl drain` (simulato con `kubectl rollout restart`) viola il budget
- `hardened`: il `ReplicaSet` non riesce a creare i Pod, evento `forbidden: violates PodSecurity "restricted:latest"` con elenco dei controlli falliti

### Attivita

#### 1. HPA + resources + autoscaling/v2 (almeno 3 problemi)

- Il container del Deployment `web-hpa` non dichiara `resources.requests.cpu`: HPA non puo calcolare la `% utilization`
- L'`HorizontalPodAutoscaler` punta a un Deployment di nome `web` che non esiste (il Deployment si chiama `web-hpa`)
- I limiti dell'HPA sono invertiti: `minReplicas: 5`, `maxReplicas: 2`
- L'`apiVersion: autoscaling/v1` non supporta i metric type avanzati: porta l'HPA su `autoscaling/v2` con metrica `Resource` su `cpu`

Correggi i manifest finche `kubectl get hpa -n lab6` mostra `TARGETS` con un valore numerico (es. `0%/50%`) e il deployment scalato in modo coerente.

#### 2. Ingress + Service + named port (3 problemi)

- Il `Service` `shop` ha `clusterIP: None` (headless): Traefik non puo bilanciare verso un Service headless
- Il `Service` espone `port: 80` con `targetPort: 80`, ma il container ascolta sulla porta `8080` (named `http`): bisogna allineare `targetPort` al nome della porta
- L'`Ingress` punta a `service.name: shop-svc` con `port.number: 8080`, ma il Service si chiama `shop` ed espone la `port: 80`; inoltre `pathType: Exact` non e adatto a un test con `curl /`

Correggi `Service` e `Ingress` finche l'Ingress risponde con il testo `cka-shop-ok`.

#### 3. PodDisruptionBudget + strategy (3 problemi)

- Il `PodDisruptionBudget` `payments-pdb` seleziona `app: payments-api`, ma i Pod del Deployment hanno label `app: payments`: il PDB non protegge alcun Pod
- `minAvailable: 3` e maggiore del numero di repliche del Deployment (`replicas: 2`): il PDB blocca qualsiasi disruption volontaria
- Il `Deployment` ha `strategy.type: Recreate`: durante un rollout tutti i Pod vengono eliminati contemporaneamente, violando il PDB; serve `RollingUpdate` con `maxUnavailable: 0`

Correggi i manifest e simula un rollout con `kubectl rollout restart deploy/payments -n lab6`: il rollout deve riuscire senza scendere sotto il `minAvailable`.

#### 4. Pod Security Admission + securityContext (4 problemi)

Il `Namespace` `lab6-secure` ha l'enforcement `pod-security.kubernetes.io/enforce: restricted`. Il Deployment `hardened` viola contemporaneamente diversi controlli del profilo `restricted`:

- `runAsUser: 0` (root) e nessun `runAsNonRoot: true`
- `allowPrivilegeEscalation: true` (deve essere `false`)
- `capabilities.add: ["NET_ADMIN"]` (deve essere `drop: ["ALL"]`)
- Manca `seccompProfile.type: RuntimeDefault` sul Pod o sul container

Correggi il `securityContext` finche il Deployment crea i Pod e gli eventi non riportano piu violazioni di PSA.

### Comandi utili

```bash
# 1. HPA
kubectl get hpa web-hpa -n lab6
kubectl describe hpa web-hpa -n lab6
kubectl get deploy web-hpa -n lab6
kubectl top pod -n lab6
kubectl get events -n lab6 --sort-by=.lastTimestamp

# 2. Ingress
kubectl get svc,endpoints shop -n lab6
kubectl get ingress shop -n lab6 -o yaml
kubectl describe ingress shop -n lab6
kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.8.0 -n lab6 -- \
  curl -sS -H "Host: shop.lab6.local" http://traefik.kube-system.svc.cluster.local/

# 3. PDB
kubectl get pdb payments-pdb -n lab6
kubectl describe pdb payments-pdb -n lab6
kubectl get pods -n lab6 -l app=payments --show-labels
kubectl rollout restart deploy/payments -n lab6
kubectl rollout status deploy/payments -n lab6

# 4. Pod Security Admission
kubectl get ns lab6-secure --show-labels
kubectl get rs -n lab6-secure -l app=hardened
kubectl get events -n lab6-secure --sort-by=.lastTimestamp | grep -i forbidden
kubectl get pod -n lab6-secure -l app=hardened
```

### Verifica finale

Tutti i workload sani:

```bash
kubectl get pods,deploy,svc,ingress,hpa,pdb -n lab6
kubectl get pods,deploy -n lab6-secure
```

1. **HPA**: `TARGETS` con valori numerici e bound al deployment corretto:

   ```bash
   kubectl get hpa web-hpa -n lab6
   kubectl describe hpa web-hpa -n lab6 | sed -n '/Conditions/,$p'
   ```

2. **Ingress**: il Service ha endpoint popolati e l'Ingress risponde:

   ```bash
   kubectl get endpoints shop -n lab6
   kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.8.0 -n lab6 -- \
     curl -sS -H "Host: shop.lab6.local" http://traefik.kube-system.svc.cluster.local/
   ```

3. **PDB**: il PDB protegge i Pod e un rollout completa senza violazioni:

   ```bash
   kubectl get pdb payments-pdb -n lab6
   kubectl rollout restart deploy/payments -n lab6
   kubectl rollout status deploy/payments -n lab6
   ```

4. **PSA**: il Pod `hardened` `Running` nel namespace `restricted`:

   ```bash
   kubectl get pod -n lab6-secure -l app=hardened
   kubectl exec -n lab6-secure deploy/hardened -- id
   ```

### Soluzione

I manifest corretti sono in:

```bash
labs/lab6/solution
```

Per applicare direttamente le soluzioni:

```bash
kubectl delete -f labs/lab6 --ignore-not-found
kubectl apply -f labs/lab6/solution
```

### Cleanup

```bash
kubectl delete -f labs/lab6 --ignore-not-found
kubectl delete namespace lab6 lab6-secure --ignore-not-found
```

Per rimuovere anche il cluster k3d dedicato:

```bash
k3d cluster delete lab6
```
