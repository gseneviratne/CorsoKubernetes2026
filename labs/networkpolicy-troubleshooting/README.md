## Lab: NetworkPolicy troubleshooting (podSelector + namespaceSelector)

Questo sotto‑progetto è pensato come **esempio didattico**: applicandolo, “tutto” risulta **bloccato** o parzialmente rotto per via di NetworkPolicy volutamente errate/incomplete.

### Obiettivo didattico

- **Capire cosa blocca cosa** (Ingress/Egress, default deny).
- Sistemare policy che richiedono sia **`podSelector`** sia **`namespaceSelector`**.
- Fare troubleshooting su sintomi tipici:
  - chiamate HTTP tra pod che vanno in timeout
  - scrape “monitoring” che non arriva all’app
  - **DNS** che non risponde (egress verso `kube-system` sbagliato)

### Topologia

- Namespace `np-app`
  - `frontend` (pod “client” che fa curl)
  - `api` (server HTTP interno)
- Namespace `np-monitoring`
  - `scraper` (pod che fa curl verso `api` per simulare Prometheus)

### Applica il lab (versione “broken”)

Da root repo:

```bash
kubectl apply -f labs/networkpolicy-troubleshooting
```

### Verifiche rapide (dovrebbero fallire all’inizio)

- Dal `frontend` verso `api` (HTTP):

```bash
kubectl -n np-app exec deploy/frontend -- sh -lc 'curl -sS --max-time 3 http://api:5678/ || echo FAIL'
```

- Dal `scraper` (namespace diverso) verso `api`:

```bash
kubectl -n np-monitoring exec deploy/scraper -- sh -lc 'curl -sS --max-time 3 http://api.np-app.svc.cluster.local:5678/ || echo FAIL'
```

