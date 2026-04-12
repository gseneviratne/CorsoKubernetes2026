## Lab: Blue/Green deployment

Questa strategia non usa una risorsa Kubernetes dedicata: si costruisce combinando `Deployment`, `Service` e `label selector`.

### Obiettivo CKAD

- Tenere in produzione una versione stabile (`blue`)
- Preparare una nuova versione (`green`) senza impattare il traffico live
- Spostare il traffico in modo rapido e reversibile
- Fare rollback cambiando il `selector` del `Service`

### Idea chiave

In Kubernetes il traffico applicativo entra di solito tramite un `Service`.

Per fare `blue/green` si creano due `Deployment` distinti:

- `app-blue`
- `app-green`

Entrambi espongono la stessa applicazione, ma con label differenti, per esempio:

- `app=web`
- `version=blue`
- `version=green`

Il `Service` di produzione punta a **una sola versione per volta**.

### Esempio minimo

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-blue
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
      version: blue
  template:
    metadata:
      labels:
        app: web
        version: blue
    spec:
      containers:
      - name: web
        image: nginx:1.25
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-green
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
      version: green
  template:
    metadata:
      labels:
        app: web
        version: green
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
    version: blue
  ports:
  - port: 80
    targetPort: 80
```

### Passi operativi

1. Crea la versione stabile `blue`

```bash
kubectl apply -f app-blue.yaml
kubectl get deploy,pods -l app=web
```

2. Crea il `Service` di produzione che punta a `blue`

```bash
kubectl apply -f web-service.yaml
kubectl get svc web-svc
kubectl get endpoints web-svc
```

3. Rilascia la nuova versione `green` senza spostare ancora il traffico

```bash
kubectl apply -f app-green.yaml
kubectl rollout status deployment/app-green
kubectl get pods -l app=web
```

4. Verifica che `green` sia pronta

Controlla almeno:

- pod in `Running`
- readiness probe passata
- log corretti
- eventuale test tramite `port-forward` o un `Service` temporaneo

Esempio:

```bash
kubectl port-forward deploy/app-green 8080:80
```

5. Sposta il traffico cambiando il `selector` del `Service`

```bash
kubectl patch svc web-svc -p '{"spec":{"selector":{"app":"web","version":"green"}}}'
kubectl get endpoints web-svc
```

Da questo momento il traffico va alla versione `green`.

6. Se tutto funziona, tieni `green` come nuova produzione

Opzionalmente puoi:

- lasciare `blue` per un rollback rapido
- scalare `blue` a zero
- eliminare `blue` a fine validazione

### Rollback

Il rollback e' immediato: basta rimettere il `Service` sulla versione precedente.

```bash
kubectl patch svc web-svc -p '{"spec":{"selector":{"app":"web","version":"blue"}}}'
```

### Comandi utili da esame

```bash
kubectl get deploy,svc,pods -l app=web -o wide
kubectl describe svc web-svc
kubectl get endpoints web-svc
kubectl rollout status deployment/app-blue
kubectl rollout status deployment/app-green
kubectl logs deploy/app-green
```

### Cosa ricordare per CKAD

- Kubernetes non ha un oggetto nativo chiamato `BlueGreenDeployment`
- La strategia si implementa con `Deployment` separati + `Service`
- Il passaggio di traffico avviene cambiando il `selector` del `Service`
- Il rollback e' rapido perche non richiede una nuova immagine o un nuovo rollout
