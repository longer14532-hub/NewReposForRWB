from dataclasses import dataclass


@dataclass(frozen=True)
class MeshConfig:
    # --- 4 фильтра допуска SKU ---
    max_turnover_days: int = 14
    max_volume_l: float = 5.0
    max_weight_kg: float = 5.0
    max_price_rub: float = 5000.0

    # --- Ёмкость и окна Опорного ПВЗ (5 м²) ---
    pvz_max_capacity_units: int = 312
    pvz_working_limit_ratio: float = 0.80
    pvz_working_capacity_units: int = 250
    off_peak_start_hour: int = 10
    off_peak_end_hour: int = 16

    # --- Себестоимость Хаба (база: Зеленодольск -> Казань) ---
    default_hub_distance_km: float = 35.0
    hub_sort_cost: float = 18.00
    hub_storage_cost: float = 1.68
    hub_delivery_base: float = 25.00
    hub_delivery_per_km: float = 0.85
    hub_return_resort_cost: float = 12.00

    # --- Переменные затраты WB в Mesh ---
    pvz_payout_zero_leg: float = 20.00
    pvz_payout_1hop: float = 25.00
    seller_discount_mesh: float = 10.00
    seal_cost_zero_leg: float = 0.00
    seal_cost_1hop: float = 2.00

    # --- Возвраты ---
    return_rate: float = 0.10
    defect_rate_in_returns: float = 0.20
    smart_return_cost_zero_leg: float = 5.00
    smart_return_cost_1hop: float = 20.00

    # --- Рейсы и целевая маржа WB ---
    milk_run_trip_cost: float = 65.00
    shuttle_trip_cost: float = 215.20
    target_wb_margin: float = 10.00

    # --- Слот 60 секунд (мастер-короб) ---
    handover_sla_sec: int = 60
    handover_bonus_pvz: float = 5.00
    handover_penalty_pvz: float = 10.00

    # --- Прогрессивное хранение (неликвид) ---
    storage_base_daily_rub: float = 1.00
    storage_alert_day: int = 15
    storage_elevated_daily_rub: float = 2.00
    storage_evac_day: int = 30
    auto_evac_fee_seller: float = 45.00

    # --- Тариф логистики для селлера (для расчёта прибыли в ЛК) ---
    seller_base_logistics_hub: float = 65.00


DEFAULT_CONFIG = MeshConfig()