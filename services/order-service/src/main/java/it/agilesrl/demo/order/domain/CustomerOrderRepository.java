package it.agilesrl.demo.order.domain;

import org.springframework.data.mongodb.repository.MongoRepository;

public interface CustomerOrderRepository extends MongoRepository<CustomerOrder, String> {
}
