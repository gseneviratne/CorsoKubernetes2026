## Lab: RBAC troubleshooting

Questo laboratorio simula tre problemi classici da CKA/CKAD legati ai permessi RBAC in Kubernetes

### Prerequisito

Usa un cluster attivo e un contesto `kubectl` con permessi sufficienti per usare l'impersonazione `--as`:

```bash
kubectl cluster-info
kubectl auth can-i impersonate serviceaccounts
```

### Obiettivo

- Capire come verificare i permessi con `kubectl auth can-i`
- Fare troubleshooting di `Role` e `RoleBinding`
- Correggere i manifest per permettere a ogni `ServiceAccount` di eseguire solo l'azione prevista

### Applica il lab rotto

```bash
kubectl apply -f labs/rbac-troubleshooting
```

### Sintomo iniziale atteso

Tutti e tre i controlli iniziali falliscono:

```bash
kubectl auth can-i list pods -n rbac-lab --as system:serviceaccount:rbac-lab:pod-reader-sa
kubectl get secret app-credentials -n rbac-lab --as system:serviceaccount:rbac-lab:secret-reader-sa
kubectl scale deployment web -n rbac-lab --replicas=3 --as system:serviceaccount:rbac-lab:deployer-sa
```

### Attivita

1. Verifica quali permessi mancano a `pod-reader-sa`
2. Identifica perche `secret-reader-sa` non riesce a leggere `app-credentials`
3. Identifica perche `deployer-sa` non riesce a scalare `Deployment/web`
4. Correggi i manifest RBAC
5. Verifica che tutti i controlli vadano a buon fine

### Comandi utili

```bash
kubectl get sa,role,rolebinding -n rbac-lab
kubectl describe role pod-reader -n rbac-lab
kubectl describe role secret-reader -n rbac-lab
kubectl describe role deployer -n rbac-lab
kubectl auth can-i list pods -n rbac-lab --as system:serviceaccount:rbac-lab:pod-reader-sa
kubectl auth can-i get secrets -n rbac-lab --as system:serviceaccount:rbac-lab:secret-reader-sa
kubectl auth can-i update deployments/scale -n rbac-lab --as system:serviceaccount:rbac-lab:deployer-sa
kubectl get rolebinding -n rbac-lab -o yaml
kubectl get secret app-credentials -n rbac-lab --as system:serviceaccount:rbac-lab:secret-reader-sa
kubectl scale deployment web -n rbac-lab --replicas=3 --as system:serviceaccount:rbac-lab:deployer-sa
kubectl get deployment web -n rbac-lab
```

### Verifica finale

```bash
kubectl auth can-i list pods -n rbac-lab --as system:serviceaccount:rbac-lab:pod-reader-sa
kubectl auth can-i get secrets -n rbac-lab --as system:serviceaccount:rbac-lab:secret-reader-sa
kubectl auth can-i update deployments/scale -n rbac-lab --as system:serviceaccount:rbac-lab:deployer-sa
kubectl get secret app-credentials -n rbac-lab --as system:serviceaccount:rbac-lab:secret-reader-sa
kubectl scale deployment web -n rbac-lab --replicas=3 --as system:serviceaccount:rbac-lab:deployer-sa
kubectl get pods -n rbac-lab
```

### Soluzione

I manifest corretti sono in:

```bash
labs/rbac-troubleshooting/solution
```

### Cleanup

```bash
kubectl delete -f labs/rbac-troubleshooting
```
