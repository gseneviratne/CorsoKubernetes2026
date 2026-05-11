# Monitoring stack - Prometheus + Grafana + dashboards

Questo lab installa uno stack di monitoring completo a partire da manifest puri (niente Helm chart, niente operator), pensato per imparare i pezzi che lo compongono. Alla fine avrai:

- **Prometheus** che fa scrape di api-server, kubelet, cAdvisor, kube-state-metrics, node-exporter e dei pod annotati `prometheus.io/scrape: "true"`
- **node-exporter** come DaemonSet (CPU, memoria, disco e rete dei nodi)
- **kube-state-metrics** (stato di pod, deployment, job, ecc. dall'API)
- **Grafana** con datasource Prometheus pre-configurato e tre dashboard caricate via file provider:
  - `Cluster Overview` - salute generale del cluster
  - `Pod Resources` - **questa e' la dashboard che usi per dimensionare requests e limits**
  - `Demo App` - le metriche HTTP esposte dall'app di esempio
- una **demo app** (`prometheus-example-app`) che espone `/metrics`
- un **load generator** che la stressa, cosi' i grafici non sono piatti

> Per gli ambienti di produzione il pattern reale e' usare il chart Helm `kube-prometheus-stack` (Operator + ServiceMonitor + Alertmanager). Vedi sezione finale.

## Struttura

```text
labs/monitoring/
├── README.md
├── queries.md                       # cheatsheet PromQL completa
├── 00-namespace.yaml
├── 10-prometheus-rbac.yaml          # SA + ClusterRole + Binding
├── 11-prometheus-config.yaml        # ConfigMap con prometheus.yml
├── 12-prometheus-deploy.yaml
├── 13-prometheus-service.yaml
├── 20-node-exporter.yaml            # DaemonSet
├── 21-kube-state-metrics.yaml       # SA + RBAC + Deploy + Service
├── 30-grafana-config.yaml           # datasource + dashboard provider
├── 32-grafana-deploy.yaml
├── 33-grafana-service.yaml
├── 40-demo-app.yaml                 # app che espone /metrics
├── 41-load-generator.yaml
└── dashboards/
    ├── cluster-overview.json
    ├── pod-resources.json
    └── demo-app.json
```

I numeri nei prefissi indicano l'ordine in cui le risorse sono state pensate, ma `kubectl apply -f labs/monitoring/` le applica tutte insieme: Kubernetes risolve poi le dipendenze al boot dei pod.

## Prerequisiti

Un cluster k3d/k3s/qualunque cluster Kubernetes >= 1.28. Per il lab basta un cluster a singolo nodo:

```bash
k3d cluster create monitoring --agents 1
kubectl cluster-info
```

## Setup

```bash
# 1. namespace + tutti i manifest dello stack
kubectl apply -f labs/monitoring/

# 2. crea il ConfigMap delle dashboard a partire dai file JSON
kubectl -n monitoring create configmap grafana-dashboards \
  --from-file=labs/monitoring/dashboards/ \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Grafana e' partito ma ha caricato le dashboard solo all'avvio del provider:
#    forziamo un restart per essere sicuri che le veda
kubectl -n monitoring rollout restart deploy/grafana
```

Aspetta che tutto sia ready:

```bash
kubectl -n monitoring rollout status deploy/prometheus
kubectl -n monitoring rollout status deploy/grafana
kubectl -n monitoring rollout status deploy/kube-state-metrics
kubectl -n monitoring rollout status ds/node-exporter
kubectl -n monitoring rollout status deploy/demo-app
```

## Accesso alle UI

Niente Ingress: usa `kubectl port-forward` cosi' resta semplice da rimettere giu'.

```bash
# Prometheus
kubectl -n monitoring port-forward svc/prometheus 9090:9090
# poi apri http://localhost:9090

# Grafana (utente: admin / password: admin)
kubectl -n monitoring port-forward svc/grafana 3000:3000
# poi apri http://localhost:3000
```

In Grafana le dashboard del lab sono in **Dashboards -> Lab**:

- *Cluster Overview*
- *Pod Resources - sizing requests e limits*
- *Demo App - HTTP metrics*

## Verifiche

### Prometheus sta scrape-ando tutto?

Dalla UI di Prometheus, vai in **Status -> Targets**. Devi vedere `up=1` per:

- `prometheus`
- `kubernetes-apiservers`
- `kubernetes-nodes`
- `kubernetes-cadvisor`
- `kubernetes-pods` (qui finiscono `demo-app` e `node-exporter` grazie alle annotation)
- `kubernetes-service-endpoints` (qui finisce `kube-state-metrics`)

Lanci di sanity:

```promql
up
sum by (job) (up)
```

### Le metriche cAdvisor arrivano?

```promql
# Pod scoperti via cAdvisor
count(container_cpu_usage_seconds_total{container!=""})

# Top 5 pod per CPU
topk(5, sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{container!=""}[5m])))
```

### kube-state-metrics arriva?

```promql
# Pod totali nel cluster
count(kube_pod_info)

# Pod NOT Ready
kube_pod_status_ready{condition="true"} == 0
```

### node-exporter arriva?

```promql
# CPU % per nodo
100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])))

# Memoria libera per nodo
node_memory_MemAvailable_bytes
```

## La dashboard chiave: "Pod Resources"

E' la dashboard che usi quando un collega ti chiede *"come faccio a sapere se 100m di CPU bastano?"*. Contiene:

- **CPU usage vs request vs limit**: linea piena = uso reale (rate del cAdvisor), linee tratteggiate = `requests.cpu` e `limits.cpu` configurati. Il confronto visivo dice subito se il pod e' sotto-dimensionato (linea sopra la request) o sovra-dimensionato (linea sotto e piatta).
- **Memoria working set vs request vs limit**: stessa logica, ma con `container_memory_working_set_bytes`. Il working set e' la memoria "viva" che NON puo' essere ricacciata su disco: e' la metrica che il kubelet usa per decidere gli OOMKill.
- **CPU throttling rate**: `container_cpu_cfs_throttled_periods_total / container_cpu_cfs_periods_total`. Se costantemente sopra il 25% il container e' strozzato dal `limits.cpu`. Soluzione: alza il limit, oppure toglilo (CPU e' compressibile).
- **OOM kills (24h)**: salta a > 0 se un container e' stato killato per superamento del `limits.memory`. Soluzione: alza il limit, oppure trova la perdita di memoria.
- **Pod sotto-dimensionati / sovra-dimensionati**: due tabelle che mostrano i candidati per cui ha senso ritoccare le request guardando il rapporto `usage / request`.

### Workflow tipico per scegliere requests e limits

1. Apri la dashboard `Pod Resources`, seleziona il `namespace` e il `pod` di interesse (template variables in alto).
2. Imposta il time range a **almeno 1 ora**, idealmente **24h o 7d** se i dati ci sono.
3. Guarda i grafici e annota il p95 dell'usage CPU e memoria. Le query corrispondenti sono in `queries.md` sezione *"Suggerimento request consigliata"*.
4. Applica la regola pratica:

```text
cpu.request    ~= p95(cpu_usage)
cpu.limit      = unset (oppure 2-3x request se l'app e' nota per essere rumorosa)
memory.request ~= p95(working_set) * 1.2
memory.limit   ~= memory.request * 1.5
```

5. Aggiorna il manifest, fai `kubectl apply`, aspetta e ri-osserva.

> **Perche' il `limits.cpu` di solito si lascia stare.** La CPU in Linux e' "compressibile": quando un pod ne chiede di piu' di quanto disponibile viene rallentato (throttling), non killato. Mettere un `limits.cpu` stretto e' utile solo per isolare workload "rumorosi", ma costa in latenza. Per workload normali, mettere solo la `request` e' la scelta pragmatica.
>
> **Perche' il `limits.memory` invece si mette quasi sempre.** La memoria non e' compressibile: se un container ne usa troppa il kubelet lo OOM-killa. Senza limit, un singolo bug di memoria puo' portare giu' un nodo intero.

## Esempio pratico: il demo-app e' sotto-dimensionato apposta

Il `demo-app` parte con `requests.cpu: 25m, limits.cpu: 100m`. Con il load generator a regime, dovresti vedere:

- *CPU usage* attorno a 30-60m, sopra la `request` ma sotto il `limit`
- *Throttling rate* basso ma occasionalmente > 0%
- la tabella *"Pod sotto-dimensionati"* lo elenca

Prova a:

```bash
# Alza CPU request a 60m e limit a 150m
kubectl -n monitoring patch deployment demo-app --type='strategic' -p \
'{"spec":{"template":{"spec":{"containers":[{"name":"app","resources":{"requests":{"cpu":"60m"},"limits":{"cpu":"150m"}}}]}}}}'
```

Aspetta 2-3 minuti e ricontrolla la dashboard: la linea `request` dovrebbe ora avvolgere la curva di usage e il throttling sparisce.

## Aggiungere una nuova app al monitoring

Per fare in modo che Prometheus scopra automaticamente una nuova app, basta che il Pod (o il Service) abbia tre annotation:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
```

Il `prometheus.yml` di questo lab ha gia' i job `kubernetes-pods` e `kubernetes-service-endpoints` che le riconoscono. Niente CRD, niente ServiceMonitor.

## Modificare il prometheus.yml

```bash
# 1. modifica labs/monitoring/11-prometheus-config.yaml
kubectl apply -f labs/monitoring/11-prometheus-config.yaml

# 2. ricarica la config a caldo (--web.enable-lifecycle e' acceso)
POD=$(kubectl -n monitoring get pod -l app=prometheus -o jsonpath='{.items[0].metadata.name}')
kubectl -n monitoring exec "$POD" -- wget -qO- --post-data='' http://localhost:9090/-/reload
```

## Aggiungere o modificare una dashboard Grafana

Le dashboard sono caricate dal file provider, NON tramite la API di Grafana. Quindi:

```bash
# 1. modifica o aggiungi un file in labs/monitoring/dashboards/*.json

# 2. ri-genera il ConfigMap (replace, cosi' i file rimossi spariscono)
kubectl -n monitoring create configmap grafana-dashboards \
  --from-file=labs/monitoring/dashboards/ \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. il provider rilegge ogni 30s. Se non vuoi aspettare:
kubectl -n monitoring rollout restart deploy/grafana
```

In alternativa puoi modificare la dashboard nella UI di Grafana, cliccare *Save -> JSON model -> Copy to clipboard* e incollarla nel file JSON corrispondente.

## Cosa NON c'e' (volutamente)

Per restare nel didattico, lo stack non include:

- **Alertmanager**: niente alerting via email/Slack/PagerDuty.
- **Prometheus Operator + ServiceMonitor**: il discovery e' fatto dal vecchio metodo annotation-based.
- **PV/PVC**: lo storage di Prometheus e Grafana e' `emptyDir`, perdi i dati al restart.
- **Ingress + TLS**: si accede solo via `port-forward`.
- **HPA / VPA**: non scaliamo automaticamente.
- **Loki/Tempo**: niente log e tracing.

## Versione "produzione": kube-prometheus-stack

Il chart `prometheus-community/kube-prometheus-stack` installa tutto quanto sopra (Operator, Prometheus + Alertmanager via CRD, Grafana con dashboard ufficiali pre-installate, ServiceMonitor/PodMonitor) in un colpo solo:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kps prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  --set grafana.adminPassword=admin \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false
```

In quello scenario, per fare scrape della tua app si usa un ServiceMonitor:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: demo-app
  namespace: monitoring
  labels:
    release: kps
spec:
  selector:
    matchLabels:
      app: demo-app
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
```

L'Operator vede il ServiceMonitor (filtrato per `release=kps`), lo traduce in scrape config, e ricarica Prometheus. Niente annotation, niente reload manuale.

## Cleanup

```bash
kubectl delete -f labs/monitoring/
kubectl delete configmap grafana-dashboards -n monitoring
kubectl delete namespace monitoring
```

Per rimuovere anche il cluster k3d:

```bash
k3d cluster delete monitoring
```

## Errori frequenti

- **Tutti i target `up=0` per `kubernetes-cadvisor` / `kubernetes-nodes`**: di solito e' un problema RBAC. Verifica `ClusterRoleBinding/prometheus` e che il pod usi `serviceAccountName: prometheus`. Su alcune distribuzioni (RKE, certi managed) il kubelet non e' raggiungibile via `apiserver/proxy`: in quel caso si usa `https://${IP}:10250` con `role: node` e `tls_config.insecure_skip_verify: true`.
- **`node-exporter` non parte su nodo**: spesso `hostPID/hostNetwork` sono bloccati da una PSP/PodSecurityAdmission. Su PSA "restricted" devi spostare il DS in un namespace con label `pod-security.kubernetes.io/enforce: privileged` o usare `baseline`.
- **Grafana mostra "No Data" sulle dashboard del lab**: aspetta 1-2 minuti il primo scrape, poi verifica che il datasource `Prometheus` punti a `http://prometheus.monitoring.svc.cluster.local:9090` e che dia OK al test.
- **Dashboard mancano dopo `kubectl apply -f`**: ricordati lo step 2 del setup (`kubectl create configmap grafana-dashboards --from-file=...`). I file JSON da soli non sono manifest Kubernetes.
- **Le query con `kube_pod_container_resource_requests` ritornano vuoto**: i pod scelti non hanno `resources.requests` impostate. Senza request, non c'e' nulla con cui confrontare l'usage. E' un problema reale: significa che il pod e' BestEffort e Kubernetes non puo' fare scheduling sensato.
- **`container_memory_working_set_bytes` mostra valori altissimi che includono pod-level somma**: filtra sempre con `container!=""` per escludere la metrica aggregata di pod e nodo, altrimenti ti ritrovi con il doppio.
