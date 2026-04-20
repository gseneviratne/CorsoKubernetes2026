# Kyverno su Kubernetes

Questa guida descrive come installare [Kyverno](https://kyverno.io/), un policy engine nativo per Kubernetes, su un cluster gia' esistente. A differenza di altri strumenti come OPA/Gatekeeper, Kyverno non richiede di imparare un nuovo linguaggio: le policy si scrivono direttamente in YAML, come qualsiasi altra risorsa Kubernetes.

## Cos'e' Kyverno

Kyverno e' un **admission controller** che intercetta le richieste verso l'API server di Kubernetes e applica regole (policy) sulle risorse prima che vengano effettivamente create o modificate.

Le funzionalita' principali sono:

- **Validate**: blocca o segnala risorse che non rispettano determinate regole (es. nessun container privilegiato, immagini solo da registry autorizzati).
- **Mutate**: modifica automaticamente le risorse in ingresso (es. aggiunge label, annotation, sidecar, securityContext di default).
- **Generate**: crea risorse aggiuntive in risposta ad eventi (es. crea un `NetworkPolicy` o un `ResourceQuota` ogni volta che viene creato un nuovo namespace).
- **VerifyImages**: verifica firme e attestation delle immagini container (cosign, sigstore, Notary).
- **Cleanup**: rimuove automaticamente risorse vecchie o orfane in base a regole TTL.
- **Policy reports**: genera report (`PolicyReport`, `ClusterPolicyReport`) sullo stato di compliance del cluster.

Kyverno funziona sia in modalita' **enforce** (blocca le richieste non conformi) sia in modalita' **audit** (lascia passare ma registra le violazioni).

## Prerequisiti

- un cluster Kubernetes funzionante (versione 1.25+ consigliata)
- `kubectl` configurato verso il cluster corretto
- `helm` installato
- accesso amministrativo al cluster

```bash
kubectl get nodes
kubectl version
```

## Installazione con Helm

Aggiungi il repository Helm ufficiale di Kyverno:

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
```

Installa Kyverno nel namespace dedicato `kyverno`:

```bash
helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace
```

Per ambienti di produzione e' consigliato eseguire piu' repliche dell'admission controller:

```bash
helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --set admissionController.replicas=3 \
  --set backgroundController.replicas=2 \
  --set cleanupController.replicas=2 \
  --set reportsController.replicas=2
```

## Verifica dell'installazione

Controlla che i pod siano stati creati correttamente:

```bash
kubectl get pods -n kyverno
```

Dovresti vedere quattro componenti principali:

- `kyverno-admission-controller`: gestisce le richieste di admission (validate, mutate, verifyImages).
- `kyverno-background-controller`: applica le policy `generate` e le mutazioni in background.
- `kyverno-cleanup-controller`: gestisce le `CleanupPolicy`.
- `kyverno-reports-controller`: produce i `PolicyReport`.

Verifica che i deployment siano pronti:

```bash
kubectl rollout status deploy/kyverno-admission-controller -n kyverno
kubectl rollout status deploy/kyverno-background-controller -n kyverno
kubectl rollout status deploy/kyverno-cleanup-controller -n kyverno
kubectl rollout status deploy/kyverno-reports-controller -n kyverno
```

Controlla anche che le CRD siano installate:

```bash
kubectl get crd | grep kyverno
```

## Installazione delle policy predefinite (opzionale)

Kyverno mette a disposizione un chart con un set di policy gia' pronte basate sui Pod Security Standards e sulle best practice:

```bash
helm install kyverno-policies kyverno/kyverno-policies \
  --namespace kyverno \
  --set podSecurityStandard=baseline
```

I valori possibili per `podSecurityStandard` sono `baseline`, `restricted` o `privileged`.

Controlla le policy installate:

```bash
kubectl get clusterpolicy
```

## Tipi di policy

Kyverno offre due tipi di policy:

- **`ClusterPolicy`**: ha effetto su tutto il cluster.
- **`Policy`**: ha effetto solo all'interno di un singolo namespace.

Ogni policy contiene una o piu' **rule**, e ogni rule ha:

- un `match` (e opzionalmente un `exclude`) che definisce su quali risorse si applica
- un'azione: `validate`, `mutate`, `generate` o `verifyImages`
- un `validationFailureAction` (per le validate): `Enforce` o `Audit`

## Esempio 1: validazione (blocca i container privilegiati)

Esempio di `ClusterPolicy` che blocca la creazione di pod con container privilegiati:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privileged-containers
spec:
  validationFailureAction: Enforce
  background: true
  rules:
    - name: check-privileged
      match:
        any:
          - resources:
              kinds:
                - Pod
      validate:
        message: "I container privilegiati non sono ammessi."
        pattern:
          spec:
            containers:
              - =(securityContext):
                  =(privileged): "false"
```

Applica la policy:

```bash
kubectl apply -f disallow-privileged-containers.yaml
```

Prova a creare un pod privilegiato per vedere il rifiuto:

```bash
kubectl run test-privileged \
  --image=nginx \
  --overrides='{"spec":{"containers":[{"name":"test","image":"nginx","securityContext":{"privileged":true}}]}}'
```

La richiesta verra' rifiutata dall'admission controller con il messaggio definito nella policy.

## Esempio 2: mutazione (aggiunta automatica di label)

Esempio di `ClusterPolicy` che aggiunge automaticamente una label `team=platform` a tutti i nuovi namespace:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-team-label
spec:
  rules:
    - name: add-team-label
      match:
        any:
          - resources:
              kinds:
                - Namespace
      mutate:
        patchStrategicMerge:
          metadata:
            labels:
              team: platform
```

Crea un nuovo namespace e verifica la label:

```bash
kubectl create namespace demo-mutate
kubectl get namespace demo-mutate --show-labels
```

## Esempio 3: generate (crea automaticamente una NetworkPolicy)

Esempio di policy che crea una `NetworkPolicy` di default ogni volta che viene creato un nuovo namespace:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-networkpolicy
spec:
  rules:
    - name: default-deny
      match:
        any:
          - resources:
              kinds:
                - Namespace
      generate:
        kind: NetworkPolicy
        apiVersion: networking.k8s.io/v1
        name: default-deny
        namespace: "{{request.object.metadata.name}}"
        synchronize: true
        data:
          spec:
            podSelector: {}
            policyTypes:
              - Ingress
              - Egress
```

Crea un namespace e verifica la NetworkPolicy generata:

```bash
kubectl create namespace demo-generate
kubectl get networkpolicy -n demo-generate
```

## Esempio 4: verifyImages (verifica firma cosign)

Esempio di policy che accetta solo immagini firmate con cosign:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: verify-image-signature
spec:
  validationFailureAction: Enforce
  rules:
    - name: check-signature
      match:
        any:
          - resources:
              kinds:
                - Pod
      verifyImages:
        - imageReferences:
            - "ghcr.io/myorg/*"
          attestors:
            - entries:
                - keys:
                    publicKeys: |
                      -----BEGIN PUBLIC KEY-----
                      ...
                      -----END PUBLIC KEY-----
```

## Policy report

Kyverno genera report sulla compliance del cluster. Puoi consultarli con:

```bash
kubectl get policyreport -A
kubectl get clusterpolicyreport
```

Per vedere il dettaglio di un report:

```bash
kubectl describe policyreport -n <namespace>
```

I report contengono il numero di risorse `pass`, `fail`, `warn`, `error` e `skip` per ogni regola.

## Modalita' Audit vs Enforce

Quando una policy contiene `validate`, puoi scegliere il comportamento in caso di violazione tramite il campo `validationFailureAction`:

- **`Audit`**: la richiesta passa, ma viene registrata una violazione nei `PolicyReport`. Utile per monitorare l'impatto di una nuova policy senza bloccare gli utenti.
- **`Enforce`**: la richiesta viene rifiutata dall'admission controller.

Una buona pratica e' introdurre nuove policy in modalita' `Audit`, analizzare i report e poi passare a `Enforce` solo dopo aver risolto le violazioni esistenti.

## Test delle policy con Kyverno CLI

Kyverno mette a disposizione una CLI utile per testare le policy in locale prima di applicarle al cluster.

Installazione su macOS:

```bash
brew install kyverno
```

Installazione manuale:

```bash
curl -LO https://github.com/kyverno/kyverno/releases/latest/download/kyverno-cli_linux_x86_64.tar.gz
tar -xvf kyverno-cli_linux_x86_64.tar.gz
sudo mv kyverno /usr/local/bin/
```

Esempio di test di una policy contro una risorsa:

```bash
kyverno apply ./policies/ --resource ./resources/pod.yaml
```

Esempio di validazione della sintassi delle policy:

```bash
kyverno validate ./policies/
```

## Disinstallazione

Per rimuovere le policy e Kyverno:

```bash
helm uninstall kyverno-policies -n kyverno
helm uninstall kyverno -n kyverno
kubectl delete namespace kyverno
```

Rimuovi anche eventuali CRD residue se non servono piu':

```bash
kubectl get crd | grep kyverno.io | awk '{print $1}' | xargs kubectl delete crd
```

## Troubleshooting rapido

Se qualcosa non funziona, controlla:

```bash
kubectl get pods -n kyverno
kubectl describe pods -n kyverno
kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller
kubectl logs -n kyverno -l app.kubernetes.io/component=background-controller
```

Verifica che il webhook di admission sia registrato correttamente:

```bash
kubectl get validatingwebhookconfigurations | grep kyverno
kubectl get mutatingwebhookconfigurations | grep kyverno
```

Problemi comuni:

- webhook non raggiungibili a causa di network policy o firewall tra control plane e i pod di Kyverno
- versione di Kubernetes non compatibile con la versione di Kyverno installata
- policy in `Enforce` che bloccano workload critici (passare temporaneamente in `Audit` per debuggare)
- mancanza di permessi RBAC per le policy `generate` (Kyverno deve poter creare le risorse target)
- CRD non installate o non aggiornate dopo un upgrade

## Risorse utili

- [Documentazione ufficiale](https://kyverno.io/docs/)
- [Catalogo delle policy](https://kyverno.io/policies/)
- [Repository GitHub](https://github.com/kyverno/kyverno)
