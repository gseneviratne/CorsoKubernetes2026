## Lab: Canary deployment

La strategia `canary` rilascia una nuova versione a una parte del traffico, mantenendo attiva la versione stabile.

### Obiettivo CKAD

- Pubblicare una nuova versione con impatto limitato
- Verificare il comportamento della nuova release prima della promozione completa
- Effettuare rollback rapido se la versione `canary` mostra problemi

### Idea chiave

Con i soli oggetti base di Kubernetes, la forma piu semplice di `canary` si realizza con:

- un `Deployment` stabile
- un `Deployment` canary
- un unico `Service` che seleziona entrambi i gruppi di Pod

Il traffico viene distribuito tra i Pod dietro il `Service`.

Questo significa che la percentuale e' **approssimativa** e dipende dal numero di repliche:

- `stable=5`, `canary=1` circa 1 richiesta su 6 va alla canary
- `stable=4`, `canary=2` circa 2 richieste su 6

### Esempio

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-stable
spec:
  replicas: 5
  selector:
    matchLabels:
      app: web
      track: stable
  template:
    metadata:
      labels:
        app: web
        track: stable
    spec:
      containers:
      - name: web
        image: nginx:1.25
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-canary
spec:
  replicas: 1
  selector:
    matchLabels:
      app: web
      track: canary
  template:
    metadata:
      labels:
        app: web
        track: canary
    spec:
      containers:
      - name: web
        image: nginx:1.27
---
apiVersion: v1
kind: Service
metadata:
  name: web-svc
spec:
  selector:
    app: web
  ports:
  - port: 80
    targetPort: 80
```

### Passi operativi

1. Rilascia la versione stabile

```bash
kubectl apply -f web-stable.yaml
kubectl rollout status deployment/web-stable
```

2. Espone l'applicazione tramite un `Service` comune

```bash
kubectl apply -f web-service.yaml
kubectl get svc web-svc
kubectl get endpoints web-svc
```

3. Crea la versione `canary` con poche repliche

```bash
kubectl apply -f web-canary.yaml
kubectl rollout status deployment/web-canary
kubectl get pods -l app=web --show-labels
```

4. Controlla che il traffico venga distribuito anche ai Pod `canary`

Verifica:

- readiness della versione canary
- log applicativi
- metriche o error rate
- eventuali test funzionali ripetuti

```bash
kubectl get endpoints web-svc
kubectl logs deploy/web-canary
```

5. Aumenta gradualmente il peso della canary

Esempio:

```bash
kubectl scale deployment web-canary --replicas=2
kubectl scale deployment web-stable --replicas=4
kubectl get deploy
```

6. Promuovi la canary a nuova versione stabile

Hai due opzioni tipiche:

- aggiornare il `Deployment` stabile alla nuova immagine
- scalare `canary` verso l'alto e `stable` verso zero, poi rinominare o riallineare i manifest

Esempio semplice:

```bash
kubectl set image deployment/web-stable web=nginx:1.27
kubectl rollout status deployment/web-stable
kubectl scale deployment web-canary --replicas=0
```

### Rollback

Se la canary fallisce:

```bash
kubectl scale deployment web-canary --replicas=0
kubectl scale deployment web-stable --replicas=5
```

Il `Service` continua a puntare ai Pod stabili, quindi il rollback e' rapido.

### Comandi utili da esame

```bash
kubectl get deploy,svc,pods -l app=web -o wide
kubectl describe svc web-svc
kubectl get endpoints web-svc
kubectl logs deploy/web-canary
kubectl rollout status deployment/web-stable
kubectl rollout status deployment/web-canary
kubectl scale deployment web-canary --replicas=0
```

### Cosa ricordare per CKAD

- `Canary` con Kubernetes base si fa usando piu `Deployment` dietro lo stesso `Service`
- La distribuzione del traffico tramite repliche e' solo approssimativa
- Per una promozione completa puoi aggiornare il `Deployment` stabile e poi rimuovere la canary
- Il rollback piu veloce consiste nel portare la canary a zero repliche
