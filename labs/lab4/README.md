## Lab: LAB4

Laboratorio piu avanzato di lab1/lab2/lab3, con argomenti tipici da esame CKA. **Ogni manifest contiene piu di un bug da risolvere**: e necessario combinare correttamente i diversi oggetti (Namespace, NetworkPolicy, RBAC, scheduling, securityContext) per portare i workload in stato sano.

Argomenti coperti:

- `NetworkPolicy` cross-namespace con default-deny, `namespaceSelector`/`podSelector` combinati, riferimenti a `containerPort` per nome
- RBAC namespaced: `ServiceAccount` + `Role` + `RoleBinding` per chiamate alla Kubernetes API dall'interno del cluster
- Scheduling: `nodeSelector`, `nodeAffinity`, `topologySpreadConstraints` con vincoli incompatibili
- Pod security: `securityContext` (runAsUser, runAsNonRoot, fsGroup), `readOnlyRootFilesystem` e PVC

### Prerequisito k3d

Un cluster con CNI che supporti `NetworkPolicy`. K3d/k3s usa di default Flannel, che **non** applica le `NetworkPolicy`: per questo lab usa la flag `--k3s-arg="--flannel-backend=none@server:*"` insieme a un CNI come Calico, oppure abilita `network-policy` su k3s. Esempio rapido con k3d e Calico:

```bash
k3d cluster create lab4 \
  --agents 2 \
  --k3s-arg "--flannel-backend=none@server:*" \
  --k3s-arg "--disable-network-policy=false@server:*" \
  --k3s-arg "--cluster-cidr=10.42.0.0/16@server:*"

kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.3/manifests/calico.yaml
kubectl rollout status -n kube-system ds/calico-node --timeout=180s
```

In alternativa, se vuoi solo provare i pezzi non basati su `NetworkPolicy` (RBAC, scheduling, podSecurity), va bene anche un cluster k3d standard:

```bash
k3d cluster create lab4 --agents 2
```

In quel caso le `NetworkPolicy` non saranno applicate dal CNI, e la verifica del punto 1 non sara significativa: tienilo a mente.

Verifica iniziale:

```bash
kubectl cluster-info
kubectl get nodes -o wide --show-labels
kubectl get storageclass
```

Nota: il lab assume la presenza della StorageClass `local-path` (default su k3d/k3s).

### Obiettivo

- Diagnosticare workload rotti combinando `kubectl describe`, `kubectl logs`, `kubectl get events`, `kubectl auth can-i`, ispezione dei `containerPort`, dei label dei `Namespace` e dei `Node`
- Riconoscere bug *combinati*: una singola correzione non basta, occorre riallineare piu oggetti tra loro
- Correggere i manifest per portare tutti i workload in uno stato sano

### Applica il lab rotto

```bash
kubectl apply -f labs/lab4
```

### Sintomo iniziale atteso

```bash
kubectl get ns -l purpose
kubectl get all -n lab4
kubectl get all -n lab4-client
kubectl get networkpolicy -n lab4
kubectl get pods -n lab4 -o wide
```

Ci si aspetta:

- Pod `client` in `lab4-client` con log `FAIL` continui: il traffico verso `api.lab4` viene bloccato dalle `NetworkPolicy`
- Pod `rbac-tester` in `lab4` con log `Error from server (Forbidden): services is forbidden ...`: il `ServiceAccount` non ha i permessi giusti
- Deployment `critical-app` in `lab4` con tutti i Pod in `Pending` ed evento `0/X nodes are available: ... node(s) didn't match Pod's node affinity/selector`
- Pod `secure-app` in `lab4` in `CrashLoopBackOff`: il container principale fallisce perche non riesce a scrivere `/var/log/app.log` (root filesystem read-only senza volume), e/o l'init non riesce a scrivere sulla PVC perche il fsGroup non e impostato

### Attivita

#### 1. NetworkPolicy cross-namespace (almeno 3 problemi)

- Il Pod `client` vive nel `Namespace` `lab4-client` ma la `NetworkPolicy` `allow-client` accetta solo da Pod nello stesso namespace tramite il `podSelector`
- L'`ingress` referenzia il `port: http` ma il `containerPort` del Deployment `api` non ha un nome
- Il `namespaceSelector` cerca un label `role: trusted` che non esiste sul `Namespace` `lab4-client`

Correggi i manifest e/o i label dei `Namespace` finche `client` riesce a chiamare `api`.

#### 2. RBAC per chiamata API dal Pod (3 problemi)

- Il `Role` espone le risorse sbagliate (`pods` invece di `services`) e i `verbs` sbagliati (manca `list`)
- Il `RoleBinding` punta al `ServiceAccount` nel namespace sbagliato (`default` invece di `lab4`)

Correggi `Role` e `RoleBinding` finche il Pod `rbac-tester` riesce a fare `kubectl get services -n lab4`.

#### 3. Scheduling con vincoli incompatibili (3 problemi)

- `nodeSelector` con un label che nessun nodo possiede (`topology.kubernetes.io/zone: eu-west-1a`)
- `nodeAffinity` `required` con `kubernetes.io/os In [windows]`, ma i nodi k3d sono Linux
- `topologySpreadConstraints` con `maxSkew: 0` (valore non valido)

Ispeziona le label reali dei nodi (`kubectl get nodes --show-labels`) e correggi i vincoli affinche il Deployment riesca a schedulare i 3 replica.

#### 4. Pod security + storage (2-3 problemi)

- Il Pod gira come uid `1000`/gid `3000` ma manca `fsGroup`: l'init container scrive sul PVC come `root` ma il container principale (non root) non riesce piu a leggere/scrivere
- Il container principale ha `readOnlyRootFilesystem: true` ma scrive in `/var/log/app.log`: quel path appartiene al root filesystem in sola lettura
- Manca un volume scrivibile montato su `/var/log`

Correggi `securityContext` e i `volumes` finche `secure-app` resta `Running` e il file di log viene scritto.

### Comandi utili

```bash
# 1. NetworkPolicy
kubectl get pods -n lab4-client -l app=client
kubectl logs -n lab4-client -l app=client --tail=20
kubectl get networkpolicy -n lab4 -o yaml
kubectl get ns lab4-client --show-labels
kubectl get pod -n lab4 -l app=api -o jsonpath='{.items[0].spec.containers[0].ports}'

# 2. RBAC
kubectl logs -n lab4 rbac-tester --tail=20
kubectl auth can-i list services -n lab4 \
  --as=system:serviceaccount:lab4:api-reader
kubectl describe role list-services -n lab4
kubectl describe rolebinding list-services-binding -n lab4

# 3. Scheduling
kubectl get pods -n lab4 -l app=critical-app
kubectl describe pod -n lab4 -l app=critical-app | sed -n '/Events/,$p'
kubectl get nodes --show-labels
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.labels.kubernetes\.io/os}{"\n"}{end}'

# 4. Pod security
kubectl get pod secure-app -n lab4
kubectl describe pod secure-app -n lab4
kubectl logs secure-app -n lab4 -c seed-data
kubectl logs secure-app -n lab4 -c app
kubectl get pvc secure-data -n lab4
```

### Verifica finale

Tutti i workload sani:

```bash
kubectl get pods,deploy -n lab4
kubectl get pods,deploy -n lab4-client
```

1. **NetworkPolicy**: il Pod `client` mostra la risposta `cka-api-ok`:

   ```bash
   kubectl logs -n lab4-client -l app=client --tail=10
   ```

2. **RBAC**: `kubectl auth can-i` ritorna `yes` e il pod `rbac-tester` elenca i Service:

   ```bash
   kubectl auth can-i list services -n lab4 \
     --as=system:serviceaccount:lab4:api-reader
   kubectl logs rbac-tester -n lab4 --tail=20
   ```

3. **Scheduling**: il Deployment `critical-app` ha 3/3 Pod `Running`:

   ```bash
   kubectl get deploy critical-app -n lab4
   kubectl get pods -n lab4 -l app=critical-app -o wide
   ```

4. **Pod security**: `secure-app` `Running`, log scritti e seed leggibile:

   ```bash
   kubectl get pod secure-app -n lab4
   kubectl exec -n lab4 secure-app -- cat /var/log/app.log | tail -n 5
   kubectl exec -n lab4 secure-app -- cat /data/seed.txt
   ```

### Soluzione

I manifest corretti sono in:

```bash
labs/lab4/solution
```

Per applicare direttamente le soluzioni:

```bash
kubectl delete -f labs/lab4
kubectl apply -f labs/lab4/solution
```

### Cleanup

```bash
kubectl delete -f labs/lab4
```

Per rimuovere anche il cluster k3d dedicato:

```bash
k3d cluster delete lab4
```
