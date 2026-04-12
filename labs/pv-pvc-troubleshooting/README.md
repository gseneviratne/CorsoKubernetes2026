## Lab: Troubleshooting PV e PVC

Questo laboratorio simula un problema tipico da esame CKA: un `Pod` resta in `Pending` perche il `PersistentVolumeClaim` non riesce a fare il bind con il `PersistentVolume` disponibile.

### Obiettivo

- Identificare perche il `PVC` resta in `Pending`
- Capire quali campi devono combaciare tra `PV` e `PVC`
- Sistemare il manifest per portare il `Pod` in `Running`

### Applica il lab rotto

```bash
kubectl apply -f labs/pv-pvc-troubleshooting
```

### Sintomo iniziale atteso

```bash
kubectl get pv,pvc,pod -n pv-lab
```

Il `Pod` risulta `Pending` e il `PVC` non va in `Bound`.

### Attivita

1. Ispeziona `PersistentVolume` e `PersistentVolumeClaim`
2. Individua perche il bind non avviene
3. Correggi il manifest rotto
4. Verifica che il `Pod` parta correttamente

### Comandi utili

```bash
kubectl get pv
kubectl get pvc -n pv-lab
kubectl describe pvc pvc-lab-data -n pv-lab
kubectl describe pv pv-lab-data
kubectl get pod -n pv-lab
kubectl describe pod app -n pv-lab
```

### Verifica finale

```bash
kubectl get pv,pvc,pod -n pv-lab
kubectl exec -n pv-lab app -- sh -lc 'echo ok > /data/check.txt && ls -l /data && cat /data/check.txt'
```

### Soluzione

I manifest corretti sono in:

```bash
labs/pv-pvc-troubleshooting/solution
```

### Cleanup

```bash
kubectl delete -f labs/pv-pvc-troubleshooting
```
