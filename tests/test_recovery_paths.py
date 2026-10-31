"""Exercise recovery through the real endpoints using isolated SQLite databases."""

import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

with patch.dict(os.environ, {
    "ORDER_DATABASE_URL": "sqlite://",
    "INVENTORY_DATABASE_URL": "sqlite://",
    "PAYMENT_DATABASE_URL": "sqlite://",
}):
    from services.order_service.app import main as orders
    from services.inventory_service.app import main as inventory
    from services.payment_service.app import main as payments

from services.order_service.app.models import Base as OrderBase, Order
from services.inventory_service.app.models import Base as InventoryBase, InventoryItem, Reservation
from services.payment_service.app.models import Base as PaymentBase, Payment


class RecoveryPathsTest(unittest.TestCase):
    def setUp(self):
        self.sessions = []
        self.clients = []
        for service, base in (
            (orders, OrderBase), (inventory, InventoryBase), (payments, PaymentBase)
        ):
            engine = create_engine(
                "sqlite://", poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
            self.addCleanup(engine.dispose)
            base.metadata.create_all(engine)
            factory = sessionmaker(bind=engine)

            def make_override(session_factory):
                def get_db():
                    with session_factory() as db:
                        yield db
                return get_db

            service.app.dependency_overrides[service.get_db] = make_override(factory)
            self.addCleanup(service.app.dependency_overrides.clear)
            self.sessions.append(factory)
            client = TestClient(service.app)
            self.addCleanup(client.close)
            self.clients.append(client)
        self.order_client, self.inventory_client, self.payment_client = self.clients
        self.inventory_unavailable = False
        self.release_unavailable = False
        self.calls = []

    def seed(self, reservation_status, order_status="PENDING_COMPENSATION",
        refund_pending=True, release_pending=True):
        with self.sessions[0]() as db:
            db.add(Order(
                id=1, customer_id=1, amount=25, status=order_status,
                reservation_id=1, payment_id=1,
                refund_pending=refund_pending, release_pending=release_pending,
            ))
            db.commit()
        with self.sessions[1]() as db:
            committed = reservation_status == "COMMITTED"
            db.add(InventoryItem(
                id=1, available_quantity=9 if committed else 10,
                reserved_quantity=0 if committed else 1,
            ))
            db.add(Reservation(
                id=1, product_id=1, order_id=1, quantity=1,
                status=reservation_status,
            ))
            db.commit()
        with self.sessions[2]() as db:
            db.add(Payment(id=1, order_id=1, amount=25, status="SUCCEEDED"))
            db.commit()

    def dispatch(self, method, url, **kwargs):
        self.calls.append((method, url))
        parsed = httpx.URL(url)
        if parsed.port == 8002:
            if self.inventory_unavailable:
                raise httpx.ConnectError("Inventory unavailable")
            if self.release_unavailable and method == "POST" and parsed.path.endswith("/release"):
                raise httpx.ConnectError("Release unavailable")
            return self.inventory_client.request(method, parsed.path, **kwargs)
        if parsed.port == 8003:
            return self.payment_client.request(method, parsed.path, **kwargs)
        raise AssertionError(f"Unexpected service URL: {url}")

    def snapshot(self):
        with self.sessions[0]() as db:
            order = db.get(Order, 1)
            state = (order.status, order.release_pending, order.refund_pending)
        with self.sessions[1]() as db:
            reservation = db.get(Reservation, 1)
            item = db.get(InventoryItem, 1)
            state += (reservation.status, item.available_quantity, item.reserved_quantity)
        with self.sessions[2]() as db:
            state += (db.get(Payment, 1).status,)
        return state

    def recover_twice(self):
        with patch.object(httpx, "post", side_effect=lambda url, **kw: self.dispatch("POST", url, **kw)), \
             patch.object(httpx, "get", side_effect=lambda url, **kw: self.dispatch("GET", url, **kw)):
            first = self.order_client.post("/orders/1/recover")
            self.assertEqual(first.status_code, 200, first.text)
            state = self.snapshot()
            calls_after_first = len(self.calls)
            second = self.order_client.post("/orders/1/recover")
            self.assertEqual(second.status_code, 200, second.text)
            self.assertEqual(second.json(), first.json())
            self.assertEqual(self.snapshot(), state, "Second recovery changed persisted state")
            if state[0] in ("FAILED", "COMPLETED"):
                self.assertEqual(len(self.calls), calls_after_first,
                                 "Terminal recovery called another service")
        return state

    def test_inventory_unavailable_preserves_payment_and_pending_order(self):
        self.seed("RESERVED")
        self.inventory_unavailable = True
        self.assertEqual(self.recover_twice(), (
            "PENDING_COMPENSATION", True, True, "RESERVED", 10, 1, "SUCCEEDED",
        ))
        self.assertFalse(any(":8003/" in url for _, url in self.calls))

    def test_reserved_releases_refunds_and_clears_both_flags(self):
        self.seed("RESERVED")
        self.assertEqual(self.recover_twice(), (
            "FAILED", False, False, "RELEASED", 10, 0, "REFUNDED",
        ))

    def test_committed_completes_without_refund_and_clears_both_flags(self):
        self.seed("COMMITTED")
        self.assertEqual(self.recover_twice(), (
            "COMPLETED", False, False, "COMMITTED", 9, 0, "SUCCEEDED",
        ))

    def test_failed_release_with_reserved_status_keeps_compensation_pending(self):
        self.seed("RESERVED")
        self.release_unavailable = True
        self.assertEqual(self.recover_twice(), (
            "PENDING_COMPENSATION", True, True, "RESERVED", 10, 1, "SUCCEEDED",
        ))

    def test_already_released_reservation_allows_refund_after_release_error(self):
        self.seed("RESERVED")
        response = self.inventory_client.post("/reservations/1/release")
        self.assertEqual(response.status_code, 200)
        self.release_unavailable = True
        self.assertEqual(self.recover_twice(), (
            "FAILED", False, False, "RELEASED", 10, 0, "REFUNDED",
        ))

    def test_unknown_payment_success_recovery(self):
        self.seed(
            "RESERVED",
            order_status="PAYMENT_UNKNOWN",
            refund_pending=False,
            release_pending=False,
        )

        self.assertEqual(self.recover_twice(), (
            "FAILED",
            False,
            False,
            "RELEASED",
            10,
            0,
            "REFUNDED",
        ))

    def test_payment_404_then_successful_recovery(self):
        self.seed(
            "RESERVED",
            order_status="PAYMENT_UNKNOWN",
            refund_pending=False,
            release_pending=False,
        )

        # Payment exists in our test setup, but make it temporarily
        # invisible to the recovery endpoint.
        original_dispatch = self.dispatch

        def dispatch_with_404(method, url, **kwargs):
            if method == "GET" and "/payments/by-order/" in url:
                return httpx.Response(404)

            return original_dispatch(method, url, **kwargs)

        with patch.object(
            httpx, "get",
            side_effect=lambda url, **kw: dispatch_with_404("GET", url, **kw),
        ):
            response = self.order_client.post("/orders/1/recover")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "PAYMENT_UNKNOWN")

        # The 404 must not trigger inventory release or payment refund.
        self.assertEqual(self.snapshot(), (
            "PAYMENT_UNKNOWN", False, False,
            "RESERVED", 10, 1, "SUCCEEDED",
        ))

        # Payment is now visible. Recovery should finish compensation.
        self.assertEqual(self.recover_twice(), (
            "FAILED", False, False,
            "RELEASED", 10, 0, "REFUNDED",
        ))

if __name__ == "__main__":
    unittest.main()
