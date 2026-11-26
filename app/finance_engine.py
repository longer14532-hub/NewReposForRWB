import math
from dataclasses import dataclass, replace
from typing import Optional

from app.config import DEFAULT_CONFIG, MeshConfig


@dataclass
class RouteDecision:
    channel: str  # ZERO_LEG | MILK_RUN | SHUTTLE | HUB
    wb_cost: float
    hub_baseline_cost: float
    wb_saving: float
    pvz_payout: float
    seller_discount: float
    n_min: Optional[int]
    reason: str
    sla_gain_hours: float


def calc_hub_delivery(distance_km: float, cfg: MeshConfig = DEFAULT_CONFIG) -> float:
    return cfg.hub_delivery_base + cfg.hub_delivery_per_km * distance_km


def calc_hub_return_leg(distance_km: float, cfg: MeshConfig = DEFAULT_CONFIG) -> float:
    return calc_hub_delivery(distance_km, cfg) + cfg.hub_return_resort_cost


def calc_hub_full_cost(distance_km: float, cfg: MeshConfig = DEFAULT_CONFIG) -> float:
    delivery = calc_hub_delivery(distance_km, cfg)
    direct = cfg.hub_sort_cost + cfg.hub_storage_cost + delivery
    expected_return = cfg.return_rate * (delivery + cfg.hub_return_resort_cost)
    return round(direct + expected_return, 2)


def calc_mesh_var_cost(mode: str, distance_km: float, cfg: MeshConfig = DEFAULT_CONFIG) -> float:
    hub_ret = calc_hub_return_leg(distance_km, cfg)
    if mode == "ZERO_LEG":
        exp_ret = cfg.return_rate * (
            (1.0 - cfg.defect_rate_in_returns) * cfg.smart_return_cost_zero_leg
            + cfg.defect_rate_in_returns * hub_ret
        )
        return round(cfg.pvz_payout_zero_leg + cfg.seller_discount_mesh + cfg.seal_cost_zero_leg + exp_ret, 2)

    exp_ret = cfg.return_rate * (
        (1.0 - cfg.defect_rate_in_returns) * cfg.smart_return_cost_1hop
        + cfg.defect_rate_in_returns * hub_ret
    )
    return round(cfg.pvz_payout_1hop + cfg.seller_discount_mesh + cfg.seal_cost_1hop + exp_ret, 2)


def calc_n_min(mode: str, distance_km: float, cfg: MeshConfig = DEFAULT_CONFIG) -> Optional[int]:
    hub_cost = calc_hub_full_cost(distance_km, cfg)
    if mode == "ZERO_LEG":
        var_cost = calc_mesh_var_cost("ZERO_LEG", distance_km, cfg)
        return 1 if (hub_cost - var_cost) >= cfg.target_wb_margin else None

    var_cost = calc_mesh_var_cost("1HOP", distance_km, cfg)
    transport_budget = hub_cost - var_cost - cfg.target_wb_margin
    if transport_budget <= 0:
        return None

    trip_cost = cfg.milk_run_trip_cost if mode == "MILK_RUN" else cfg.shuttle_trip_cost
    return int(math.ceil(trip_cost / transport_budget))


def validate_sku_filters(
    turnover_days: int,
    volume_l: float,
    weight_kg: float,
    price: float,
    is_whitelist: bool,
    has_factory_seal: bool,
    cfg: MeshConfig = DEFAULT_CONFIG,
) -> tuple[bool, list[str]]:
    errors = []
    if turnover_days > cfg.max_turnover_days:
        errors.append(f"Оборачиваемость {turnover_days} дн. > {cfg.max_turnover_days} дн. (не кат. A)")
    if volume_l > cfg.max_volume_l or weight_kg > cfg.max_weight_kg:
        errors.append(f"КГТ ({volume_l} л / {weight_kg} кг > лимита 5 л / 5 кг)")
    if not is_whitelist:
        errors.append("Товар не в белом списке (размерный ряд)")
    if not has_factory_seal:
        errors.append("Нет заводской пломбы")
    if price > cfg.max_price_rub:
        errors.append(f"Цена {price:.0f} ₽ > {cfg.max_price_rub:.0f} ₽")
    return len(errors) == 0, errors


def route_order(
    requested_mode: str,
    distance_km: float,
    batch_size: int,
    filters_ok: bool,
    is_evening_interdistrict: bool = False,
    circuit_breaker_open: bool = False,
    cfg: MeshConfig = DEFAULT_CONFIG,
) -> RouteDecision:
    hub_cost = calc_hub_full_cost(distance_km, cfg)

    if circuit_breaker_open:
        return RouteDecision(
            channel="HUB",
            wb_cost=hub_cost,
            hub_baseline_cost=hub_cost,
            wb_saving=0.0,
            pvz_payout=0.0,
            seller_discount=0.0,
            n_min=None,
            reason="Circuit Breaker активен (сбой логистики) → безопасный откат в Хаб",
            sla_gain_hours=0.0,
        )

    if not filters_ok:
        return RouteDecision(
            channel="HUB",
            wb_cost=hub_cost,
            hub_baseline_cost=hub_cost,
            wb_saving=0.0,
            pvz_payout=0.0,
            seller_discount=0.0,
            n_min=None,
            reason="Не пройдены 4 фильтра допуска Mesh → отправка через Хаб",
            sla_gain_hours=0.0,
        )

    if is_evening_interdistrict and requested_mode != "ZERO_LEG":
        return RouteDecision(
            channel="HUB",
            wb_cost=hub_cost,
            hub_baseline_cost=hub_cost,
            wb_saving=0.0,
            pvz_payout=0.0,
            seller_discount=0.0,
            n_min=None,
            reason="Вечерний межрайон (18–21) → защита от простоев, откат в Хаб",
            sla_gain_hours=0.0,
        )

    n_min = calc_n_min(requested_mode, distance_km, cfg)

    if requested_mode == "ZERO_LEG":
        var_cost = calc_mesh_var_cost("ZERO_LEG", distance_km, cfg)
        if n_min is None:
            return RouteDecision(
                channel="HUB",
                wb_cost=hub_cost,
                hub_baseline_cost=hub_cost,
                wb_saving=0.0,
                pvz_payout=0.0,
                seller_discount=0.0,
                n_min=None,
                reason=f"Близко к хабу (d={distance_km} км): маржа Zero-Leg ниже цели → Хаб",
                sla_gain_hours=0.0,
            )
        saving = round(hub_cost - var_cost, 2)
        return RouteDecision(
            channel="ZERO_LEG",
            wb_cost=var_cost,
            hub_baseline_cost=hub_cost,
            wb_saving=saving,
            pvz_payout=cfg.pvz_payout_zero_leg,
            seller_discount=cfg.seller_discount_mesh,
            n_min=1,
            reason=f"Zero-Leg (тот же Опорный ПВЗ, d={distance_km} км): экономия +{saving:.2f} ₽",
            sla_gain_hours=16.0,
        )

    var_cost = calc_mesh_var_cost("1HOP", distance_km, cfg)
    trip_cost = cfg.milk_run_trip_cost if requested_mode == "MILK_RUN" else cfg.shuttle_trip_cost
    unit_cost_if_run = round(var_cost + (trip_cost / max(batch_size, 1)), 2)

    if n_min is None or batch_size < n_min or (hub_cost - unit_cost_if_run) < cfg.target_wb_margin:
        loss_or_shortfall = round(hub_cost - unit_cost_if_run, 2)
        n_min_str = str(n_min) if n_min is not None else "∞ (нерентабельно на этой дистанции)"
        return RouteDecision(
            channel="HUB",
            wb_cost=hub_cost,
            hub_baseline_cost=hub_cost,
            wb_saving=0.0,
            pvz_payout=0.0,
            seller_discount=0.0,
            n_min=n_min,
            reason=(
                f"Автооткат в Хаб: {requested_mode} при N={batch_size} < N_min={n_min_str} "
                f"(d={distance_km} км; расход составил бы {unit_cost_if_run:.2f} ₽, дельта {loss_or_shortfall:+.2f} ₽)"
            ),
            sla_gain_hours=0.0,
        )

    saving = round(hub_cost - unit_cost_if_run, 2)
    return RouteDecision(
        channel=requested_mode,
        wb_cost=unit_cost_if_run,
        hub_baseline_cost=hub_cost,
        wb_saving=saving,
        pvz_payout=cfg.pvz_payout_1hop,
        seller_discount=cfg.seller_discount_mesh,
        n_min=n_min,
        reason=(
            f"1-Hop {requested_mode} (d={distance_km} км, N={batch_size} ≥ N_min={n_min}): "
            f"расход {unit_cost_if_run:.2f} ₽ vs Хаб {hub_cost:.2f} ₽ → экономия +{saving:.2f} ₽"
        ),
        sla_gain_hours=10.0 if requested_mode == "MILK_RUN" else 8.0,
    )


def calc_progressive_storage_delta(prev_days: int, new_days: int, qty: int, cfg: MeshConfig = DEFAULT_CONFIG) -> float:
    """Считает доначисление за хранение при переходе с prev_days к new_days."""
    if new_days <= prev_days or qty <= 0:
        return 0.0
    total = 0.0
    for day in range(prev_days + 1, min(new_days, cfg.storage_evac_day - 1) + 1):
        rate = cfg.storage_base_daily_rub if day < cfg.storage_alert_day else cfg.storage_elevated_daily_rub
        total += rate * qty
    return round(total, 2)


def make_custom_config(
    hub_delivery_base: Optional[float] = None,
    milk_run_trip_cost: Optional[float] = None,
    shuttle_trip_cost: Optional[float] = None,
    pvz_payout_1hop: Optional[float] = None,
    seller_discount_mesh: Optional[float] = None,
    return_rate: Optional[float] = None,
) -> MeshConfig:
    updates = {}
    if hub_delivery_base is not None:
        updates["hub_delivery_base"] = hub_delivery_base
    if milk_run_trip_cost is not None:
        updates["milk_run_trip_cost"] = milk_run_trip_cost
    if shuttle_trip_cost is not None:
        updates["shuttle_trip_cost"] = shuttle_trip_cost
        updates["pvz_payout_zero_leg"] = max(5.0, pvz_payout_1hop - 5.0)
    if seller_discount_mesh is not None:
        updates["seller_discount_mesh"] = seller_discount_mesh
    if return_rate is not None:
        updates["return_rate"] = return_rate
    return replace(DEFAULT_CONFIG, **updates)