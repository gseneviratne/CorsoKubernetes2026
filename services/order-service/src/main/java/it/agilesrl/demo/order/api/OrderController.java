package it.agilesrl.demo.order.api;

import it.agilesrl.demo.order.domain.CustomerOrder;
import it.agilesrl.demo.order.domain.CustomerOrderRepository;
import it.agilesrl.demo.order.domain.OrderItem;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.List;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final CustomerOrderRepository orderRepository;

    public OrderController(CustomerOrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    @GetMapping
    public List<CustomerOrder> findAll() {
        return orderRepository.findAll();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public CustomerOrder create(@Valid @RequestBody CustomerOrder order) {
        order.setId(null);
        order.setCreatedAt(Instant.now());
        order.setTotalAmount(calculateTotal(order.getItems()));
        return orderRepository.save(order);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable String id) {
        orderRepository.deleteById(id);
    }

    private double calculateTotal(List<OrderItem> items) {
        return items.stream()
                .mapToDouble(item -> item.getUnitPrice() * item.getQuantity())
                .sum();
    }
}
