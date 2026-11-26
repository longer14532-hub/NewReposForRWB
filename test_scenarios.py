from fastapi.testclient import TestClient

from app.finance_engine import calc_hub_full_cost, calc_n_min
from app.main import app

client = TestClient(app)


def test_1_fixed_math_thresholds():
    # Проверка 100% синхронизации с модельной частью
    assert calc_hub_full_cost(35.0) == 81.11
    assert calc_hub_full_cost(6.0) == 53.99
    assert calc_n_min("MILK_RUN", 35.0) == 3
    assert calc_n_min("SHUTTLE", 35.0) == 7


def test_2_offpeak_and_filters_guard():
    client.post("/api/seed")
    # Пиковый час 19:00 -> отказ
    r_peak = client.post(
        "/api/stock/intake",
        json={"sku_code": "T-1", "name": "Test", "price": 1000, "qty": 5, "current_hour": 19},
    )
    assert r_peak.status_code == 400
    # Цена > 5000 -> отказ
    r_price = client.post(
        "/api/stock/intake",
        json={"sku_code": "T-2", "name": "Expensive", "price": 7500, "qty": 5, "current_hour": 12},
    )
    assert r_price.status_code == 400


def test_3_hub_rollback_on_low_batch_and_near_hub():
    client.post("/api/seed")
    r = client.post("/api/demo/scenario2")
    assert r.status_code == 200
    state = client.get("/api/state").json()
    latest_two = state["orders"][:2]
    assert all(o["routed_channel"] == "HUB" for o in latest_two)
    assert all(o["wb_saving"] == 0.0 for o in latest_two)


def test_4_return_shelf_vs_hub():
    client.post("/api/seed")
    client.post("/api/demo/scenario1")
    r_shelf = client.post("/api/demo/scenario3?intact_seal=true")
    assert r_shelf.status_code == 200
    assert "Smart Return-to-Shelf" in r_shelf.json()["details"]

    client.post("/api/demo/scenario1")
    r_hub = client.post("/api/demo/scenario3?intact_seal=false")
    assert r_hub.status_code == 200
    assert "Хаб" in r_hub.json()["details"]


def test_5_circuit_breaker_and_idempotency():
    client.post("/api/seed")
    r = client.post("/api/demo/scenario4")
    assert r.status_code == 200
    assert r.json()["idempotency_blocked_duplicate"] is True
    client.post("/api/demo/scenario4/reset")


def test_6_storage_30_days_auto_evacuation_and_shadow_routing():
    client.post("/api/seed")
    r = client.post("/api/demo/scenario5?days=15")
    assert r.status_code == 200
    assert "SKU-KZN-003" in r.json()["details"]

    sr = client.post("/api/shadow-routing", json={"n_orders": 500})
    assert sr.status_code == 200
    data = sr.json()
    assert data["unprofitable_trips"] == 0
    assert data["criteria"]["saving_ge_15pct"] is True
    assert data["criteria"]["pvz_ge_20k"] is True