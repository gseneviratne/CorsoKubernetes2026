NAMESPACE=corso-demo
TAG?=latest

.PHONY: build-catalog build-order build-frontend build-images deploy undeploy

build-catalog:
	docker build -t catalog-service:$(TAG) ./services/catalog-service

build-order:
	docker build -t order-service:$(TAG) ./services/order-service

build-frontend:
	docker build -t frontend:$(TAG) ./frontend

build-images: build-catalog build-order build-frontend

deploy:
	kubectl apply -f k8s

undeploy:
	kubectl delete namespace $(NAMESPACE)
