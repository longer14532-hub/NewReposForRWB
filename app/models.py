import os
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mesh_wb.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


class StockItem(Base):
    __tablename__ = "stock_items"

    id = Column(Integer, primary_key=True, index=True)
    sku_code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    seller_name = Column(String, default="ИП Казань-Локал (FBS)")
    price = Column(Float, nullable=False)
    turnover_days = Column(Integer, default=7)
    volume_l = Column(Float, default=2.8)
    weight_kg = Column(Float, default=1.2)
    is_whitelist = Column(Boolean, default=True)
    has_factory_seal = Column(Boolean, default=True)
    qty_available = Column(Integer, default=0)
    qty_reserved = Column(Integer, default=0)
    storage_days = Column(Integer, default=1)
    status = Column(String, default="ACTIVE")  # ACTIVE | ALERT_15 | EVACUATED
    created_at = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, index=True, nullable=False)
    stock_item_id = Column(Integer, ForeignKey("stock_items.id"), nullable=False)
    cluster_name = Column(String, default="Казань — Советский")
    distance_km = Column(Float, default=35.0)
    requested_mode = Column(String, default="MILK_RUN")
    routed_channel = Column(String, nullable=False)  # ZERO_LEG | MILK_RUN | SHUTTLE | HUB
    batch_size = Column(Integer, default=8)
    n_min = Column(Integer, nullable=True)
    route_reason = Column(String, nullable=False)
    seal_code = Column(String, nullable=True)
    handover_sec = Column(Integer, nullable=True)
    status = Column(String, default="CREATED")
    # CREATED | PACKED | HANDED_OVER | DELIVERED | RETURNED_TO_SHELF | RETURNED_TO_HUB | REROUTED_HUB
    wb_cost = Column(Float, default=0.0)
    hub_baseline_cost = Column(Float, default=0.0)
    wb_saving = Column(Float, default=0.0)
    pvz_payout = Column(Float, default=0.0)
    seller_discount = Column(Float, default=0.0)
    sla_gain_hours = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    stock_item = relationship("StockItem")


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    actor = Column(String, nullable=False)  # WB | PVZ | SELLER
    category = Column(String, nullable=False)
    # PVZ_PAYOUT | PVZ_BONUS | PVZ_PENALTY | SELLER_REVENUE | SELLER_LOGISTICS |
    # SELLER_STORAGE | SELLER_EVAC | WB_SAVING | RETURN_RECALC
    amount = Column(Float, nullable=False)
    description = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemIncident(Base):
    __tablename__ = "system_incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_type = Column(String, nullable=False)
    details = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()