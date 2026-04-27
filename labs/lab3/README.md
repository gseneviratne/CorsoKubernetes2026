## Lab: LAB3

Questo laboratorio simula quattro problemi tipici da esame CKAD su argomenti diversi rispetto a lab1 e lab2:

- Rollout di un Deployment con immagine non disponibile (`ImagePullBackOff` e gestione `kubectl rollout`)
- `CronJob` con `schedule` invalido e `restartPolicy` non ammesso
- `ResourceQuota` + `LimitRange` che bloccano la creazione dei Pod
- `StatefulSet` con `Headless Service` per la peer discovery DNS

### Prerequisito k3d

Un cluster con almeno un worker e sufficiente per il lab. Per esempio:

```bash
k3d cluster create lab3 --agents 1
```

Se hai gia un cluster, verifica che sia raggiungibile:

```bash
kubectl cluster-info
kubectl get nodes
```

### Obiettivo

- Diagnosticare workload rotti usando `kubectl describe`, `kubectl logs`, `kubectl get events`, `kubectl rollout status/history`
- Riconoscere sintomi tipici: `ImagePullBackOff`, errori di validazione su `CronJob`, `forbidden: exceeded quota` / `forbidden: maximum cpu usage` da `ResourceQuota`/`LimitRange`, `StatefulSet` bloccato in `Pending` per `serviceName` errato
- Correggere i manifest per portare tutti i workload in uno stato sano

### Applica il lab rotto

```bash
kubectl apply -f labs/lab3
```

Nota: l'apply del `CronJob` rotto e del Deployment `web-quota` puo gia fallire al server-side a causa della validazione (`schedule` non valido, `restartPolicy: Always` non ammesso, quota violata). E un sintomo voluto: l'errore stesso fa parte del lab.

### Sintomo iniziale atteso

```bash
kubectl get all -n lab3
kubectl get pods -n lab3
kubectl get cronjob,jobs -n lab3
kubectl get statefulset,svc -n lab3
kubectl get resourcequota,limitrange -n lab3
```

Ci si aspetta:

- `web-rollout` con Pod in `ImagePullBackOff` / `ErrImagePull` e `Deployment` con `0/3 READY`
- `hello-cron` non creato oppure con errore di validazione (schedule invalido / restartPolicy non valido)
- `web-quota` con `ReplicaSet` che non riesce a creare i Pod: evento `forbidden: failed quota` o `forbidden: minimum cpu usage per Container is ...`
- `cache` (`StatefulSet`) con Pod `cache-0` in `Pending` (DNS non risolto) o creato ma senza peer discovery, perche `serviceName` punta a un `Service` non esistente e il `Service` `cache-svc` non e headless

### Attivita

1. Identifica perche `web-rollout` non avvia i Pod e correggi l'immagine; usa `kubectl rollout` per verificare la situazione
2. Identifica i due errori di validazione del `CronJob` `hello-cron` (formato `schedule` e `restartPolicy`) e correggili
3. Identifica perche `web-quota` non puo creare Pod nonostante la quota abbia spazio: confronta il manifest con i vincoli imposti da `ResourceQuota` e `LimitRange`
4. Identifica perche lo `StatefulSet` `cache` non riesce a fare peer discovery: controlla `serviceName`, tipo del `Service` e record DNS
5. Correggi i manifest rotti
6. Verifica che tutti i workload siano sani

### Comandi utili

```bash
kubectl get pods -n lab3 -o wide
kubectl describe pod -n lab3 -l app=web-rollout
kubectl rollout status deploy/web-rollout -n lab3
kubectl rollout history deploy/web-rollout -n lab3

kubectl get cronjob hello-cron -n lab3 -o yaml
kubectl get events -n lab3 --sort-by=.lastTimestamp | grep -i cron

kubectl describe rs -n lab3 -l app=web-quota
kubectl get resourcequota lab3-quota -n lab3 -o yaml
kubectl get limitrange lab3-limits -n lab3 -o yaml

kubectl get statefulset cache -n lab3 -o yaml
kubectl get svc -n lab3
kubectl get pods -n lab3 -l app=cache -o wide
kubectl run dnsutils --rm -it --restart=Never -n lab3 \
  --image=registry.k8s.io/e2e-test-images/jessie-dnsutils:1.7 -- \
  nslookup cache-0.cache-headless.lab3.svc.cluster.local
```

### Verifica finale

Pod e workload in stato sano:

```bash
kubectl get pods,deploy,sts,cronjob -n lab3
```

Il Deployment `web-rollout` con tutti i replica `Ready`:

```bash
kubectl rollout status deploy/web-rollout -n lab3
kubectl get deploy web-rollout -n lab3
```

Il `CronJob` valido e con almeno un Job completato:

```bash
kubectl get cronjob hello-cron -n lab3
kubectl get jobs -n lab3 -l app=hello-cron
kubectl logs -n lab3 -l app=hello-cron --tail=20
```

Il Deployment `web-quota` con i Pod `Running` e quota usata:

```bash
kubectl get pods -n lab3 -l app=web-quota
kubectl describe resourcequota lab3-quota -n lab3
```

Lo `StatefulSet` `cache` con peer DNS funzionante:

```bash
kubectl get sts cache -n lab3
kubectl get svc cache-headless -n lab3
kubectl run dnsutils --rm -it --restart=Never -n lab3 \
  --image=registry.k8s.io/e2e-test-images/jessie-dnsutils:1.7 -- \
  nslookup cache-0.cache-headless.lab3.svc.cluster.local
```

### Soluzione

I manifest corretti sono in:

```bash
labs/lab3/solution
```

Per applicare direttamente le soluzioni:

```bash
kubectl delete -f labs/lab3
kubectl apply -f labs/lab3/solution
```

### Cleanup

```bash
kubectl delete -f labs/lab3
```

Per rimuovere anche il cluster k3d dedicato:

```bash
k3d cluster delete lab3
```
