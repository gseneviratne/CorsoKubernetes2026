# Lab: CRD + Operator in Kubernetes

Laboratorio didattico in tre parti, pensato per essere fatto in classe in
sequenza. Alla fine avrai:

1. **Parte 1 — La CRD base**: capisci cos'e' una `CustomResourceDefinition`,
   come la registri e quali sono i suoi limiti operativi.
2. **Parte 2 — La CRD "professionale"**: schema OpenAPI per la validazione,
   `status` come subresource, printer columns, short names.
3. **Parte 3 — L'operator**: scrivi un controller (in Python con `kopf`)
   che osserva le CR `WebApp` e crea automaticamente Deployment + Service.
   Verifichi update, scale, e cancellazione via garbage collection.

L'esempio scelto e' una CRD `WebApp` perche' rappresenta un caso introduttivo
chiaro: ogni studente capisce cosa significa "esporre un'app web" e la
logica di riconciliazione resta immediata da seguire.

> Per andare oltre questo lab, gli stessi concetti si applicano a operator
> di produzione scritti in Go con [kubebuilder](https://book.kubebuilder.io/) o
> [operator-sdk](https://sdk.operatorframework.io/). Il loop di
> reconciliation pero' e' identico a quello di `kopf`: osserva il mondo,
> calcola lo stato desiderato, riconcilia. Vedi sezione finale.

---

## Prerequisiti

- Un cluster Kubernetes >= 1.27 raggiungibile (`kubectl cluster-info`).
  k3d/kind/minikube/k3s sono opzioni adeguate.
- I nodi devono poter raggiungere `pypi.org` (al primo avvio l'operator
  installa `kopf` e `kubernetes` via `pip`). Se sei in un ambiente
  air-gapped costruisci l'immagine con il `Dockerfile` fornito e usala
  al posto di `python:3.12-slim` nel Deployment.
- Familiarita' con `kubectl`, Deployment, Service, ConfigMap, RBAC.

```bash
# Esempio cluster k3d:
k3d cluster create operator-lab --agents 1
kubectl cluster-info
```

---

## Struttura del lab

```text
labs/operator-lab/
├── README.md                       # questo file
├── 00-namespace.yaml               # namespace operator-lab
├── 10-crd-minimal.yaml             # Parte 1: CRD senza schema
├── 11-cr-minimal.yaml              # Parte 1: una WebApp di esempio
├── 20-crd-v1.yaml                  # Parte 2: CRD con schema, status, printer cols
├── 21-cr-invalid.yaml              # Parte 2: CR che VIOLA lo schema
├── 22-cr-valid.yaml                # Parte 2: CR conforme allo schema
├── 30-operator-rbac.yaml           # Parte 3: SA + ClusterRole + Bindings
├── 31-operator-deploy.yaml         # Parte 3: Deployment dell'operator
├── 40-webapp-sample.yaml           # Parte 3: prima WebApp gestita
├── 41-webapp-scaled.yaml           # Parte 3: WebApp aggiornata a 3 repliche
├── 42-webapp-second.yaml           # Parte 3: una seconda WebApp indipendente
└── operator/
    ├── main.py                     # codice dell'operator (~80 righe)
    ├── requirements.txt            # kopf + kubernetes client
    └── Dockerfile                  # opzionale, per buildare un'immagine "vera"
```

---

# Parte 1 — La CRD base

Obiettivo: capire che una CRD, da sola, e' solo una **definizione di tipo**
per l'API server. Niente comportamento.

## Passo 1.1 — Crea il namespace e applica la CRD minima

```bash
kubectl apply -f labs/operator-lab/00-namespace.yaml
kubectl apply -f labs/operator-lab/10-crd-minimal.yaml
```

Verifica:

```bash
kubectl get crd webapps.training.example.com
kubectl api-resources | grep webapps
```

Output atteso (forma):

```text
NAME              SHORTNAMES   APIVERSION                            NAMESPACED   KIND
webapps           wa           training.example.com/v1alpha1         true         WebApp
```

Da questo momento il cluster sa che esiste un tipo `WebApp`, esattamente
come sa che esiste `Deployment`. `kubectl get webapps -A` funziona, anche
se per ora ritorna vuoto.

## Passo 1.2 — Crea una WebApp e osserva il comportamento iniziale

```bash
kubectl apply -f labs/operator-lab/11-cr-minimal.yaml
kubectl get webapps -n operator-lab
kubectl get wa -n operator-lab           # short name
kubectl get webapp hello-world -n operator-lab -o yaml
```

L'oggetto e' nel cluster (in etcd), `kubectl get` lo elenca, ma:

```bash
kubectl get deploy,svc,pod -n operator-lab
```

...non ci sono Deployment, ne' Service, ne' Pod. **La CRD non ha
comportamento**: e' solo "una nuova tabella nel database K8s". Per farci
qualcosa serve un controller che la osservi.

## Passo 1.3 — La validazione "permissiva"

Apri `labs/operator-lab/11-cr-minimal.yaml`: noterai un campo
`qualcosaDiCasuale` completamente inventato. La CRD lo ha accettato
perche' nello schema c'e':

```yaml
x-kubernetes-preserve-unknown-fields: true
```

E' la posizione "non validare, accetta qualunque YAML". Utile per
prototipare, **inaccettabile** in qualunque CRD seria. Vediamo perche'
nella Parte 2.

---

# Parte 2 — La CRD "professionale"

Obiettivo: aggiungere validazione, separare lo `status`, migliorare la UX
con printer columns.

## Passo 2.1 — Aggiorna la CRD alla versione "v1"

```bash
kubectl apply -f labs/operator-lab/20-crd-v1.yaml
```

Verifica che sia lo stesso `webapps.training.example.com` ma adesso con
schema reale:

```bash
kubectl explain webapp.spec
kubectl explain webapp.spec.replicas
kubectl explain webapp.status
```

Ti aspetti di vedere finalmente un help "tipato": `replicas` e' un intero
con `minimum: 1, maximum: 10`, `image` e' una `string` obbligatoria, ecc.

## Passo 2.2 — Prova a creare una CR invalida

```bash
kubectl apply -f labs/operator-lab/21-cr-invalid.yaml
```

Output atteso (errore HTTP 422 dall'API server):

```text
The WebApp "webapp-broken" is invalid:
* spec.image: Required value
* spec.replicas: Invalid value: 99: spec.replicas in body should be
  less than or equal to 10
* spec.port: Invalid value: 99999: spec.port in body should be less
  than or equal to 65535
```

**Punto chiave**: questa validazione avviene PRIMA di scrivere su etcd.
Il controller non vedra' mai questa risorsa. Lo schema e' la tua prima
linea di difesa, anche prima di Kyverno o di un admission webhook.

## Passo 2.3 — Crea una CR valida

```bash
kubectl apply -f labs/operator-lab/22-cr-valid.yaml
kubectl get webapps -n operator-lab
```

Adesso `kubectl get` mostra le **printer columns** che hai dichiarato
nella CRD:

```text
NAME         IMAGE         REPLICAS   PHASE     URL    AGE
ciao-mondo   nginx:1.27    2                           5s
```

`PHASE` e `URL` sono vuoti perche' nessuno aggiorna ancora lo
`status`: e' compito dell'operator, che installiamo nel prossimo passaggio.

## Passo 2.4 — La status subresource

Verifica che `kubectl edit` non ti permetta di modificare lo status
"manualmente" come parte della spec:

```bash
kubectl edit webapp ciao-mondo -n operator-lab
# prova a mettere a mano:
#   status:
#     phase: Running
# salva e esci. Riapri e vedrai che il campo e' SCOMPARSO.
```

E' il comportamento della subresource `/status`: il client che fa
PATCH/PUT su `/webapps/<n>` puo' toccare solo la spec; lo status si scrive
SOLO via `PATCH /webapps/<n>/status`, e questo richiede un permesso RBAC
distinto. E' la separazione "spec=stato desiderato, status=stato osservato
del controller".

---

# Parte 3 — L'operator

Obiettivo: dare un comportamento alla CRD. Faremo un operator che, per
ogni `WebApp`, mantiene:

- un Deployment con `spec.replicas` repliche dell'immagine `spec.image`
- un Service ClusterIP che la espone su `spec.port`
- lo `status` della WebApp aggiornato (phase, url, deploymentName, ecc.)
- alla cancellazione della WebApp, le risorse owned spariscono via
  garbage collection di K8s (grazie alle ownerReferences).

Il sorgente e' in `operator/main.py`, ~80 righe Python con
[kopf](https://kopf.readthedocs.io/). Leggilo prima di andare avanti, e'
volutamente brevissimo.

## Passo 3.1 — Applica RBAC

```bash
kubectl apply -f labs/operator-lab/30-operator-rbac.yaml
```

Verifica:

```bash
kubectl get sa,role,rolebinding,clusterrole,clusterrolebinding \
  -l '!app.kubernetes.io/managed-by' -n operator-lab 2>/dev/null
kubectl get clusterrole webapp-operator -o yaml | head -40
```

I permessi essenziali sono spiegati nei commenti del file: la regola
"chiave" e' `webapps/status` con `verbs: [update, patch]`, perche' senza
quella l'operator non puo' aggiornare la subresource.

## Passo 3.2 — Carica il sorgente in una ConfigMap

L'operator vive in un Pod che monta il sorgente come volume. Crea la
ConfigMap a partire dai file in `operator/`:

```bash
kubectl -n operator-lab create configmap webapp-operator-code \
  --from-file=labs/operator-lab/operator/main.py \
  --from-file=labs/operator-lab/operator/requirements.txt
```

> Stesso pattern del lab `monitoring/` con le dashboard Grafana: i file
> sorgente vivono nel repo, una `ConfigMap` li monta nel Pod.

## Passo 3.3 — Avvia l'operator

```bash
kubectl apply -f labs/operator-lab/31-operator-deploy.yaml
kubectl -n operator-lab rollout status deploy/webapp-operator
kubectl -n operator-lab logs -f deploy/webapp-operator
```

Il primo avvio impiega ~30s perche' il container fa `pip install` di
`kopf` e `kubernetes`. Nel log vedrai:

```text
[bootstrap] installing kopf + kubernetes client...
[bootstrap] launching kopf...
[INFO] Initial authentication has been initiated.
[INFO] Initial authentication has finished.
[INFO] Watching for training.example.com/v1alpha1/webapps in operator-lab
```

Lascia il `logs -f` aperto in un terminale separato: aiuta a vedere
gli handler scattare in tempo reale.

## Passo 3.4 — La WebApp `ciao-mondo` ora viene riconciliata

La WebApp che avevi gia' applicato nella Parte 2 e' rimasta in attesa.
Appena l'operator parte, dovresti vedere nei log:

```text
[INFO] [operator-lab/ciao-mondo] Created Deployment/ciao-mondo in operator-lab
[INFO] [operator-lab/ciao-mondo] Created Service/ciao-mondo in operator-lab
[INFO] [operator-lab/ciao-mondo] Handler 'reconcile' succeeded.
```

Verifica:

```bash
kubectl get webapps -n operator-lab
kubectl get deploy,svc,pod -n operator-lab
```

Output atteso:

```text
NAME         IMAGE         REPLICAS   PHASE     URL                                            AGE
ciao-mondo   nginx:1.27    2          Running   http://ciao-mondo.operator-lab.svc...:80       2m
```

E i Pod del Deployment `ciao-mondo` sono in `Running`.

Apri lo `status` per intero:

```bash
kubectl get webapp ciao-mondo -n operator-lab -o jsonpath='{.status}' | jq
```

```json
{
  "phase": "Running",
  "deploymentName": "ciao-mondo",
  "serviceName": "ciao-mondo",
  "observedReplicas": 2,
  "url": "http://ciao-mondo.operator-lab.svc.cluster.local:80"
}
```

## Passo 3.5 — Verifica le ownerReferences

L'operator ha settato `ownerReferences` sulle risorse create, in modo
che siano "figlie" della WebApp. E' la chiave della cascade-delete.

```bash
kubectl get deploy ciao-mondo -n operator-lab -o jsonpath='{.metadata.ownerReferences}' | jq
kubectl get svc    ciao-mondo -n operator-lab -o jsonpath='{.metadata.ownerReferences}' | jq
```

Cerca `controller: true` e `kind: WebApp`. Significa che il garbage
collector di K8s cancellera' Deployment e Service nel momento esatto in
cui cancelli la WebApp. Niente codice di cleanup nel tuo operator.

## Passo 3.6 — Crea una nuova WebApp e guarda l'operator reagire

```bash
kubectl apply -f labs/operator-lab/40-webapp-sample.yaml
kubectl get webapp -n operator-lab -w        # Ctrl-C dopo qualche secondo
```

Nel log dell'operator (terminale aperto al Passo 3.3) vedi:

```text
[INFO] [operator-lab/sito-demo] Created Deployment/sito-demo in operator-lab
[INFO] [operator-lab/sito-demo] Created Service/sito-demo in operator-lab
```

Test funzionale: usa la URL dello status per chiamare l'app dal cluster:

```bash
kubectl run -it --rm curl --image=curlimages/curl --restart=Never -- \
  curl -s http://sito-demo.operator-lab.svc.cluster.local:80 | head -5
```

(la pagina di benvenuto di nginx)

## Passo 3.7 — Aggiorna la spec: scale + cambio immagine

```bash
kubectl apply -f labs/operator-lab/41-webapp-scaled.yaml
```

Cose che ti aspetti di osservare:

1. nei log dell'operator: `Patched Deployment/sito-demo`
2. `kubectl get pod -n operator-lab -w` mostra il rolling update di
   `sito-demo` da 1 a 3 repliche con la nuova immagine
3. `kubectl get webapp sito-demo -n operator-lab` mostra `REPLICAS: 3`
   e `IMAGE: nginx:1.27-alpine`
4. `.status.observedReplicas` aggiornato a 3

## Passo 3.8 — Una seconda WebApp, completamente indipendente

```bash
kubectl apply -f labs/operator-lab/42-webapp-second.yaml
kubectl get webapp,deploy,svc,pod -n operator-lab
```

Adesso hai due WebApp gestite dallo stesso operator: `sito-demo` e
`api-mock`. Per ognuna esiste un Deployment + Service. Hai dimostrato
che un singolo operator scala a N istanze della stessa risorsa custom.

## Passo 3.9 — Cancella la CR e osserva la cascade-delete

```bash
kubectl delete webapp api-mock -n operator-lab
kubectl get deploy,svc -n operator-lab -l app=api-mock
```

Output atteso: nessuna risorsa. K8s ha cancellato Deployment e Service
automaticamente perche' la WebApp era il loro `controller`. Nessun
handler `on.delete` nell'operator: e' tutto Garbage Collection nativo.

Conferma anche dai log dell'operator: vedrai un evento di "deletion
acknowledged" ma nessuna chiamata di cleanup.

---

# Esercizi extra (consigliati)

1. **Modifica il sorgente con rollout controllato**:
   - Edita `operator/main.py` cambiando il valore di default di `image`
     in `nginx:1.25`.
   - Ricrea la ConfigMap (`kubectl create configmap ... --from-file ...
     --dry-run=client -o yaml | kubectl apply -f -`).
   - `kubectl rollout restart deploy/webapp-operator -n operator-lab`.
   - Crea una WebApp senza `image` nello spec: l'API server la blocca
     perche' `image` e' `required`. Questo conferma che la CRD protegge
     il sistema anche da configurazioni incomplete.
2. **Forza un drift**: `kubectl scale deploy ciao-mondo -n operator-lab
   --replicas=5`. Aspetta. Cosa succede? L'operator riconcilia? Il
   Deployment torna a 2? **Spoiler: no**, perche' il nostro handler
   e' su `@kopf.on.update(... field='spec')` della WebApp, non su
   eventi del Deployment. In un operator di produzione aggiungeresti un
   `@kopf.on.update('apps', 'v1', 'deployments', labels={'managed-by':
   'webapp-operator'})` che richiama la reconcile. Provaci.
3. **Aggiungi un nuovo campo allo schema**: `spec.serviceType` (enum:
   ClusterIP, NodePort, LoadBalancer). Aggiorna la CRD e la funzione
   `build_service` per usarlo. Riapplica e ricarica la ConfigMap.
4. **Aggiungi un printer column** che mostra `.status.observedReplicas`.
5. **Conditions invece di phase**: cambia lo status per usare un array
   di `conditions` (Available, Progressing, Degraded) invece di un
   singolo `phase`. E' lo standard usato dai controller Kubernetes
   (Deployment, ReplicaSet, ecc.).

---

# Versione "produzione": kubebuilder / operator-sdk

Il pattern di questo lab — CRD + controller che reconcilia — e' lo
stesso che usano gli operator commerciali (Postgres, Kafka, Cert-Manager,
ArgoCD, ecc.). In produzione, pero', si scrive in **Go** con due
framework principali:

- **[kubebuilder](https://book.kubebuilder.io/)**: tooling ufficiale
  della SIG api-machinery. Genera CRD, RBAC, deepcopy, manager, ecc.
  da una `make`. E' la base di quasi tutti gli operator moderni.
- **[operator-sdk](https://sdk.operatorframework.io/)**: estende
  kubebuilder con scaffolding per la pubblicazione su OperatorHub e
  supporto per operator in Helm / Ansible.

Esempio di scaffolding kubebuilder che produrrebbe una struttura
analoga al nostro lab (ma in Go):

```bash
kubebuilder init --domain training.example.com --repo example.com/webapp-operator
kubebuilder create api --group training --version v1alpha1 --kind WebApp
# implementi Reconcile() in internal/controller/webapp_controller.go
make manifests   # rigenera config/crd/bases/*.yaml dal Go type
make install     # applica la CRD al cluster
make run         # gira il controller in locale, contro il kubeconfig corrente
```

Il `Reconcile(ctx, req)` di Go fa esattamente quello che fa il nostro
`reconcile()` Python: legge la CR, costruisce gli oggetti owned,
fa create-or-update, scrive lo status. La struttura concettuale e'
identica. La differenza e' che con Go ottieni:

- type-safety del client
- caching automatico (`client.Get` non chiama mai l'API server, va su una
  cache aggiornata da watch)
- workqueue con rate-limit, retry esponenziale, leader election
- generazione automatica della CRD dal tipo Go (single source of truth)

Per la didattica, kopf e' molto leggibile. In produzione, kubebuilder
offre maggiore robustezza operativa.

---

# Cleanup

```bash
# tutte le WebApp e le CRD (i Deployment+Service spariscono via GC)
kubectl delete -f labs/operator-lab/40-webapp-sample.yaml --ignore-not-found
kubectl delete -f labs/operator-lab/42-webapp-second.yaml --ignore-not-found
kubectl delete -f labs/operator-lab/22-cr-valid.yaml      --ignore-not-found
kubectl delete -f labs/operator-lab/11-cr-minimal.yaml    --ignore-not-found

# operator
kubectl delete -f labs/operator-lab/31-operator-deploy.yaml --ignore-not-found
kubectl delete configmap webapp-operator-code -n operator-lab --ignore-not-found
kubectl delete -f labs/operator-lab/30-operator-rbac.yaml   --ignore-not-found

# CRD (cancellare la CRD cancella tutte le CR rimaste e quindi anche le
# loro risorse owned)
kubectl delete -f labs/operator-lab/20-crd-v1.yaml --ignore-not-found

# namespace
kubectl delete -f labs/operator-lab/00-namespace.yaml --ignore-not-found

# cluster k3d (se l'avevi creato per il lab)
k3d cluster delete operator-lab
```

---

# Errori frequenti

- **`kubectl apply` della CR funziona ma l'operator non reagisce**.
  Controlla nell'ordine:
  - i log dell'operator (`kubectl logs -n operator-lab deploy/webapp-operator`),
  - che la CR sia nel namespace `operator-lab` (l'operator ascolta solo li' di
    default, vedi env `WATCH_NAMESPACE` nel Deployment),
  - che la `apiVersion` della CR sia esattamente
    `training.example.com/v1alpha1`.
- **Il Pod dell'operator e' in `CrashLoopBackOff` con
  `ModuleNotFoundError: No module named 'kopf'`**.
  Vuol dire che il `pip install` al boot e' fallito (rete?). Buildare
  il `Dockerfile` e usare quell'immagine al posto di `python:3.12-slim`.
- **`patch.status` non aggiorna la CR**.
  Manca il permesso RBAC su `webapps/status` (non basta quello su
  `webapps`). Verifica con `kubectl auth can-i update
  webapps.training.example.com/status --as=system:serviceaccount:operator-lab:webapp-operator -n operator-lab`.
- **Cancello la CR ma il Deployment resta**.
  Le `ownerReferences` non sono state settate. Verifica che nel codice
  ci sia `kopf.adopt(deployment)` PRIMA di `apps.create_namespaced_*`.
  Senza ownerReferences, la GC non sa che le risorse vanno cancellate.
- **`x-kubernetes-preserve-unknown-fields: true` e poi al passaggio a v1
  i miei CR esistenti diventano "broken"**.
  Si: i campi non previsti vengono "potati" al primo update. Per gestire
  l'evoluzione delle CRD esistono le `conversion webhook`, fuori
  scope per il lab.
- **`kubectl explain webapp.spec` dice "no documentation found"**.
  Hai applicato la CRD minimale (`10-crd-minimal.yaml`) ma non la v1.
  Applica `20-crd-v1.yaml` e riprova: e' la presenza dello schema
  OpenAPI a far funzionare `explain`.
- **L'operator funziona, ma `kubectl scale deploy` torna sempre indietro
  alle repliche della WebApp**.
  In questo lab non accade: il nostro `reconcile` scatta solo su
  cambi della spec della WebApp. Vedi Esercizio extra #2 per
  implementare anche il drift-detect sul Deployment.
