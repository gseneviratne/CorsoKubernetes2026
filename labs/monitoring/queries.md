# PromQL - cheatsheet del lab monitoring

Questa raccolta di query e' organizzata per scenario d'uso: ognuna e' pensata per essere lanciata in **Prometheus -> Graph** o per riuscire a leggere le dashboard Grafana di questo lab.

Convenzioni:

- `$__rate_interval` e' una variabile di Grafana. Se lanci la query in Prometheus diretto, sostituisci con `[5m]`.
- `container!=""` esclude le metriche cgroup di livello "pod" (somma di tutti i container) per evitare doppio conteggio quando aggreghi.
- Le metriche `container_*` arrivano da **cAdvisor** (kubelet). Le `kube_*` da **kube-state-metrics**. Le `node_*` da **node-exporter**.

## Verificare che Prometheus stia raccogliendo

```promql
# Quanti target sta facendo scrape, divisi per stato
count by (job) (up == 1)

# Target down
up == 0

# Quanto e' in ritardo lo scrape rispetto allo schedule
scrape_duration_seconds
```

## Cluster e nodi (da node-exporter)

```promql
# CPU usata (in core) sul cluster, ultimi 5 minuti
sum(rate(node_cpu_seconds_total{mode!="idle"}[5m]))

# CPU usage % sul cluster
100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])))

# CPU per nodo
100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])))

# Memoria usata sul cluster
sum(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes)

# Memoria % per nodo
100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)

# Disco rootfs % per nodo
100 * (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})

# Network: bytes in / out per nodo
rate(node_network_receive_bytes_total{device!~"lo|veth.*|docker.*|cni.*"}[5m])
rate(node_network_transmit_bytes_total{device!~"lo|veth.*|docker.*|cni.*"}[5m])

# Load 1 minuto vs core disponibili
node_load1 / count by (instance) (node_cpu_seconds_total{mode="idle"})
```

## Inventario del cluster (da kube-state-metrics)

```promql
# Numero di nodi
count(kube_node_info)

# Pod per fase
sum by (phase) (kube_pod_status_phase)

# Pod NOT Ready
kube_pod_status_ready{condition="true"} == 0

# Pod in CrashLoopBackOff
kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"} == 1

# Restart totali per pod nelle ultime 24h
sum by (namespace, pod) (increase(kube_pod_container_status_restarts_total[24h]))

# Deployment con replica desiderate != pronte
kube_deployment_status_replicas != kube_deployment_status_replicas_ready

# Pod schedulati per nodo
sum by (node) (kube_pod_info)

# Servizi LoadBalancer pendenti (ip non assegnato)
kube_service_status_load_balancer_ingress unless on (namespace, service) kube_service_spec_type{type="LoadBalancer"}
```

## Pod - CPU (da cAdvisor)

```promql
# CPU usata da un pod (in core)
sum by (namespace, pod) (
  rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m])
)

# Top 10 pod per CPU
topk(10, sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{container!=""}[5m])))

# CPU per container dentro un pod
sum by (namespace, pod, container) (rate(container_cpu_usage_seconds_total{container!=""}[5m]))

# CPU throttling: % di tempo in cui il container e' stato strozzato dal limit
sum by (namespace, pod) (rate(container_cpu_cfs_throttled_periods_total[5m]))
  /
sum by (namespace, pod) (rate(container_cpu_cfs_periods_total[5m]))

# CPU usage / CPU request
sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{container!=""}[5m]))
  /
sum by (namespace, pod) (kube_pod_container_resource_requests{resource="cpu"} > 0)

# CPU usage / CPU limit (>1 e' impossibile, ma vicino a 1 = throttling probabile)
sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{container!=""}[5m]))
  /
sum by (namespace, pod) (kube_pod_container_resource_limits{resource="cpu"} > 0)
```

## Pod - memoria (da cAdvisor)

```promql
# Memoria "viva" di un pod (working set: e' quella che conta per OOM)
sum by (namespace, pod) (container_memory_working_set_bytes{container!=""})

# Top 10 pod per memoria
topk(10, sum by (namespace, pod) (container_memory_working_set_bytes{container!=""}))

# RSS (memoria fisica privata) - alternativa a working set
sum by (namespace, pod) (container_memory_rss{container!=""})

# Cache (riclamabile, NON conta per OOM)
sum by (namespace, pod) (container_memory_cache{container!=""})

# Memoria usage / request
sum by (namespace, pod) (container_memory_working_set_bytes{container!=""})
  /
sum by (namespace, pod) (kube_pod_container_resource_requests{resource="memory"} > 0)

# Memoria usage / limit. Quando si avvicina a 1 -> rischio OOMKill
sum by (namespace, pod) (container_memory_working_set_bytes{container!=""})
  /
sum by (namespace, pod) (kube_pod_container_resource_limits{resource="memory"} > 0)

# OOM kills nelle ultime 24h
sum(increase(kube_pod_container_status_last_terminated_reason{reason="OOMKilled"}[24h]))
```

## Sizing di requests e limits - le query "decisionali"

Sono le query che usi per decidere se alzare/abbassare i valori in `resources:` di un Deployment. Lanciale su finestre lunghe (1d, 7d) per non farti ingannare da picchi temporanei.

### Trovare i sotto-dimensionati (alzare la request)

```promql
# CPU: usage > 80% della request, sostenuto su 1 ora
(
  sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{container!=""}[1h]))
  /
  sum by (namespace, pod) (kube_pod_container_resource_requests{resource="cpu"} > 0)
) > 0.8

# Memoria: working set > 80% della request
(
  sum by (namespace, pod) (container_memory_working_set_bytes{container!=""})
  /
  sum by (namespace, pod) (kube_pod_container_resource_requests{resource="memory"} > 0)
) > 0.8
```

### Trovare i sovra-dimensionati (abbassare la request, recuperare capacita')

```promql
# CPU: media usage molto sotto la request da almeno 1 ora
(
  avg_over_time(
    (sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{container!=""}[5m])))[1h:5m]
  )
  /
  sum by (namespace, pod) (kube_pod_container_resource_requests{resource="cpu"} > 0)
) < 0.2

# Memoria: working set sotto il 30% della request
(
  sum by (namespace, pod) (container_memory_working_set_bytes{container!=""})
  /
  sum by (namespace, pod) (kube_pod_container_resource_requests{resource="memory"} > 0)
) < 0.3
```

### Trovare i CPU-throttled (alzare il limit, o toglierlo)

```promql
# % di CPU period throttled
sum by (namespace, pod) (rate(container_cpu_cfs_throttled_periods_total[5m]))
  /
sum by (namespace, pod) (rate(container_cpu_cfs_periods_total[5m])) > 0.25
```

### Suggerimento "request consigliata" (95-percentile)

Una regola pratica: la **request** dovrebbe coprire il p95 dell'uso reale, il **limit** lascia un po' di headroom (1.5x o 2x) o resta non impostato per la CPU.

```promql
# p95 della CPU usage di un pod sull'ultima settimana, in core
quantile_over_time(0.95,
  sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{container!=""}[5m]))
[7d:5m])

# p95 della memoria working set sull'ultima settimana
quantile_over_time(0.95,
  sum by (namespace, pod) (container_memory_working_set_bytes{container!=""})
[7d:5m])
```

Confronta questi valori con la `request` corrente per decidere il nuovo valore. Per un workload tipo, la formula che funziona quasi sempre:

```text
cpu.request    ~= p95(cpu_usage)        (oppure media + 2 * stdev)
cpu.limit      = unset (o 2-3x request, solo per applicazioni "rumorose")
memory.request ~= p95(working_set) * 1.2
memory.limit   ~= memory.request * 1.5
```

## Capacity planning del cluster

```promql
# CPU richiesto da tutti i pod / CPU del cluster (overcommit factor)
sum(kube_pod_container_resource_requests{resource="cpu"})
  /
sum(kube_node_status_allocatable{resource="cpu"})

# Memoria richiesta / memoria allocabile
sum(kube_pod_container_resource_requests{resource="memory"})
  /
sum(kube_node_status_allocatable{resource="memory"})

# Quanti pod possono ancora schedulare in media (heuristica grossolana)
floor(
  sum(kube_node_status_allocatable{resource="pods"})
  - sum(kube_pod_info{node!=""})
)

# CPU "sprecata": somma di (request - usage) sui pod
sum(kube_pod_container_resource_requests{resource="cpu"})
  -
sum(rate(container_cpu_usage_seconds_total{container!=""}[5m]))
```

## Rete e errori applicativi (dal demo-app)

Le metriche `http_requests_total` e `http_request_duration_seconds_*` sono esposte dal pod demo-app e raccolte via annotation `prometheus.io/scrape: "true"`.

```promql
# RPS totali
sum(rate(http_requests_total[1m]))

# RPS per status code
sum by (status) (rate(http_requests_total[1m]))

# Error rate (% di 5xx sul totale)
sum(rate(http_requests_total{status=~"5.."}[5m]))
  /
sum(rate(http_requests_total[5m]))

# Latenza p95 dalle histogram bucket
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# Apdex (T = 0.3s): quante richieste sotto la soglia di "soddisfatto"
(
  sum(rate(http_request_duration_seconds_bucket{le="0.3"}[5m]))
  +
  sum(rate(http_request_duration_seconds_bucket{le="1.2"}[5m]))
) / 2 / sum(rate(http_request_duration_seconds_count[5m]))
```

## Trucchi PromQL utili

```promql
# Differenza fra due metriche con label diverse: usa "on()" o "ignoring()"
sum by (pod) (container_memory_working_set_bytes{container!=""})
  / on (pod) group_left
sum by (pod) (kube_pod_container_resource_requests{resource="memory"})

# vector(0) come fallback quando una serie potrebbe non esistere
sum(rate(http_requests_total{status=~"5.."}[5m])) or vector(0)

# Top N
topk(5, sum by (namespace, pod) (container_memory_working_set_bytes))

# Bottom N (escludendo gli zero)
bottomk(5, sum by (namespace, pod) (container_memory_working_set_bytes) > 0)

# Differenza fra due istanti (delta)
delta(node_filesystem_avail_bytes{mountpoint="/"}[1h])

# Cambio in percentuale
(metric - metric offset 1h) / metric offset 1h * 100
```
