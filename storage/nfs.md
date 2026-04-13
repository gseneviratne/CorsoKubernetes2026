# NFS su Kubernetes con server NFS Linux

Questa guida mostra come configurare uno share NFS su una macchina Linux e usarlo come storage persistente in Kubernetes.

L'idea e' semplice:

- il server Linux esporta una directory via NFS
- Kubernetes usa quella directory tramite un `PersistentVolume`
- i pod montano il volume tramite `PersistentVolumeClaim`

## Prerequisiti

- un cluster Kubernetes gia' disponibile
- `kubectl` configurato verso il cluster corretto
- una macchina Linux raggiungibile dai nodi del cluster
- accesso `root` o `sudo` al server Linux

## 1. Installare il server NFS su Linux

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install -y nfs-kernel-server
```

## 2. Preparare la directory condivisa

Crea la directory che verra' esportata via NFS:

```bash
sudo mkdir -p /srv/nfs/k8s
sudo chown nobody:nogroup /srv/nfs/k8s 2>/dev/null || sudo chown nfsnobody:nfsnobody /srv/nfs/k8s
sudo chmod 0777 /srv/nfs/k8s
echo "Storage NFS per Kubernetes" | sudo tee /srv/nfs/k8s/README.txt >/dev/null
```

Questa directory conterra' i dati realmente condivisi ai pod.

## 3. Configurare l'export NFS

Modifica `/etc/exports` sul server Linux e aggiungi una riga simile a questa:

```exports
/srv/nfs/k8s 172.18.8.0/24(rw,sync,no_subtree_check,no_root_squash)
```

Note:
- `rw` abilita lettura e scrittura
- `sync` rende le scritture piu' sicure
- `no_subtree_check` evita controlli non necessari sulle sottodirectory
- `no_root_squash` e' comodo nei laboratori; in ambienti production va valutato con attenzione

Applica la configurazione:

```bash
sudo exportfs -rav
```

Verifica gli export attivi:

```bash
sudo exportfs -v
showmount -e 172.18.8.111
```

## 4. Aprire il firewall se necessario

Se sul server Linux e' attivo un firewall, abilita il traffico NFS.

Esempio con `firewalld`:

```bash
sudo firewall-cmd --add-service=nfs --permanent
sudo firewall-cmd --add-service=mountd --permanent
sudo firewall-cmd --add-service=rpc-bind --permanent
sudo firewall-cmd --reload
```

Esempio con `ufw`:

```bash
sudo ufw allow from 172.18.8.0/24 to any port nfs
```

## 5. Installare il client NFS sui nodi

Esegui sui nodi Kubernetes:

```bash
sudo apt update
sudo apt install -y nfs-common
sudo systemctl restart kubelet
```

## 6. Creare la StorageClass

Per usare in modo esplicito la classe `nfs-manual`, crea prima anche la relativa `StorageClass`.

Salva questo file come `storageclass-nfs.yaml`:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: nfs-manual
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: Immediate
```

Applica la risorsa:

```bash
kubectl apply -f storageclass-nfs.yaml
kubectl get storageclass
```

Questa `StorageClass` non effettua provisioning dinamico: serve a dare un nome coerente al `PersistentVolume` e al `PersistentVolumeClaim` che creerai nei passaggi successivi.

## 7. Creare il PersistentVolume

Salva questo file come `pv-nfs.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-nfs-linux
spec:
  capacity:
    storage: 5Gi
  accessModes:
    - ReadWriteMany
  persistentVolumeReclaimPolicy: Retain
  storageClassName: nfs-manual
  nfs:
    server: 172.18.8.111
    path: /srv/nfs/k8s
```

Applica la risorsa:

```bash
kubectl apply -f pv-nfs.yaml
kubectl get pv
```

## 8. Creare il PersistentVolumeClaim

Salva questo file come `pvc-nfs.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc-nfs-linux
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: nfs-manual
  resources:
    requests:
      storage: 1Gi
```

Applica il claim:

```bash
kubectl apply -f pvc-nfs.yaml
kubectl get pvc
```

Il PVC deve andare in stato `Bound`.

## 9. Deployment di esempio

Questo esempio usa:

- un `initContainer` che crea una pagina `index.html` dentro al volume NFS
- un container `nginx` che serve il contenuto della directory montata

Salva questo file come `deploy-nfs-nginx.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-nfs-demo
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx-nfs-demo
  template:
    metadata:
      labels:
        app: nginx-nfs-demo
    spec:
      initContainers:
        - name: init-content
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              cat <<'EOF' > /data/index.html
              <html>
              <body>
                <h1>NFS su Kubernetes</h1>
                <p>Volume NFS Linux montato correttamente.</p>
              </body>
              </html>
              EOF
          volumeMounts:
            - name: nfs-storage
              mountPath: /data
      containers:
        - name: nginx
          image: nginx:stable
          ports:
            - containerPort: 80
          volumeMounts:
            - name: nfs-storage
              mountPath: /usr/share/nginx/html
      volumes:
        - name: nfs-storage
          persistentVolumeClaim:
            claimName: pvc-nfs-linux
```

Applica il deployment:

```bash
kubectl apply -f deploy-nfs-nginx.yaml
kubectl rollout status deployment/nginx-nfs-demo
kubectl get pod -l app=nginx-nfs-demo
```

## 10. Verifica del mount

Controlla che il file sia stato scritto sul volume condiviso:

```bash
kubectl exec deploy/nginx-nfs-demo -- ls -l /usr/share/nginx/html
kubectl exec deploy/nginx-nfs-demo -- cat /usr/share/nginx/html/index.html
```

Puoi anche verificare direttamente sul server Linux:

```bash
ls -l /srv/nfs/k8s
cat /srv/nfs/k8s/index.html
```

Per testare anche via HTTP puoi fare un port-forward:

```bash
kubectl port-forward deploy/nginx-nfs-demo 8080:80
```

Poi apri:

[http://localhost:8080](http://localhost:8080)

## Troubleshooting rapido

Se il pod non parte oppure il volume non viene montato, controlla:

```bash
kubectl describe pod -l app=nginx-nfs-demo
kubectl describe pvc pvc-nfs-linux
kubectl get events --sort-by=.lastTimestamp
showmount -e 172.18.8.111
sudo exportfs -v
sudo systemctl status nfs-server || sudo systemctl status nfs-kernel-server
```
