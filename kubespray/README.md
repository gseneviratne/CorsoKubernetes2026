# Kubespray con Vagrant

Questa cartella contiene i passaggi minimi per creare un cluster Kubernetes locale con Kubespray usando Vagrant.

## Prerequisiti

- Vagrant installato
- VirtualBox (o provider Vagrant equivalente) installato
- Python 3 disponibile nel sistema

## Avvio infrastruttura VM

```bash
vagrant up
```

## Scarica Kubespray (es: 2.29.0) e decomprimila:

```bash
curl -LO https://github.com/kubernetes-sigs/kubespray/archive/refs/tags/v2.29.0.zip
unzip v2.29.0.zip
rm -f v2.29.0.zip
```

## Setup ambiente Kubespray

```bash
cd kubespray-2.29.0
cp -rfp inventory/sample inventory/mycluster
cp ../inventory.ini inventory/mycluster/inventory.ini
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Deploy cluster Kubernetes

Da dentro `kubespray-2.29.0`, eseguire:

```bash
ansible-playbook -i inventory/mycluster/inventory.ini \
  --user vagrant \
  --become \
  cluster.yml
```

## Verifica rapida

Al termine del playbook, entrare nel nodo control-plane e verificare i nodi:

```bash
cd ..
vagrant ssh k8s-master-1
mkdir ~/.kube/
sudo cp -R /etc/kubernetes/admin.conf ~/.kube/config
sudo chown vagrant:vagrant ~/.kube/config
kubectl get nodes -o wide
```


## Upgrade del cluster Kubernetes

Per eseguire l’upgrade del cluster:

```bash
curl -LO https://github.com/kubernetes-sigs/kubespray/archive/refs/tags/v2.30.0.zip
unzip v2.30.0.zip
rm -f v2.30.0.zip
cd kubespray-2.30.0
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Da dentro `kubespray-2.30.0`, eseguire:

```bash
cp -rfp ../kubespray-2.29.0/inventory/mycluster inventory/mycluster
ansible-playbook -i inventory/mycluster/inventory.ini \
  --user vagrant \
  --become \
  upgrade-cluster.yml
```

## Aggiungere un nodo al cluster

1. **Aggiungi il nuovo nodo nel Vagrantfile**  
   Aumenta la variabile `NUM_NODES` e rilancia:

   ```bash
   vagrant up
   ```

2. **Aggiorna `inventory.ini`**  
   Aggiungi la nuova entry (ad es. `k8s-node-3`) nel file `inventory.ini`.  
   La riga può essere simile a:

   ```
   k8s-node-3 ip=172.18.8.103 access_ip=172.18.8.103 ansible_host=127.0.0.1 ansible_port=2202 ansible_user=vagrant ansible_ssh_private_key_file=.../k8s-node-3/virtualbox/private_key
   ```

3. **Rilancia il playbook solo per i nuovi nodi:**

   ```bash
   ansible-playbook -i inventory/mycluster/inventory.ini \
     --user vagrant \
     --become \
     scale.yml
   ```

   oppure il playbook principale (`cluster.yml`), che è idempotente.


## Rimuovere un nodo dal cluster

1. **Rimuovi il nodo dal Vagrantfile**  
   Riduci la variabile `NUM_NODES` e distruggi la VM del nodo da eliminare:

   ```bash
   vagrant destroy k8s-node-3 -f
   ```

2. **Rimuovi il nodo da `inventory.ini`**  
   Cancella la relativa entry e la referenza nei gruppi.

3. **Aggiorna il cluster:**

   ```bash
   ansible-playbook -i inventory/mycluster/inventory.ini \
     --user vagrant \
     --become \
     remove-node.yml --extra-vars "node=<nome-nodo-da-rimuovere>"
   ```

   oppure rilancia semplicemente `cluster.yml` per aggiornare la configurazione del cluster.

## Note
- Per distruggere e ricreare l'ambiente:

```bash
vagrant destroy -f
vagrant up
```