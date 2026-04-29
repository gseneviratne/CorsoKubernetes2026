# Cheatsheet CKA / CKAD

Questa cheatsheet raccoglie comandi veloci da usare durante esercizi ed esami CKA/CKAD. L'obiettivo e lavorare in modo rapido, generare manifest YAML invece di scriverli da zero e usare `kubectl` per ispezione, debug e correzioni.

## Setup veloce kubectl

### Alias essenziale

```bash
alias k=kubectl
```

## Regole d'oro da esame

- Usa sempre `--dry-run=client -o yaml > file.yaml` per generare manifest.
- Usa `kubectl explain <resource>.<field> --recursive` per ricordare i campi.
- Imposta subito il namespace corretto con `kubectl config set-context --current --namespace <ns>`.
- Prima guarda lo stato con `kubectl get`, poi dettagli con `kubectl describe`, poi log/eventi.
- Evita editing manuale lungo: genera YAML, modifica solo i campi necessari, applica.
- Per troubleshooting guarda sempre `Events`, `READY`, `RESTARTS`, `AGE`, `node`, `labels`, `selectors`.

## Namespace e contesto

```bash
kubectl config get-contexts
kubectl config current-context
kubectl config use-context <context>

kubectl create ns dev
kubectl config set-context --current --namespace dev
kubectl get all
kubectl get all -A
```

## Generazione manifest YAML

### Pod

```bash
kubectl run nginx --image=nginx --dry-run=client -o yaml > pod.yaml
kubectl run busybox --image=busybox --restart=Never --command -- sleep 3600 --dry-run=client -o yaml > pod-busybox.yaml
kubectl run curl --image=curlimages/curl --restart=Never -it --rm -- sh
```

### Deployment

```bash
kubectl create deployment web --image=nginx --replicas=3 --dry-run=client -o yaml > deploy.yaml
kubectl set image deployment/web nginx=nginx:1.27
kubectl scale deployment web --replicas=5
kubectl rollout status deployment/web
kubectl rollout history deployment/web
kubectl rollout undo deployment/web
```

### Service

```bash
kubectl expose pod nginx --port=80 --target-port=80 --name=nginx-svc --dry-run=client -o yaml > svc.yaml
kubectl expose deployment web --port=80 --target-port=80 --type=ClusterIP --dry-run=client -o yaml > svc.yaml
kubectl expose deployment web --port=80 --target-port=8080 --type=NodePort --dry-run=client -o yaml > nodeport.yaml
```

### Job e CronJob

```bash
kubectl create job pi --image=perl -- perl -Mbignum=bpi -wle 'print bpi(2000)' --dry-run=client -o yaml > job.yaml
kubectl create cronjob hello --image=busybox --schedule='*/5 * * * *' -- /bin/sh -c 'date; echo hello' --dry-run=client -o yaml > cronjob.yaml
kubectl create job manual-run --from=cronjob/hello
```

### ConfigMap e Secret

```bash
kubectl create configmap app-config --from-literal=ENV=prod --from-literal=LOG_LEVEL=info --dry-run=client -o yaml > cm.yaml
kubectl create configmap app-config --from-file=app.properties --dry-run=client -o yaml > cm-file.yaml

kubectl create secret generic app-secret --from-literal=username=admin --from-literal=password='S3cr3t' --dry-run=client -o yaml > secret.yaml
kubectl create secret tls tls-secret --cert=tls.crt --key=tls.key --dry-run=client -o yaml > tls-secret.yaml
```

### ServiceAccount, Role, RoleBinding

```bash
kubectl create serviceaccount app-sa --dry-run=client -o yaml > sa.yaml
kubectl create role pod-reader --verb=get,list,watch --resource=pods --dry-run=client -o yaml > role.yaml
kubectl create rolebinding read-pods --role=pod-reader --serviceaccount=default:app-sa --dry-run=client -o yaml > rb.yaml
kubectl auth can-i list pods --as=system:serviceaccount:default:app-sa
```

## Comandi di ispezione

```bash
kubectl get pods -o wide
kubectl get pods --show-labels
kubectl get pod <pod> -o yaml
kubectl get pod <pod> -o jsonpath='{.status.podIP}{"\n"}'
kubectl describe pod <pod>
kubectl get events --sort-by=.lastTimestamp
kubectl api-resources
kubectl api-versions
kubectl explain pod.spec.containers --recursive
```

Output utili:

```bash
kubectl get pods -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,IP:.status.podIP,PHASE:.status.phase
kubectl get deploy -o custom-columns=NAME:.metadata.name,READY:.status.readyReplicas,AVAILABLE:.status.availableReplicas
kubectl get pods -l app=web
kubectl get all -l app=web
```

## Debug Pod e workload

```bash
kubectl logs <pod>
kubectl logs <pod> -c <container>
kubectl logs <pod> --previous
kubectl logs -l app=web --tail=100
kubectl exec -it <pod> -- sh
kubectl describe pod <pod>
kubectl get events --field-selector involvedObject.name=<pod>
```

Pod temporanei per test:

```bash
kubectl run tmp-shell --image=busybox --restart=Never -it --rm -- sh
kubectl run dns-test --image=busybox --restart=Never -it --rm -- nslookup kubernetes.default
kubectl run curl --image=curlimages/curl --restart=Never -it --rm -- curl -I http://svc-name
```

Debug avanzato:

```bash
kubectl debug node/<node-name> -it --image=busybox
kubectl debug pod/<pod> -it --image=busybox --target=<container>
```

## Label, selector e annotazioni

```bash
kubectl label pod nginx app=web env=dev
kubectl label pod nginx env=prod --overwrite
kubectl annotate pod nginx owner=team-a
kubectl get pods -l app=web
kubectl get pods -l 'env in (dev,prod)'
kubectl get pods -l app=web --show-labels
```

## ConfigMap e Secret nei Pod

Variabile singola:

```yaml
env:
- name: LOG_LEVEL
  valueFrom:
    configMapKeyRef:
      name: app-config
      key: LOG_LEVEL
```

Tutte le variabili:

```yaml
envFrom:
- configMapRef:
    name: app-config
- secretRef:
    name: app-secret
```

Volume:

```yaml
volumes:
- name: config
  configMap:
    name: app-config
containers:
- name: app
  image: nginx
  volumeMounts:
  - name: config
    mountPath: /etc/config
```

## Probes

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

Command probe:

```yaml
livenessProbe:
  exec:
    command:
    - cat
    - /tmp/healthy
```

## Resources, quota e limit range

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

Controlli:

```bash
kubectl describe resourcequota
kubectl describe limitrange
kubectl top nodes
kubectl top pods
```

## Scheduling

### nodeSelector

```yaml
nodeSelector:
  disk: ssd
```

```bash
kubectl label node <node> disk=ssd
kubectl get nodes --show-labels
```

### Taints e tolerations

```bash
kubectl taint nodes <node> dedicated=gpu:NoSchedule
kubectl taint nodes <node> dedicated=gpu:NoSchedule-
```

```yaml
tolerations:
- key: dedicated
  operator: Equal
  value: gpu
  effect: NoSchedule
```

### Affinity semplice

```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - worker-1
```

## Storage

PVC:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

Mount in Pod:

```yaml
volumes:
- name: data
  persistentVolumeClaim:
    claimName: data
containers:
- name: app
  image: nginx
  volumeMounts:
  - name: data
    mountPath: /usr/share/nginx/html
```

Comandi:

```bash
kubectl get pv,pvc
kubectl describe pvc data
kubectl get storageclass
```

## Network e DNS

```bash
kubectl get svc,endpoints
kubectl describe svc <service>
kubectl get endpoints <service> -o yaml
kubectl run dns-test --image=busybox --restart=Never -it --rm -- nslookup <service>.<namespace>.svc.cluster.local
```

Pattern DNS:

```text
<service>
<service>.<namespace>
<service>.<namespace>.svc
<service>.<namespace>.svc.cluster.local
```

## NetworkPolicy

Esempio: nega tutto in ingresso nel namespace.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
spec:
  podSelector: {}
  policyTypes:
  - Ingress
```

Esempio: consenti traffico verso Pod `app=web` solo da Pod `role=frontend`.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-web
spec:
  podSelector:
    matchLabels:
      app: web
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: frontend
    ports:
    - protocol: TCP
      port: 80
```

## SecurityContext

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 2000
containers:
- name: app
  image: nginx
  securityContext:
    allowPrivilegeEscalation: false
    capabilities:
      drop:
      - ALL
```

## RBAC

```bash
kubectl auth can-i get pods
kubectl auth can-i create deployments --namespace dev
kubectl auth can-i list secrets --as=system:serviceaccount:dev:app-sa -n dev
```

Role minimale:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
rules:
- apiGroups:
  - ""
  resources:
  - pods
  verbs:
  - get
  - list
  - watch
```

## Deployment rollout

```bash
kubectl create deployment web --image=nginx:1.26 --replicas=3
kubectl set image deployment/web nginx=nginx:1.27 --record
kubectl rollout status deployment/web
kubectl rollout history deployment/web
kubectl rollout history deployment/web --revision=2
kubectl rollout undo deployment/web
kubectl rollout undo deployment/web --to-revision=1
kubectl rollout restart deployment/web
kubectl pause deployment/web
kubectl resume deployment/web
```

Strategia rolling update:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 1
    maxSurge: 1
```

## Job e CronJob troubleshooting

```bash
kubectl get jobs,cronjobs
kubectl describe job <job>
kubectl logs job/<job>
kubectl delete job <job>
kubectl create job test-run --from=cronjob/<cronjob>
```

Campi importanti:

```yaml
spec:
  completions: 3
  parallelism: 1
  backoffLimit: 2
  template:
    spec:
      restartPolicy: Never
```

Per `CronJob`, `restartPolicy` deve essere `Never` oppure `OnFailure`, non `Always`.

## Static Pod e componenti cluster

Tipico CKA:

```bash
ls /etc/kubernetes/manifests
kubectl get pods -n kube-system
kubectl describe pod -n kube-system <pod>
```

Manifest static Pod:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: static-nginx
spec:
  containers:
  - name: nginx
    image: nginx
```

## Etcd backup e restore

Tipico CKA, da adattare ai path del cluster:

```bash
ETCDCTL_API=3 etcdctl snapshot save /tmp/etcd-snapshot.db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

ETCDCTL_API=3 etcdctl snapshot status /tmp/etcd-snapshot.db --write-out=table
```

## Cluster upgrade rapido

Tipico CKA, verifica sempre la versione richiesta:

```bash
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data
sudo apt-mark unhold kubeadm kubelet kubectl
sudo apt-get update
sudo apt-get install -y kubeadm=<version>
sudo kubeadm upgrade node
sudo apt-get install -y kubelet=<version> kubectl=<version>
sudo systemctl daemon-reload
sudo systemctl restart kubelet
sudo apt-mark hold kubeadm kubelet kubectl
kubectl uncordon <node>
```

Control plane:

```bash
sudo kubeadm upgrade plan
sudo kubeadm upgrade apply v<version>
```

## Troubleshooting checklist

Pod non parte:

```bash
kubectl get pod <pod> -o wide
kubectl describe pod <pod>
kubectl logs <pod> --previous
kubectl get events --sort-by=.lastTimestamp
```

Service non risponde:

```bash
kubectl get svc,endpoints <svc>
kubectl get pods --show-labels
kubectl describe svc <svc>
kubectl run curl --image=curlimages/curl --restart=Never -it --rm -- curl -v http://<svc>:<port>
```

Deployment non aggiorna:

```bash
kubectl rollout status deploy/<deploy>
kubectl describe deploy/<deploy>
kubectl describe rs -l app=<label>
kubectl get pods -l app=<label>
```

PVC in `Pending`:

```bash
kubectl get pv,pvc,storageclass
kubectl describe pvc <pvc>
kubectl describe pod <pod>
```

Scheduling fallisce:

```bash
kubectl describe pod <pod>
kubectl get nodes --show-labels
kubectl describe node <node>
kubectl get events --sort-by=.lastTimestamp
```

## Comandi veloci da ricordare

```bash
kubectl apply -f file.yaml
kubectl delete -f file.yaml
kubectl replace -f file.yaml
kubectl edit deploy/<name>
kubectl diff -f file.yaml
kubectl explain deployment.spec.template.spec.containers
kubectl get pod <pod> -o yaml > pod.yaml
kubectl get deploy <deploy> -o yaml > deploy.yaml
kubectl delete pod <pod> --force --grace-period=0
```

## JSONPath utili

```bash
kubectl get nodes -o jsonpath='{.items[*].metadata.name}{"\n"}'
kubectl get pod <pod> -o jsonpath='{.spec.nodeName}{"\n"}'
kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[*].restartCount}{"\n"}'
kubectl get svc <svc> -o jsonpath='{.spec.clusterIP}{"\n"}'
kubectl get secret <secret> -o jsonpath='{.data.password}' | base64 -d; echo
```

## Vim rapido per YAML

```vim
:set number
:set paste
:set expandtab
:set tabstop=2 shiftwidth=2
:%s/old/new/g
```

## Mini workflow consigliato

```bash
kubectl create deployment web --image=nginx --replicas=2 --dry-run=client -o yaml > web.yaml
vim web.yaml
kubectl apply -f web.yaml
kubectl get deploy,pods,svc -o wide
kubectl describe pod -l app=web
kubectl logs -l app=web
```
