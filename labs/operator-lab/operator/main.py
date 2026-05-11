"""WebApp operator — versione didattica scritta con kopf.

Cosa fa:
  - osserva le CR `WebApp` nel namespace passato via env WATCH_NAMESPACE
  - per ognuna, crea (o aggiorna) un Deployment + un Service "owned"
  - aggiorna lo status della CR con phase, url, repliche osservate
  - alla cancellazione della CR, le risorse owned spariscono via garbage
    collection del controller manager (perche' settiamo ownerReferences
    con controller=true tramite kopf.adopt())

E' volutamente piccolo: ~80 righe, niente reconciler stateful, niente
work queue manuale. kopf fa tutto questo per te.

In produzione, lo schema "professionale" sarebbe scrivere lo stesso loop
in Go con controller-runtime (kubebuilder/operator-sdk). La logica di
reconciliation pero' e' la stessa.
"""

from __future__ import annotations

import logging
import os

import kopf
from kubernetes import client as k8s
from kubernetes.client import exceptions as k8s_exc

GROUP = "training.example.com"
VERSION = "v1alpha1"
PLURAL = "webapps"


# ---------------------------------------------------------------------------
# kopf lifecycle: configurazione globale
# ---------------------------------------------------------------------------
@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    """Configurazione di kopf, eseguita una volta all'avvio."""
    settings.posting.level = logging.INFO
    # disabilita il "peering" (coordinamento fra istanze multiple),
    # cosi' il lab funziona anche con un solo replica e senza CRD aggiuntive
    settings.peering.standalone = True


# ---------------------------------------------------------------------------
# Reconciliation: handler che reagisce a create/update sulla spec
# ---------------------------------------------------------------------------
@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL, field="spec")
def reconcile(spec, name, namespace, patch, logger, **_):
    """Crea/aggiorna Deployment+Service per la WebApp corrente."""
    image    = spec.get("image", "nginx:1.27")
    replicas = int(spec.get("replicas", 1))
    port     = int(spec.get("port", 80))
    message  = spec.get("message", f"Hello from {name}")

    deployment = build_deployment(name, image, replicas, port, message)
    service    = build_service(name, port)

    # Marca le risorse come "owned" dalla WebApp:
    # - aggiunge ownerReferences[*].controller=true
    # - quando la WebApp viene cancellata, K8s GC cancella anche queste
    kopf.adopt(deployment)
    kopf.adopt(service)

    apps = k8s.AppsV1Api()
    core = k8s.CoreV1Api()

    _create_or_patch(
        kind="Deployment", name=name, namespace=namespace, logger=logger,
        create=lambda: apps.create_namespaced_deployment(namespace, deployment),
        patch_=lambda: apps.patch_namespaced_deployment(name, namespace, deployment),
    )
    _create_or_patch(
        kind="Service", name=name, namespace=namespace, logger=logger,
        create=lambda: core.create_namespaced_service(namespace, service),
        # NB: clusterIP e' immutable. Non patchamo i Service: una volta
        # creati restano cosi'. In produzione faresti un drift-detect piu'
        # furbo (delete + recreate solo se cambia veramente qualcosa).
        patch_=None,
    )

    # Scrive lo status della WebApp via la subresource /status.
    # patch.status[...] viene tradotto da kopf in PATCH /status.
    patch.status["phase"]            = "Running"
    patch.status["deploymentName"]   = name
    patch.status["serviceName"]      = name
    patch.status["observedReplicas"] = replicas
    patch.status["url"]              = f"http://{name}.{namespace}.svc.cluster.local:{port}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _create_or_patch(*, kind, name, namespace, logger, create, patch_):
    """Idempotente: prova a creare, se 409 fa patch (o no-op)."""
    try:
        create()
        logger.info(f"Created {kind}/{name} in {namespace}")
    except k8s_exc.ApiException as e:
        if e.status == 409:
            if patch_ is not None:
                patch_()
                logger.info(f"Patched {kind}/{name} in {namespace}")
            else:
                logger.info(f"{kind}/{name} already exists, leaving as-is")
        else:
            raise


def build_deployment(name: str, image: str, replicas: int, port: int, message: str) -> dict:
    """Restituisce il manifest del Deployment come dict (no client model)."""
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "labels": {
                "app": name,
                "managed-by": "webapp-operator",
            },
        },
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "containers": [{
                        "name": "web",
                        "image": image,
                        "ports": [{"containerPort": port, "name": "http"}],
                        "env": [{"name": "WEBAPP_MESSAGE", "value": message}],
                        "resources": {
                            "requests": {"cpu": "10m",  "memory": "32Mi"},
                            "limits":   {"cpu": "200m", "memory": "128Mi"},
                        },
                    }],
                },
            },
        },
    }


def build_service(name: str, port: int) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "labels": {
                "app": name,
                "managed-by": "webapp-operator",
            },
        },
        "spec": {
            "type": "ClusterIP",
            "selector": {"app": name},
            "ports": [{"name": "http", "port": port, "targetPort": port}],
        },
    }


# ---------------------------------------------------------------------------
# Permette `python main.py` durante lo sviluppo locale.
# In cluster il container fa direttamente `kopf run ...`.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ns = os.environ.get("WATCH_NAMESPACE", "operator-lab")
    kopf.run(namespaces=[ns], standalone=True)
