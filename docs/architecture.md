# System Overview

## Order Service

### Responsibilities

- Place an order
- Track an order
- Cancel an order
- Coordinate Payment Service
- Coordinate Inventory Service
- Handle workflow failures and compensation

### Data

- id
- customer_id
- amount
- products[]
- status

### Endpoints

- POST /orders
- GET /orders/{id}

### Order Statuses

- PENDING
- COMPLETED
- FAILED
- PENDING_COMPENSATION

---

## Payment Service

### Responsibilities

- Process payment for an order
- Track payment status
- Refund successful payments

### Data

- payment_id
- order_id
- status
- amount

### Endpoints

- POST /payments
- GET /payments/{id}
- POST /payments/{payment_id}/refund

### Payment Statuses

- PROCESSING
- SUCCEEDED
- FAILED
- REFUNDED

---

## Inventory Service

### Responsibilities

- Track inventory
- Check availability
- Reserve items
- Commit reservations
- Release reservations

### Data

#### Inventory Item

- product_id
- available_quantity
- reserved_quantity

#### Reservation

- reservation_id
- product_id
- order_id
- quantity
- status

### Endpoints

- GET /items/{id}
- POST /reservations
- POST /reservations/{reservation_id}/commit
- POST /reservations/{reservation_id}/release

### Reservation Statuses

- RESERVED
- COMMITTED
- RELEASED

---

# Transaction Architecture

The Order Service acts as the orchestrator for the transaction.

This follows an orchestrated Saga pattern. Each service owns its own data, and the Order Service coordinates the workflow and triggers compensating actions when later steps fail.

- Order Service owns order and workflow state
- Payment Service owns payment state
- Inventory Service owns inventory and reservation state

## Happy Path

1. Client sends POST /orders
2. Order Service creates an order with status PENDING
3. Order Service asks Inventory Service to reserve the requested item
4. Inventory Service creates a RESERVED reservation
5. Order Service asks Payment Service to process payment
6. Payment Service returns SUCCEEDED
7. Order Service asks Inventory Service to commit the reservation
8. Inventory Service marks the reservation COMMITTED and reduces available stock
9. Order Service marks the order COMPLETED

```text
Client
  ↓
Order Service
  ↓
Create PENDING order
  ↓
Inventory Service
  ↓
Reserve inventory
  ↓
Payment Service
  ↓
Process payment
  ↓
Inventory Service
  ↓
Commit reservation
  ↓
Order = COMPLETED
```

# Failure and Compensation Flow

```text
Create order
    ↓
Reserve inventory
    ├─ service unavailable → FAILED
    ├─ reservation rejected → FAILED
    ↓
Process payment
    ├─ service unavailable
    │     ↓
    │   release reservation
    │     ├─ success → FAILED
    │     └─ failure → PENDING_COMPENSATION
    │
    ├─ payment failed
    │     ↓
    │   release reservation
    │     ├─ success → FAILED
    │     └─ failure → PENDING_COMPENSATION
    │
    └─ payment succeeded
          ↓
       Commit reservation
          ├─ success → COMPLETED
          │
          ├─ known failure
          │     ↓
          │   refund payment
          │     ↓
          │   release reservation
          │     ├─ both succeed → FAILED
          │     └─ cleanup incomplete → PENDING_COMPENSATION
          │
          └─ request outcome unknown
                ↓
          PENDING_COMPENSATION
```

# Compensation Rules

A compensating action reverses an earlier successful step when a later step fails.

```text
Reserve inventory → Release reservation
Successful payment → Refund payment
```

An order is marked FAILED only when the workflow has failed and all required cleanup has completed.

An order is marked PENDING_COMPENSATION when the workflow has failed but some cleanup is still unresolved.

Examples:

```text
Payment failed
Reservation released successfully
→ FAILED
```

```text
Payment succeeded
Inventory commit failed
Payment refunded
Reservation released
→ FAILED
```

```text
Payment succeeded
Inventory commit failed
Refund succeeded
Reservation release failed
→ PENDING_COMPENSATION
```

```text
Commit request times out and the Order Service cannot determine whether the reservation was committed
→ PENDING_COMPENSATION
```
