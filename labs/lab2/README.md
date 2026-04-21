## Lab: LAB2

Questo laboratorio simula quattro problemi tipici da esame CKAD su argomenti diversi rispetto a lab1:

- Resources requests/limits e scheduling
- Jobs con volumi da ConfigMap
- Pod multi-container (pattern sidecar) con volume condiviso
- PersistentVolumeClaim e StorageClass

### Prerequisito k3d

Un cluster con almeno un worker e sufficiente per il lab. Per esempio:

```bash
k3d cluster create lab2 --agents 1
```

Se hai gia un cluster, verifica che sia raggiungibile:

```bash
kubectl cluster-info
kubectl get nodes
kubectl get storageclass
```

Nota: il lab assume la presenza della StorageClass `local-path` (default su k3d/k3s).

### Obiettivo

- Diagnosticare workload rotti usando `kubectl describe`, `kubectl logs`, `kubectl get events`
- Riconoscere sintomi tipici: `Pending` per insufficient resources, `Job` in fallimento con `BackoffLimitExceeded`, sidecar che non vede i log, `PVC` in `Pending` per StorageClass inesistente
- Correggere i manifest per portare tutti i workload in uno stato sano

### Applica il lab rotto

```bash
kubectl apply -f labs/lab2
```

### Sintomo iniziale atteso

```bash
kubectl get all -n lab2
kubectl get pods -n lab2
kubectl get pvc -n lab2
kubectl get jobs -n lab2
```

Ci si aspetta:

- `web-resources` con Pod in `Pending` e evento `FailedScheduling` per CPU/memoria insufficienti
- `batch-job` con Pod in stato `Error` / `CrashLoopBackOff` e Job con `BackoffLimitExceeded`
- `web-sidecar` con entrambi i container `Running` ma il container `log-reader` fermo in attesa del file (nessun log in output)
- `data-pvc` in stato `Pending` e Pod `web-pvc` in `Pending` per PVC non legato

### Attivita

1. Identifica perche il Pod di `web-resources` non viene schedulato (confronta `requests` con le risorse dei nodi)
2. Identifica perche il `Job` `batch-job` fallisce (il comando fa riferimento a un file inesistente)
3. Identifica perche il sidecar `log-reader` non vede i log prodotti dal container `app`
4. Identifica perche il `PersistentVolumeClaim` `data-pvc` resta in `Pending`
5. Correggi i manifest rotti
6. Verifica che tutti i workload siano sani

### Comandi utili

```bash
kubectl get pods -n lab2 -o wide
kubectl describe pod -n lab2 -l app=web-resources
kubectl get events -n lab2 --sort-by=.lastTimestamp

kubectl get jobs -n lab2
kubectl describe job batch-job -n lab2
kubectl logs -n lab2 -l app=batch-job --tail=50

kubectl describe pod web-sidecar -n lab2
kubectl logs web-sidecar -n lab2 -c app --tail=5
kubectl logs web-sidecar -n lab2 -c log-reader --tail=5

kubectl get pvc,pv -n lab2
kubectl describe pvc data-pvc -n lab2
kubectl get storageclass
```

### Verifica finale

Pod e risorse tutti in stato sano:

```bash
kubectl get pods,pvc,jobs -n lab2
```

Il Pod `web-resources` in `Running`:

```bash
kubectl get pod -n lab2 -l app=web-resources
```

Il Job `batch-job` in stato `Complete` e log che mostrano l'input letto:

```bash
kubectl get job batch-job -n lab2
kubectl logs -n lab2 -l app=batch-job
```

Il sidecar `log-reader` che stampa gli eventi prodotti dal container `app`:

```bash
kubectl logs web-sidecar -n lab2 -c log-reader --tail=5
```

Il `PVC` in stato `Bound` e file scritto dal Pod:

```bash
kubectl get pvc data-pvc -n lab2
kubectl exec -n lab2 web-pvc -- cat /data/hello.txt
```

### Soluzione

I manifest corretti sono in:

```bash
labs/lab2/solution
```

Per applicare direttamente le soluzioni:

```bash
kubectl delete -f labs/lab2
kubectl apply -f labs/lab2/solution
```

### Cleanup

```bash
kubectl delete -f labs/lab2
```

Per rimuovere anche il cluster k3d dedicato:

```bash
k3d cluster delete lab2
```
