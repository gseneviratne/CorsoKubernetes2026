## Lab: Troubleshooting Helm

Questo laboratorio simula quattro errori classici che si incontrano scrivendo o usando un chart Helm. Ogni bug si manifesta a uno stadio diverso della pipeline (`helm lint`, `helm template`, `helm install --dry-run=server`, post-install)

### Prerequisito

Cluster Kubernetes attivo e Helm 3 installato:

```bash
kubectl cluster-info
helm version
```

### Obiettivo

- Riconoscere i tipici errori Helm e capire a quale stadio vengono intercettati
- Usare `helm lint`, `helm template`, `helm install --dry-run=server` come passi successivi di verifica
- Correggere `Chart.yaml`, `values.yaml` e i template per portare il chart a installazione pulita e funzionante

### Struttura del lab

```text
labs/helm-troubleshooting/
├── README.md
├── envs/
│   └── values-dev.yaml
├── webapp/                 # chart volutamente rotto
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── .helmignore
│   └── templates/
│       ├── _helpers.tpl
│       ├── NOTES.txt
│       ├── configmap.yaml
│       ├── deployment.yaml
│       └── service.yaml
└── solution/               # versione corretta di tutto cio che sta sopra
    ├── envs/
    │   └── values-dev.yaml
    └── webapp/
        ├── Chart.yaml
        ├── values.yaml
        ├── .helmignore
        └── templates/...
```

### Sintomi attesi (in ordine di apparizione)

Lavorando dall'alto al basso della pipeline, scoprirai i bug uno alla volta:

1. `helm lint` segnala un problema sul `Chart.yaml`
2. `helm template` fallisce con un messaggio chiaro su un valore mancante
3. `helm install --dry-run=server` fallisce con un errore dell'API server
4. L'install riesce ma il Service non risponde (`kubectl get endpoints` vuoto)

### Passo 1 - lint del chart

```bash
helm lint labs/helm-troubleshooting/webapp
```

Atteso (BUG A):

```text
[ERROR] Chart.yaml: version should be of type string but it's of type float64
[WARNING] Chart.yaml: version '0.1' is not a valid SemVerV2
Error: 1 chart(s) linted, 1 chart(s) failed
```

Hint: la versione del chart deve seguire SemVer completo `MAJOR.MINOR.PATCH` ed essere una stringa. Modifica `Chart.yaml`.

### Passo 2 - render senza cluster

```bash
helm template demo labs/helm-troubleshooting/webapp \
  -f labs/helm-troubleshooting/envs/values-dev.yaml \
  -n webapp-dev
```

Atteso (BUG C):

```text
Error: execution error at (webapp/templates/deployment.yaml:19:28): values.yaml: config.appMode e obbligatorio
```

Nota: l'errore e tracciato sulla riga del Deployment perche il `checksum/config` calcola l'hash della ConfigMap renderizzata, e quel render attiva la funzione `required` definita in `configmap.yaml`. La causa vera e nella ConfigMap.

Hint: la funzione `required` blocca il render se il valore e nil o vuoto. O aggiungi un default in `values.yaml`, o passi il valore via `-f` o `--set config.appMode=dev`.

### Passo 3 - dry-run server-side

Una volta che `helm template` produce YAML pulito, valida lato API server:

```bash
kubectl create namespace webapp-dev
helm install demo labs/helm-troubleshooting/webapp \
  -f labs/helm-troubleshooting/envs/values-dev.yaml \
  -n webapp-dev \
  --dry-run=server --debug
```

Atteso (BUG B):

```text
Error: ... Deployment.apps "demo-webapp" is invalid:
spec.template.metadata.labels: Invalid value: ...
`selector` does not match template `labels`
```

Hint: `spec.selector.matchLabels` di un Deployment deve corrispondere alle label del Pod template. Usa lo stesso helper (`webapp.selectorLabels`) in entrambi i punti.

### Passo 4 - install reale e verifica del Service

Ora l'install passa:

```bash
helm install demo labs/helm-troubleshooting/webapp \
  -f labs/helm-troubleshooting/envs/values-dev.yaml \
  -n webapp-dev --create-namespace
```

I Pod partono `Running`, ma il Service non risponde:

```bash
kubectl -n webapp-dev get pods
kubectl -n webapp-dev get svc demo-webapp
kubectl -n webapp-dev get endpoints demo-webapp
kubectl -n webapp-dev port-forward svc/demo-webapp 8080:80 &
curl -m 3 http://localhost:8080 ; echo
```

Atteso (BUG D): la riga `endpoints` riporta `<none>` e `curl` va in timeout o ritorna errore.

Hint: il `selector` del `Service` non corrisponde alle label del Pod. Stesso principio del Deployment: usa `include "webapp.selectorLabels" .` anche nel Service.

### Comandi utili durante il troubleshooting

```bash
# Lint del chart
helm lint labs/helm-troubleshooting/webapp

# Render dei template senza cluster (utile per ispezionare YAML generato)
helm template demo labs/helm-troubleshooting/webapp \
  -f labs/helm-troubleshooting/envs/values-dev.yaml --debug

# Validazione lato API server
helm install demo labs/helm-troubleshooting/webapp \
  -f labs/helm-troubleshooting/envs/values-dev.yaml \
  -n webapp-dev --dry-run=server --debug

# Stato di una release
helm status demo -n webapp-dev
helm get manifest demo -n webapp-dev
helm get values demo -n webapp-dev --all

# Endpoint di un Service e label dei Pod
kubectl -n webapp-dev get endpoints demo-webapp -o yaml
kubectl -n webapp-dev get pod -l app.kubernetes.io/name=webapp --show-labels
kubectl -n webapp-dev describe svc demo-webapp
```

### Verifica finale

Dopo le correzioni, il flusso completo deve passare senza errori:

```bash
helm lint labs/helm-troubleshooting/webapp
helm template demo labs/helm-troubleshooting/webapp \
  -f labs/helm-troubleshooting/envs/values-dev.yaml -n webapp-dev > /dev/null
helm upgrade --install demo labs/helm-troubleshooting/webapp \
  -f labs/helm-troubleshooting/envs/values-dev.yaml \
  -n webapp-dev --create-namespace

kubectl -n webapp-dev rollout status deploy/demo-webapp
kubectl -n webapp-dev get endpoints demo-webapp
kubectl -n webapp-dev port-forward svc/demo-webapp 8080:80 &
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080
```

L'output finale deve essere `200` e gli endpoints non devono essere vuoti.

### Soluzione

Il chart corretto e i value file fixati sono in:

```bash
labs/helm-troubleshooting/solution/
```

Confronto rapido con `diff`:

```bash
diff -ru labs/helm-troubleshooting/webapp labs/helm-troubleshooting/solution/webapp
diff -ru labs/helm-troubleshooting/envs   labs/helm-troubleshooting/solution/envs
```

Per provare direttamente la versione corretta:

```bash
helm upgrade --install demo labs/helm-troubleshooting/solution/webapp \
  -f labs/helm-troubleshooting/solution/envs/values-dev.yaml \
  -n webapp-dev --create-namespace
```

### Riepilogo dei bug

| Bug | File | Sintomo | Strumento che lo intercetta |
|---|---|---|---|
| A | `webapp/Chart.yaml` | `version: 0.1` non e SemVer | `helm lint` |
| C | `webapp/values.yaml` + `templates/configmap.yaml` | `required` su `config.appMode` con valore mancante | `helm template` |
| B | `webapp/templates/deployment.yaml` | `selector.matchLabels` diverso dalle label del Pod template | `helm install --dry-run=server` |
| D | `webapp/templates/service.yaml` | Service `selector` hardcoded che non matcha i Pod | post-install (`endpoints` vuoti) |

### Lezione da portare a casa

I controlli vanno fatti in cascata, dal piu economico al piu costoso:

1. `helm lint` per metadati e struttura del chart
2. `helm template` per il rendering Go-template e i `required`
3. `helm install --dry-run=server` per la validazione lato API server (schema OpenAPI, immutabilita, ammissione)
4. `kubectl get endpoints` e i log dei Pod per la correttezza funzionale

I primi tre passi non toccano lo stato del cluster e sono perfetti in pipeline CI prima di un deploy.

### Cleanup

```bash
helm uninstall demo -n webapp-dev
kubectl delete namespace webapp-dev
```
