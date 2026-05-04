# Kustomize - esempio didattico completo

Questa directory mostra un esempio reale di Kustomize organizzato come `base` + `overlays` per due ambienti (`dev` e `prod`). Lo scopo e capire i meccanismi piu comuni in vista di CKA/CKAD e dell'uso quotidiano:

- `resources` per includere manifest e altre kustomization
- `labels` (e selectors) gestiti centralmente
- `namespace` e `namePrefix` per isolare gli ambienti
- `images` per override delle immagini senza toccare il Deployment
- `replicas` per scalare per ambiente
- `configMapGenerator` e `secretGenerator` con hash suffix automatico
- `patches` con strategic merge (SMP) e JSON 6902

## Struttura

```text
labs/kustomize/
├── README.md
├── namespaces.yaml
├── base/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── files/
│       ├── app.properties
│       └── index.html
└── overlays/
    ├── dev/
    │   ├── kustomization.yaml
    │   ├── patch-deployment.yaml
    │   └── files/
    │       ├── app.properties
    │       └── index.html
    └── prod/
        ├── kustomization.yaml
        ├── patch-resources.yaml
        ├── patch-spread.yaml
        └── files/
            ├── app.properties
            └── index.html
```

I `Namespace` non vivono dentro la kustomization, perche `namePrefix` li rinominerebbe. Sono in `namespaces.yaml`, applicato a parte.

## Cosa contiene la base

`base/kustomization.yaml` definisce i mattoni comuni:

```yaml
resources:
- deployment.yaml
- service.yaml

labels:
- includeSelectors: true
  pairs:
    app: portal
    part-of: training

configMapGenerator:
- name: portal-env
  envs:
  - files/app.properties
- name: portal-page
  files:
  - files/index.html
```

Cose da notare:

- `labels` con `includeSelectors: true` aggiunge le label sia su `metadata.labels`, sia sul `selector` del Deployment, sia sul `template.metadata.labels`. Equivalente moderno del vecchio `commonLabels`.
- Il `Deployment` referenzia la ConfigMap come `portal-env` (senza hash). Sara Kustomize a sostituire il riferimento col nome reale `<prefix>-portal-env-<hash>`.
- `configMapGenerator` con `envs:` legge un file in formato `KEY=VALUE` e crea le chiavi corrispondenti. Con `files:` invece la chiave nella ConfigMap e il nome del file.

## Overlay dev

Obiettivi:

- ambiente `portal-dev`, prefisso `dev-` su tutte le risorse
- 1 replica
- immagine `nginx:1.27-alpine`
- `app.properties` e `index.html` di sviluppo
- variabile `ENVIRONMENT=dev` aggiunta al container
- limiti di risorse piu bassi

```yaml
namespace: portal-dev
namePrefix: dev-

resources:
- ../../base

labels:
- includeSelectors: false
  pairs:
    environment: dev
    tier: nonprod

images:
- name: nginx
  newTag: "1.27-alpine"

replicas:
- name: portal
  count: 1

configMapGenerator:
- name: portal-env
  behavior: replace
  envs:
  - files/app.properties
- name: portal-page
  behavior: replace
  files:
  - files/index.html

patches:
- path: patch-deployment.yaml
  target:
    kind: Deployment
    name: portal
```

Punti chiave:

- `behavior: replace` riscrive completamente il contenuto della ConfigMap proveniente dal base. Le altre opzioni utili sono `merge` (unisce le chiavi) e `create` (crea nuove ConfigMap che non esistono nella base).
- `includeSelectors: false` aggiunge `environment: dev` e `tier: nonprod` solo come label informative, senza toccare il selector del Deployment (che resterebbe rotto al rolling update se cambiassi le label di selezione).
- `replicas` e `images` evitano di scrivere patch a mano.
- `target` nei `patches` permette di applicare lo stesso patch a piu risorse o di filtrare per kind/name.

Il file `patch-deployment.yaml` e un classico strategic merge:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: portal
spec:
  template:
    spec:
      containers:
      - name: portal
        env:
        - name: ENVIRONMENT
          value: dev
        resources:
          requests: {cpu: 25m, memory: 32Mi}
          limits:   {cpu: 100m, memory: 64Mi}
```

Kustomize unisce i container per `name`, quindi e fondamentale che `name: portal` corrisponda al container nel base.

## Overlay prod

Obiettivi:

- ambiente `portal-prod`, prefisso `prod-`
- 3 repliche
- immagine `nginx:1.27` con tag pinned
- `secretGenerator` per `API_TOKEN`
- `topologySpreadConstraints` aggiunto via JSON 6902
- strategia di rollout `maxUnavailable: 0`

```yaml
namespace: portal-prod
namePrefix: prod-

resources:
- ../../base

labels:
- includeSelectors: false
  pairs:
    environment: prod
    tier: prod

images:
- name: nginx
  newName: nginx
  newTag: "1.27"

replicas:
- name: portal
  count: 3

configMapGenerator:
- name: portal-env
  behavior: replace
  envs:
  - files/app.properties
- name: portal-page
  behavior: replace
  files:
  - files/index.html

secretGenerator:
- name: portal-secret
  literals:
  - API_TOKEN=prod-super-secret

patches:
- path: patch-resources.yaml
  target: {kind: Deployment, name: portal}
- path: patch-spread.yaml
  target: {kind: Deployment, name: portal}
```

`patch-resources.yaml` e SMP, alza le risorse e collega `API_TOKEN` al Secret generato:

```yaml
- name: API_TOKEN
  valueFrom:
    secretKeyRef:
      name: portal-secret
      key: API_TOKEN
```

Anche qui scrivi `portal-secret` senza hash: Kustomize sostituisce con `prod-portal-secret-<hash>` perche capisce che e un riferimento generato.

`patch-spread.yaml` e un patch JSON 6902 (RFC 6902). Si usa quando lo strategic merge non basta, per esempio per aggiungere campi a un array o creare strutture mancanti:

```yaml
- op: add
  path: /spec/template/spec/topologySpreadConstraints
  value:
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: ScheduleAnyway
    labelSelector:
      matchLabels:
        app: portal
- op: add
  path: /spec/strategy
  value:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
```

Operazioni supportate: `add`, `replace`, `remove`, `move`, `copy`, `test`.

## Comandi essenziali

Render senza applicare nulla:

```bash
kubectl kustomize labs/kustomize/base
kubectl kustomize labs/kustomize/overlays/dev
kubectl kustomize labs/kustomize/overlays/prod
```

Diff prima di applicare:

```bash
kubectl diff -k labs/kustomize/overlays/dev
```

Apply degli ambienti:

```bash
kubectl apply -f labs/kustomize/namespaces.yaml
kubectl apply -k labs/kustomize/overlays/dev
kubectl apply -k labs/kustomize/overlays/prod
```

Verifica:

```bash
kubectl get all -n portal-dev
kubectl get all -n portal-prod
kubectl get cm,secret -n portal-prod
kubectl describe deploy/prod-portal -n portal-prod
```

Testa il Service da un Pod temporaneo:

```bash
kubectl -n portal-dev run curl --image=curlimages/curl --restart=Never -it --rm -- \
  curl -s http://dev-portal/

kubectl -n portal-prod run curl --image=curlimages/curl --restart=Never -it --rm -- \
  curl -s http://prod-portal/
```

## Hash suffix e rolling update automatico

Le ConfigMap e Secret generate hanno un suffisso hash, per esempio `prod-portal-env-9k7mf48mc6`. Quando cambi `files/app.properties`, l'hash cambia, il nome cambia e Kustomize aggiorna i riferimenti dentro il Deployment. Kubernetes vede una modifica nel Pod template e fa partire un rolling update senza che tu debba toccare il Deployment a mano.

Per disattivarlo (sconsigliato in produzione):

```yaml
generatorOptions:
  disableNameSuffixHash: true
```

## Errori frequenti

- `image:` con tag numerico senza apici: `newTag: 1.27` viene letto come float, devi mettere `"1.27"`.
- Patch SMP che non trova il container: il `name` del container nel patch deve coincidere col base, altrimenti Kustomize aggiunge un nuovo container invece di unire.
- `namePrefix` applicato al `Namespace`: lo rinomina anche lui. Tieni i Namespace fuori dalla kustomization, oppure usa una `kustomizeconfig` per escluderli.
- ConfigMap riferita per nome senza hash quando `disableNameSuffixHash: false`: funziona solo se il nome compare in un campo riconosciuto (volumes/configMap, envFrom, valueFrom). In campi custom Kustomize non sa che e un riferimento.
- `labels` con `includeSelectors: true` su una risorsa gia in produzione: cambiare il selector di un Deployment esistente fa fallire il rollout. In quel caso usa `includeSelectors: false`.

## Cleanup

```bash
kubectl delete -k labs/kustomize/overlays/dev
kubectl delete -k labs/kustomize/overlays/prod
kubectl delete -f labs/kustomize/namespaces.yaml
```
