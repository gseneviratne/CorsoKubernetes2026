# Longhorn su Kubernetes

Questa guida descrive come installare [Longhorn](https://longhorn.io/), una soluzione di storage distribuito per Kubernetes, su un cluster gia' esistente.

## Prerequisiti

- un cluster Kubernetes funzionante
- `kubectl` configurato verso il cluster corretto
- `helm` installato
- accesso amministrativo al cluster
- almeno 3 nodi worker per un setup piu' resiliente (consigliato, non obbligatorio)

```bash
kubectl get nodes
```

## Requisiti dei nodi

Longhorn utilizza storage locale sui nodi. Prima di installarlo, verifica:

- spazio disco sufficiente sui nodi
- filesystem supportato e montato correttamente
- connettivita' tra i nodi del cluster
- pacchetti richiesti dal sistema operativo, in particolare `iscsi`

Su molte distribuzioni Linux e' necessario installare il supporto iSCSI.

Esempio su Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y open-iscsi
sudo systemctl enable --now iscsid
```

Esempio su RHEL/CentOS/Rocky:

```bash
sudo yum install -y iscsi-initiator-utils
sudo systemctl enable --now iscsid
```

## Installazione con Helm

Aggiungi il repository Helm ufficiale di Longhorn:

```bash
helm repo add longhorn https://charts.longhorn.io
helm repo update
```

Installa Longhorn nel namespace dedicato `longhorn-system`:

```bash
helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --create-namespace
```

## Verifica dell'installazione

Controlla che i pod siano stati creati correttamente:

```bash
kubectl get pods -n longhorn-system
```

Aspetta che le componenti principali siano in stato `Running` o `Completed`:

```bash
kubectl rollout status deploy/longhorn-driver-deployer -n longhorn-system
kubectl rollout status deploy/longhorn-ui -n longhorn-system
kubectl rollout status deploy/longhorn-manager -n longhorn-system
```

Verifica anche le classi di storage disponibili:

```bash
kubectl get storageclass
```

In genere Longhorn crea una `StorageClass` predefinita o comunque disponibile per il provisioning dinamico dei volumi.

## Accesso alla UI di Longhorn

Per accedere rapidamente alla dashboard web in locale, usa il port-forward:

```bash
kubectl -n longhorn-system port-forward service/longhorn-frontend 8080:80
```

Poi apri il browser su:

[http://localhost:8080](http://localhost:8080)

Da qui puoi controllare:

- nodi
- dischi disponibili
- volumi
- repliche
- snapshot
- backup target

## Test rapido con un PVC

Puoi verificare che Longhorn effettui correttamente il provisioning creando un `PersistentVolumeClaim` di test:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc-longhorn-test
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: longhorn
  resources:
    requests:
      storage: 2Gi
```

Applica il file:

```bash
kubectl apply -f pvc-longhorn-test.yaml
kubectl get pvc
kubectl get pv
```

Se il PVC passa allo stato `Bound`, il provisioning dinamico funziona correttamente.

Per verificare anche il mount del volume dentro a un workload, puoi creare un `Deployment` che usa lo stesso PVC:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-longhorn-test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx-longhorn-test
  template:
    metadata:
      labels:
        app: nginx-longhorn-test
    spec:
      containers:
        - name: nginx
          image: nginx:stable
          ports:
            - containerPort: 80
          volumeMounts:
            - name: longhorn-storage
              mountPath: /usr/share/nginx/html
      volumes:
        - name: longhorn-storage
          persistentVolumeClaim:
            claimName: pvc-longhorn-test
```

Applica il deployment e controlla che il pod parta correttamente:

```bash
kubectl apply -f nginx-longhorn-test.yaml
kubectl rollout status deploy/nginx-longhorn-test
kubectl get pod -l app=nginx-longhorn-test
```

## Disinstallazione

Per rimuovere Longhorn:

```bash
helm uninstall longhorn -n longhorn-system
kubectl delete namespace longhorn-system
```

## Troubleshooting rapido

Se qualcosa non funziona, controlla:

```bash
kubectl get pods -n longhorn-system
kubectl describe pods -n longhorn-system
kubectl logs -n longhorn-system -l app=longhorn-manager
```

Problemi comuni:

- `open-iscsi` non installato sui nodi
- nodi con spazio disco insufficiente
- storage locale non disponibile o non montato correttamente
- firewall o networking che impediscono la comunicazione tra i nodi