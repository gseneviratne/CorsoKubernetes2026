# Helm - esempio didattico completo

Questa directory contiene un chart Helm `portal` che impacchetta la stessa app dell'esempio Kustomize, ma usando il modello Helm: `Chart.yaml` + `values.yaml` + `templates/`. Vengono coperti i meccanismi che servono in CKA/CKAD e nel lavoro reale:

- struttura di un chart e file obbligatori
- `values.yaml` come fonte unica della configurazione
- override per ambiente con `-f values-<env>.yaml`
- helper / named templates in `_helpers.tpl`
- conditional rendering con `if`, `with`, `range`
- funzioni e pipeline (`default`, `quote`, `toYaml`, `nindent`, `required`, `tpl`)
- annotazioni `checksum/config` per rolling update automatico al cambio di config
- `helm.sh/hook` per i test del chart
- `NOTES.txt` per dare istruzioni post-install

## Struttura

```text
labs/helm/
├── README.md
├── envs/
│   ├── values-dev.yaml
│   └── values-prod.yaml
└── portal/
    ├── Chart.yaml
    ├── values.yaml
    ├── .helmignore
    └── templates/
        ├── _helpers.tpl
        ├── NOTES.txt
        ├── configmap.yaml
        ├── deployment.yaml
        ├── hpa.yaml
        ├── ingress.yaml
        ├── secret.yaml
        ├── service.yaml
        ├── serviceaccount.yaml
        └── tests/
            └── test-connection.yaml
```

I file di valori per ambiente sono volutamente fuori dal chart (`envs/`): cosi il chart resta riutilizzabile e i valori specifici di un'installazione sono tracciati separatamente, come si fa in un GitOps reale.

## Chart.yaml: i metadati

```yaml
apiVersion: v2          # Helm 3+
name: portal
type: application       # oppure "library"
version: 0.1.0          # versione del chart (SemVer)
appVersion: "1.27"      # versione dell'applicazione (stringa, va tra apici)
```

`version` cambia ad ogni modifica del chart, `appVersion` quando cambia l'app sottostante. Solo `version` viene usata da Helm per decidere upgrade/rollback.

## values.yaml: il contratto del chart

`values.yaml` definisce i valori di default e funge da documentazione. Ogni chiave qui presente puo essere sovrascritta da:

1. file di valori passati con `-f`
2. flag `--set` (ha priorita massima)

Strutturalmente abbiamo separato:

- `image`, `replicaCount`, `service`, `ingress`, `resources`, `autoscaling`: parametri infrastrutturali
- `config`: variabili applicative iniettate via `envFrom`
- `secret`: secret opzionale, controllato da `secret.enabled`
- `nodeSelector`, `tolerations`, `affinity`, `podAnnotations`, `env`: campi di tuning del Pod

## Helpers in `_helpers.tpl`

Sono template riutilizzabili invocati con `include`. I principali:

- `portal.name`: nome breve del chart, troncato a 63 caratteri (limite delle label).
- `portal.fullname`: nome univoco usato in `metadata.name`. Pattern standard: usa `release-chart`, ma se il release name contiene gia il chart name lo lascia cosi. E quello che permette di installare lo stesso chart con release diverse senza collisioni.
- `portal.labels`: tutte le label comuni (`helm.sh/chart`, `app.kubernetes.io/*`).
- `portal.selectorLabels`: il sottoinsieme che va nei selettori di Service e Deployment. Sono separate dalle altre proprio per evitare di toccare il selector quando aggiungi label informative (cambiare il selector di un Deployment e immutabile).
- `portal.serviceAccountName`: ritorna il nome del SA da usare, gestendo i casi `serviceAccount.create=false`.

In ogni template usi:

```yaml
metadata:
  name: {{ include "portal.fullname" . }}
  labels:
    {{- include "portal.labels" . | nindent 4 }}
```

`nindent N` aggiunge una newline e indenta di `N` spazi: serve perche `include` ritorna una stringa multilinea.

## Pattern usati nei template

### `default` per fallback

```yaml
image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
```

Se `image.tag` e vuoto in `values.yaml`, viene usato `appVersion` da `Chart.yaml`.

### `required` per valori obbligatori

```yaml
API_TOKEN: {{ required "secret.apiToken e obbligatorio quando secret.enabled e true" .Values.secret.apiToken | quote }}
```

Se manca, `helm install` fallisce con il messaggio dato.

### `with` per accorciare contesti opzionali

```yaml
{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 8 }}
{{- end }}
```

Il blocco viene reso solo se `.Values.nodeSelector` e non vuoto. Dentro, `.` e il valore stesso.

### `if` per intere risorse opzionali

`secret.yaml`, `hpa.yaml`, `ingress.yaml` e `serviceaccount.yaml` sono interamente avvolti in `{{- if ... -}} ... {{- end }}`. Quando la feature e disabilitata, il file non produce output e Helm non crea la risorsa.

### `range` con `$` per accedere al contesto root

In `ingress.yaml` ci sono due `range` annidati. All'interno il `.` cambia: per tornare al contesto root (per accedere a `.Values.service.port`) si usa `$`:

```yaml
{{- range .Values.ingress.hosts }}
- host: {{ .host | quote }}
  http:
    paths:
    {{- range .paths }}
    - path: {{ .path }}
      backend:
        service:
          name: {{ include "portal.fullname" $ }}
          port:
            number: {{ $.Values.service.port }}
    {{- end }}
{{- end }}
```

### `checksum/config` per rolling update automatici

```yaml
template:
  metadata:
    annotations:
      checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

L'hash della ConfigMap renderizzata viene messo come annotation del Pod template. Quando cambi `values.config.*`, l'hash cambia, il Pod template cambia, Kubernetes fa partire un rolling update. Stessa cosa per il Secret quando abilitato.

E l'equivalente Helm del nome con hash che fa Kustomize via `configMapGenerator`.

## Override per ambiente

`envs/values-dev.yaml`:

```yaml
replicaCount: 1
image: { tag: "1.27-alpine" }
config:
  appMode: dev
  logLevel: debug
  featureFlags: experimental
ingress: { enabled: true, hosts: [{ host: dev.portal.local, paths: [{ path: /, pathType: Prefix }] }] }
```

`envs/values-prod.yaml`:

```yaml
replicaCount: 3
image: { tag: "1.27" }
config:
  appMode: prod
  logLevel: warn
  featureFlags: stable
secret: { enabled: true, apiToken: "prod-super-secret" }
autoscaling: { enabled: true, minReplicas: 3, maxReplicas: 10, targetCPUUtilizationPercentage: 70 }
ingress:
  enabled: true
  className: nginx
  hosts: [{ host: portal.example.com, paths: [{ path: /, pathType: Prefix }] }]
```

In `prod` accendiamo `secret`, `autoscaling` e `ingress.className`. Il template del Deployment elimina il campo `replicas` quando `autoscaling.enabled=true`, lasciando il controllo all'HPA.

## Comandi essenziali

### Render senza toccare il cluster

```bash
helm lint labs/helm/portal
helm template portal labs/helm/portal -f labs/helm/envs/values-dev.yaml -n portal-dev
helm template portal labs/helm/portal -f labs/helm/envs/values-prod.yaml -n portal-prod
```

### Install dry-run con validazione lato server

```bash
kubectl create ns portal-dev
helm install portal labs/helm/portal \
  -f labs/helm/envs/values-dev.yaml \
  -n portal-dev \
  --dry-run=server --debug
```

### Install per davvero

```bash
helm install portal labs/helm/portal \
  -f labs/helm/envs/values-dev.yaml \
  -n portal-dev --create-namespace

helm install portal labs/helm/portal \
  -f labs/helm/envs/values-prod.yaml \
  -n portal-prod --create-namespace
```

### Override puntuale

```bash
helm install portal labs/helm/portal \
  -f labs/helm/envs/values-dev.yaml \
  --set replicaCount=2 \
  --set image.tag=1.27 \
  -n portal-dev --create-namespace
```

### Upgrade, status, history, rollback

```bash
helm upgrade portal labs/helm/portal \
  -f labs/helm/envs/values-prod.yaml \
  -n portal-prod

helm status portal -n portal-prod
helm history portal -n portal-prod
helm rollback portal 1 -n portal-prod
```

`helm upgrade --install` (alias `-i`) e idempotente: installa se non esiste, aggiorna se esiste. Pattern tipico nelle pipeline CI.

```bash
helm upgrade --install portal labs/helm/portal \
  -f labs/helm/envs/values-prod.yaml \
  -n portal-prod --create-namespace
```

### Test del chart

```bash
helm test portal -n portal-prod
```

Esegue il Pod definito in `templates/tests/test-connection.yaml` (annotato con `helm.sh/hook: test`) e mostra esito e log. Utile in pipeline di rilascio.

### Vedere i valori effettivi dopo l'install

```bash
helm get values portal -n portal-prod
helm get values portal -n portal-prod --all     # con i default
helm get manifest portal -n portal-prod         # YAML applicato
helm get notes portal -n portal-prod            # le NOTES.txt
```

### Uninstall

```bash
helm uninstall portal -n portal-dev
helm uninstall portal -n portal-prod
kubectl delete ns portal-dev portal-prod
```

## Errori frequenti

- `appVersion: 1.27` senza apici viene letto come float. Mettere sempre `"1.27"` in `Chart.yaml` e in `image.tag`.
- Dimenticare `nindent` su `include`: l'output finisce attaccato alla riga sbagliata e il YAML diventa invalido. Regola pratica: ogni volta che `include` produce piu di una riga, usa `| nindent N`.
- Cambiare `selectorLabels` dopo il primo install: il selector di Deployment e immutabile, l'upgrade fallisce. Aggiungi label informative solo in `portal.labels`, non in `portal.selectorLabels`.
- `helm template` funziona ma `helm install` fallisce: succede quando i template generano YAML valido ma non passano la validazione di Kubernetes (campi obbligatori mancanti, riferimenti a risorse non esistenti). Usa `helm install --dry-run=server` per fare la validazione lato API.
- `--set` con liste e mappe complesse: meglio scrivere un file di valori e passarlo con `-f`. Per liste si usa la sintassi `--set 'env[0].name=FOO,env[0].value=bar'`, fragile.
- Reinstallare dopo un fallito install: usa `helm uninstall <release>` prima, oppure `helm install --replace`. In Helm 3 le release fallite restano nel cluster.

## Confronto rapido con Kustomize

| Feature | Kustomize | Helm |
|---|---|---|
| Variabili | no, solo patch e generators | si, `values.yaml` |
| Template engine | no (dichiarativo puro) | si (Go template + Sprig) |
| Override per ambiente | overlays | file `-f values-env.yaml` |
| Riferimenti a configmap/secret aggiornati | name suffix hash | annotation `checksum/config` |
| Conditional rendering | difficile | nativo (`if`, `with`) |
| Versionamento e rollback | esterno (git, argo) | nativo (`helm history/rollback`) |
| Curva di apprendimento | bassa | media |
