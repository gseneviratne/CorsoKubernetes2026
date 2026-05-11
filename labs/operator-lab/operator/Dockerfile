# Immagine "vera" per l'operator. Opzionale: il lab funziona anche senza
# costruirla, perche' il Deployment di default scarica le dipendenze al volo.
# Da usare se vuoi un avvio piu' veloce o un deliverable distribuibile.
#
# Build:
#   docker build -t webapp-operator:0.1 labs/operator-lab/operator
# Push (es. su un registry locale per k3d):
#   k3d image import webapp-operator:0.1 -c <nome-cluster>
# Poi modifica labs/operator-lab/31-operator-deploy.yaml usando l'immagine
# `webapp-operator:0.1` invece di `python:3.12-slim`.
FROM python:3.12-slim

WORKDIR /opt/operator
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .

ENV WATCH_NAMESPACE=operator-lab
USER 65534:65534

ENTRYPOINT ["kopf", "run", "--standalone", "--namespace=operator-lab", "/opt/operator/main.py"]
