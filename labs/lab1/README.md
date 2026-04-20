## Lab: LAB1
Questo laboratorio simula quattro problemi tipici da esame CKAD su argomenti diversi

### Prerequisito k3d

Un cluster con almeno un worker e sufficiente per il lab. Per esempio:

```bash
k3d cluster create lab1 --agents 1
```

Se hai gia un cluster, verifica che sia raggiungibile:

```bash
kubectl cluster-info
kubectl get nodes
```

### Obiettivo

- Diagnosticare workload rotti usando `kubectl describe`, `kubectl logs`, `kubectl get events`
- Riconoscere sintomi tipici: `CrashLoopBackOff`, `CreateContainerConfigError`, `Init:0/1`, endpoints vuoti
- Correggere i manifest per portare tutti i workload in uno stato sano

### Applica il lab rotto

```bash
kubectl apply -f labs/ckad-troubleshooting
```

### Sintomo iniziale atteso

```bash
kubectl get all -n lab1
kubectl get pods -n lab1
```

Ci si aspetta:

- `web-probes` in `CrashLoopBackOff` o `Running` con `0/1 READY` e restart in aumento
- `web-config` in `CreateContainerConfigError`
- `web-service` con Pod `Running` ma `Service` senza endpoint raggiungibile
- `web-init` bloccato in `Init:0/1`

### Attivita

1. Identifica perche i Pod di `web-probes` continuano a riavviarsi
2. Identifica quali chiavi mancano o sono sbagliate in `web-config`
3. Identifica perche il `Service` `web-service` non risponde (selector? porta?)
4. Identifica perche il Pod `web-init` resta in `Init`
5. Correggi i manifest rotti
6. Verifica che tutti i workload siano sani

### Comandi utili

```bash
kubectl get pods -n lab1 -o wide
kubectl describe pod -n lab1 -l app=web-probes
kubectl logs -n lab1 -l app=web-probes
kubectl describe pod -n lab1 -l app=web-config
kubectl get configmap app-config -n lab1 -o yaml
kubectl get secret app-secret -n lab1 -o yaml
kubectl get svc,endpoints web-service -n lab1
kubectl get pods -n lab1 -l app=web-service --show-labels
kubectl describe pod web-init -n lab1
kubectl logs web-init -n lab1 -c wait-for-file
```

### Verifica finale

Pod tutti in stato sano:

```bash
kubectl get pods -n lab1
```

`Service` con endpoint popolati e risposta HTTP:

```bash
kubectl get endpoints web-service -n lab1
kubectl run curl --rm -it --restart=Never --image=curlimages/curl:8.8.0 -n lab1 -- \
  curl -sS http://web-service.lab1.svc.cluster.local/
```

`ConfigMap` e `Secret` letti correttamente:

```bash
kubectl logs -n lab1 -l app=web-config --tail=5
```

`initContainer` concluso e container principale partito:

```bash
kubectl exec -n lab1 web-init -- cat /shared/ready
```

### Soluzione

I manifest corretti sono in:

```bash
labs/ckad-troubleshooting/solution
```

Per applicare direttamente le soluzioni:

```bash
kubectl delete -f labs/ckad-troubleshooting
kubectl apply -f labs/ckad-troubleshooting/solution
```

### Cleanup

```bash
kubectl delete -f labs/ckad-troubleshooting
```

Per rimuovere anche il cluster k3d dedicato:

```bash
k3d cluster delete lab1
```
