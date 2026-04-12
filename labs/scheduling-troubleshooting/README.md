## Lab: Troubleshooting scheduling

Questo laboratorio simula tre problemi classici da CKA legati al scheduling dei Pod:

- `nodeSelector` errato
- `nodeAffinity` non soddisfatta
- `taints` e `tolerations` non allineati

### Prerequisito k3d

Usa un cluster con almeno due worker schedulabili. Per esempio:

```bash
k3d cluster create cka-scheduling --agents 2
```

Se il cluster esiste gia, verifica di avere almeno due worker:

```bash
kubectl get nodes
```

### Preparazione dei nodi per il lab

Seleziona un worker per `nodeSelector` e `nodeAffinity`, e un worker dedicato per `taints/tolerations`:

```bash
export SCHED_NODE=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o jsonpath='{.items[0].metadata.name}')
export TAINT_NODE=$(kubectl get nodes -l '!node-role.kubernetes.io/control-plane' -o jsonpath='{.items[1].metadata.name}')
echo "$SCHED_NODE"
echo "$TAINT_NODE"
kubectl label node "$SCHED_NODE" disk=ssd nodepool=blue --overwrite
kubectl label node "$TAINT_NODE" lab=dedicated --overwrite
kubectl taint node "$TAINT_NODE" workload=exercise:NoSchedule --overwrite
```

Verifica:

```bash
kubectl get nodes --show-labels
kubectl describe node "$SCHED_NODE"
kubectl describe node "$TAINT_NODE"
```

### Applica il lab rotto

```bash
kubectl apply -f labs/scheduling-troubleshooting
```

### Sintomo iniziale atteso

Tutti e tre i Pod restano in `Pending`.

```bash
kubectl get pods -n scheduling-lab -o wide
```

### Attivita

1. Identifica perche `web-node-selector` non viene schedulato
2. Identifica perche `web-node-affinity` non trova un nodo valido
3. Identifica perche `web-taints` non tollera il nodo corretto
4. Correggi i manifest
5. Verifica che tutti i Pod vadano in `Running`

### Comandi utili

```bash
kubectl get pods -n scheduling-lab
kubectl describe pod web-node-selector -n scheduling-lab
kubectl describe pod web-node-affinity -n scheduling-lab
kubectl describe pod web-taints -n scheduling-lab
kubectl get nodes --show-labels
kubectl describe node "$SCHED_NODE"
kubectl describe node "$TAINT_NODE"
```

### Verifica finale

```bash
kubectl get pods -n scheduling-lab -o wide
```

### Soluzione

I manifest corretti sono in:

```bash
labs/scheduling-troubleshooting/solution
```

### Cleanup

```bash
kubectl delete -f labs/scheduling-troubleshooting
kubectl taint node "$TAINT_NODE" workload=exercise:NoSchedule-
kubectl label node "$SCHED_NODE" disk- nodepool-
kubectl label node "$TAINT_NODE" lab-
```
