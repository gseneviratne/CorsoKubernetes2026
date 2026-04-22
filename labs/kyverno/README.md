## Lab: Kyverno

Laboratorio didattico per imparare a scrivere e applicare policy con **Kyverno**.
A differenza degli altri lab, questo non è un esercizio di troubleshooting ma un
percorso guidato che mostra, con esempi progressivi, le tre famiglie principali
di policy di Kyverno:

1. **Validate** — rifiuta o audita le risorse che non rispettano una regola
2. **Mutate** — modifica le risorse in ingresso (es. aggiunge label, patch)
3. **Generate** — crea automaticamente risorse correlate (es. NetworkPolicy)

### Prerequisiti

- Un cluster Kubernetes raggiungibile (`kubectl cluster-info`)
- **Kyverno già installato nel cluster**. Il lab non copre l'installazione.

Verifica che Kyverno sia presente e pronto:

```bash
kubectl get pods -n kyverno
kubectl get crd | grep kyverno.io
kubectl api-resources | grep kyverno
```

Ti aspetti di vedere i Pod di Kyverno in `Running` e le CRD
`clusterpolicies.kyverno.io`, `policies.kyverno.io`, `policyreports.wgpolicyk8s.io`.

Se Kyverno non è installato, puoi installarlo rapidamente con Helm:

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
helm install kyverno kyverno/kyverno -n kyverno --create-namespace
```

### Struttura del lab

```
labs/kyverno/
├── 00-namespace.yaml                  # Namespace kyverno-lab (con label kyverno-demo=true)
├── 10-validate-require-labels.yaml    # Validate/Enforce: richiede la label team
├── 20-validate-disallow-latest.yaml   # Validate/Audit: vieta :latest
├── 30-mutate-add-labels.yaml          # Mutate: aggiunge label di default
├── 40-mutate-imagepullpolicy.yaml     # Mutate: imagePullPolicy=Always su :latest
├── 50-generate-networkpolicy.yaml     # Generate: NetworkPolicy default-deny
└── tests/
    ├── pod-ok.yaml                    # Pod conforme
    ├── pod-missing-team.yaml          # Pod senza label team → rifiutato
    ├── pod-latest.yaml                # Pod con :latest → audit + mutation
    └── deployment-ok.yaml             # Deployment conforme
```

### Obiettivi didattici

- Leggere e scrivere una `ClusterPolicy` Kyverno
- Distinguere `validationFailureAction: Enforce` vs `Audit`
- Applicare mutation tramite `patchStrategicMerge` e `foreach`
- Generare risorse con `generate` + `synchronize`
- Leggere i `PolicyReport` per capire quali risorse violano le policy

---

## Passo 1 — Crea il namespace di lavoro

```bash
kubectl apply -f labs/kyverno/00-namespace.yaml
kubectl get ns kyverno-lab --show-labels
```

---

## Passo 2 — Validate in modalità Enforce (require-team-label)

Applica la prima policy: richiede la label `team` su tutti i Pod in `kyverno-lab`.

```bash
kubectl apply -f labs/kyverno/10-validate-require-labels.yaml
kubectl get clusterpolicy require-team-label
kubectl describe clusterpolicy require-team-label
```

Prova a creare un Pod **senza** la label `team`: deve essere **rifiutato**
dall'admission controller.

```bash
kubectl apply -f labs/kyverno/tests/pod-missing-team.yaml
```

Output atteso (errore bloccante):

```
Error from server: error when creating "...pod-missing-team.yaml":
admission webhook "validate.kyverno.svc-fail" denied the request:
resource Pod/kyverno-lab/pod-missing-team was blocked due to the following policies:
require-team-label:
  check-team-label: 'validation error: La label ''team'' è obbligatoria...'
```

Ora crea un Pod conforme:

```bash
kubectl apply -f labs/kyverno/tests/pod-ok.yaml
kubectl get pod pod-ok -n kyverno-lab
```

---

## Passo 3 — Validate in modalità Audit (disallow-latest-tag)

Applica la policy che vieta il tag `:latest`, ma in modalità **Audit**: le
violazioni **non bloccano** la creazione ma vengono registrate nei `PolicyReport`.

```bash
kubectl apply -f labs/kyverno/20-validate-disallow-latest.yaml
```

Crea un Pod che usa `nginx:latest` (passa, ma in audit):

```bash
kubectl apply -f labs/kyverno/tests/pod-latest.yaml
kubectl get pod pod-latest -n kyverno-lab
```

Verifica il `PolicyReport` del namespace:

```bash
kubectl get policyreport -n kyverno-lab
kubectl get policyreport -n kyverno-lab -o wide
kubectl describe policyreport -n kyverno-lab
```

Ti aspetti di vedere un `fail` per `pod-latest` sulla regola `require-image-tag`.

Prova a cambiare la policy da `Audit` a `Enforce` e riapplicala:

```bash
kubectl patch clusterpolicy disallow-latest-tag \
  --type=merge \
  -p '{"spec":{"validationFailureAction":"Enforce"}}'
```

Ora riprovando ad applicare `pod-latest.yaml` il deploy viene bloccato.

---

## Passo 4 — Mutate: aggiungi label di default (add-default-labels)

Applica la mutation policy che aggiunge `environment=dev` e `managed-by=kyverno`
a tutti i Pod del namespace.

```bash
kubectl apply -f labs/kyverno/30-mutate-add-labels.yaml
```

Ricrea il Pod conforme per farlo passare attraverso la mutation:

```bash
kubectl delete pod pod-ok -n kyverno-lab --ignore-not-found
kubectl apply -f labs/kyverno/tests/pod-ok.yaml
kubectl get pod pod-ok -n kyverno-lab --show-labels
```

Ti aspetti di vedere, oltre alle label originali, anche `environment=dev` e
`managed-by=kyverno` aggiunte automaticamente da Kyverno.

La sintassi `+(chiave): valore` significa *anchor condizionale*: aggiunge la
label solo se non esiste già.

---

## Passo 5 — Mutate con foreach (set-imagepullpolicy-always)

Applica la policy che, per ogni container con immagine `:latest`, forza
`imagePullPolicy: Always`.

```bash
kubectl apply -f labs/kyverno/40-mutate-imagepullpolicy.yaml
```

Prima rimetti la policy `disallow-latest-tag` in Audit (se l'hai messa in Enforce
nel passo 3), altrimenti il prossimo Pod verrebbe rifiutato:

```bash
kubectl patch clusterpolicy disallow-latest-tag \
  --type=merge \
  -p '{"spec":{"validationFailureAction":"Audit"}}'
```

Ricrea `pod-latest` e verifica `imagePullPolicy`:

```bash
kubectl delete pod pod-latest -n kyverno-lab --ignore-not-found
kubectl apply -f labs/kyverno/tests/pod-latest.yaml
kubectl get pod pod-latest -n kyverno-lab -o jsonpath='{.spec.containers[0].imagePullPolicy}{"\n"}'
```

Output atteso: `Always` (aggiunto dalla mutation).

---

## Passo 6 — Generate: crea una NetworkPolicy default-deny

Applica la generate policy. Genera automaticamente una NetworkPolicy
`default-deny` in ogni namespace che ha la label `kyverno-demo=true`.

```bash
kubectl apply -f labs/kyverno/50-generate-networkpolicy.yaml
```

Verifica che la NetworkPolicy sia stata creata nel namespace `kyverno-lab`:

```bash
kubectl get networkpolicy -n kyverno-lab
kubectl describe networkpolicy default-deny -n kyverno-lab
```

Prova a cancellarla: grazie a `synchronize: true`, Kyverno la **ricrea**:

```bash
kubectl delete networkpolicy default-deny -n kyverno-lab
sleep 5
kubectl get networkpolicy -n kyverno-lab
```

Prova a creare un altro namespace con la label `kyverno-demo=true` e verifica
che la NetworkPolicy venga generata anche lì:

```bash
kubectl create ns kyverno-lab-2
kubectl label ns kyverno-lab-2 kyverno-demo=true
sleep 5
kubectl get networkpolicy -n kyverno-lab-2
```

---

## Passo 7 — Esplora i PolicyReport

Kyverno produce `PolicyReport` per namespace (e `ClusterPolicyReport` per
risorse cluster-scoped). Sono il modo principale per capire lo stato delle
policy nel cluster.

```bash
kubectl get policyreport -A
kubectl get policyreport -n kyverno-lab -o yaml | head -80
```

Conta i pass/fail per policy:

```bash
kubectl get policyreport -n kyverno-lab \
  -o jsonpath='{range .items[*].results[*]}{.policy}{"\t"}{.result}{"\n"}{end}' \
  | sort | uniq -c
```

---

## Comandi utili di debug

```bash
kubectl get clusterpolicy
kubectl get policy -A
kubectl describe clusterpolicy <nome>

kubectl get policyreport -A
kubectl get clusterpolicyreport

kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller --tail=100
kubectl logs -n kyverno -l app.kubernetes.io/component=background-controller --tail=100
```

Test offline di una policy contro un manifest (richiede la CLI `kyverno`):

```bash
kyverno apply labs/kyverno/10-validate-require-labels.yaml \
  --resource labs/kyverno/tests/pod-missing-team.yaml
```

---

## Verifica finale

Tutte le policy presenti:

```bash
kubectl get clusterpolicy
```

Ti aspetti:

```
NAME                             ADMISSION   BACKGROUND   VALIDATE ACTION   READY
add-default-labels               true        false                          True
disallow-latest-tag              true        true         Audit             True
generate-default-deny-netpol     true        true                           True
require-team-label               true        false        Enforce           True
set-imagepullpolicy-always       true        false                          True
```

NetworkPolicy generata nel namespace:

```bash
kubectl get networkpolicy -n kyverno-lab
```

Pod conformi con label aggiunte dalla mutation:

```bash
kubectl get pods -n kyverno-lab --show-labels
```

---

## Cleanup

```bash
kubectl delete -f labs/kyverno/tests/ --ignore-not-found
kubectl delete -f labs/kyverno/ --ignore-not-found
kubectl delete ns kyverno-lab kyverno-lab-2 --ignore-not-found
```

Nota: cancellare le `ClusterPolicy` di tipo `generate` con `synchronize: true`
rimuove anche le risorse generate (se il flag di clone/sync lo consente).
Verifica sempre con `kubectl get networkpolicy -A` prima di concludere.

---

## Approfondimenti

- Kyverno docs: https://kyverno.io/docs/
- Policy Library ufficiale: https://kyverno.io/policies/
- Differenze Kyverno vs OPA/Gatekeeper: https://kyverno.io/docs/introduction/
