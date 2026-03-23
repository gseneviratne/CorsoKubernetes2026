NAMESPACE=corso-demo
REGISTRY?=ghcr.io/your-org
TAG?=latest

.PHONY: build-catalog build-order build-frontend build-images deploy undeploy

build-catalog:
	docker build -t $(REGISTRY)/catalog-service:$(TAG) ./services/catalog-service

build-order:
	docker build -t $(REGISTRY)/order-service:$(TAG) ./services/order-service

build-frontend:
	docker build -t $(REGISTRY)/frontend:$(TAG) ./frontend

build-images: build-catalog build-order build-frontend

deploy:
	kubectl apply -f k8s

undeploy:
	kubectl delete namespace $(NAMESPACE)
