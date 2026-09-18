System overview

Order Service

- responsibilities
  - Place an order
  - Track an order
  - Cancel an order
  - Coordinate payment service
  - Coordinate inventory service

- data
  - id
  - customer_id
  - amount
  - products[]
  - status

- endpoints
  - Post /orders
  - Get /orders/{id}

Payment Service

- responsibilities
  - Process payment for order
  - track payment status
  - Cancel/Refund payment

- data
  - payment_id
  - order_id
  - status
  - amount

- endpoints
  - Post /payments
  - Get /payments/{id}

Inventory Service

- responsibilities
  - Track inventory
  - Check availability
  - Reserve items
  - Release reserved items

- data

Inventory item

- product id
- available quantity
- reserved quantity

Reservation

- product id
- order id
- reservation id
- quantity

- endpoints
  - Get /items/{id}
  - Post /reservations
  - Post /reservations/{reservation_id}/commit
  - Post /reservations/{reservation_id}/release

Happy-path transaction flow

1. Client sends POST /orders
2. Order Service creates a new order with status PENDING
3. Order Service asks Inventory Service to reserve the requested items
4. Inventory Service checks availability and creates the reservation
5. Order Service asks Payment Service to process payment
6. Payment Service processes payment and returns success
7. Order Service tells Inventory Service to commit the reservation
8. Inventory Service reduces available stock and clears the reserved quantity
9. Order Service marks the order as COMPLETED

<!-- Order Service = owns the business workflow
Payment Service = owns payment state
Inventory Service = owns inventory/reservation state -->
