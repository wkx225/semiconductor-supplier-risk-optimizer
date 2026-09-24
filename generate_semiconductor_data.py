"""
生成半导体采购项目所需的模拟数据。

输出文件：
1. data/suppliers.csv       供应商主数据
2. data/purchase_orders.csv 采购订单明细

说明：
本项目全部使用模拟数据，不代表任何真实企业或供应商。
固定随机种子后，每次运行都会得到相同结果，便于复现。
"""

from pathlib import Path

import numpy as np
import pandas as pd


# 固定随机种子，保证每次运行结果一致
RANDOM_SEED = 42
rng = np.random.default_rng(RANDOM_SEED)

# 数据保存位置：当前项目根目录下的 data 文件夹
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


# 五类半导体关键物料及其模拟基准单价
MATERIALS = {
    "MCU控制芯片": 36.0,
    "功率半导体": 24.0,
    "模拟芯片": 18.0,
    "传感器芯片": 28.0,
    "存储芯片": 45.0,
}

REGIONS = [
    "华东",
    "华南",
    "华北",
    "西南",
    "海外",
]


# 不同风险类型的订单表现参数
RISK_PARAMETERS = {
    "稳定型": {
        "late_probability": 0.08,
        "average_delay_days": 3,
        "defect_rate": 0.008,
        "price_std": 0.015,
        "off_contract_probability": 0.03,
        "minimum_fill_rate": 0.97,
    },
    "交付风险型": {
        "late_probability": 0.35,
        "average_delay_days": 9,
        "defect_rate": 0.012,
        "price_std": 0.020,
        "off_contract_probability": 0.06,
        "minimum_fill_rate": 0.92,
    },
    "质量风险型": {
        "late_probability": 0.15,
        "average_delay_days": 5,
        "defect_rate": 0.040,
        "price_std": 0.020,
        "off_contract_probability": 0.05,
        "minimum_fill_rate": 0.94,
    },
    "价格风险型": {
        "late_probability": 0.15,
        "average_delay_days": 5,
        "defect_rate": 0.015,
        "price_std": 0.090,
        "off_contract_probability": 0.25,
        "minimum_fill_rate": 0.95,
    },
    "综合风险型": {
        "late_probability": 0.45,
        "average_delay_days": 12,
        "defect_rate": 0.055,
        "price_std": 0.100,
        "off_contract_probability": 0.30,
        "minimum_fill_rate": 0.88,
    },
}


def generate_suppliers() -> pd.DataFrame:
    """生成30家模拟供应商的主数据。"""

    # 18家稳定型，其余12家带有不同类型的风险
    risk_profiles = (
        ["稳定型"] * 18
        + ["交付风险型"] * 3
        + ["质量风险型"] * 3
        + ["价格风险型"] * 3
        + ["综合风险型"] * 3
    )
    rng.shuffle(risk_profiles)

    supplier_rows = []
    supplier_number = 1

    # 每类物料配置6家候选供应商，共30家
    for material, reference_price in MATERIALS.items():
        for _ in range(6):
            supplier_id = f"SUP{supplier_number:03d}"

            # MPQ：订单数量必须按该批量的整数倍采购
            mpq = int(rng.choice([100, 200, 500]))

            # MOQ：单次订单的最低采购数量
            moq = int(mpq * rng.choice([2, 4, 6]))

            contract_price = round(
                reference_price * rng.uniform(0.85, 1.18),
                2,
            )

            annual_capacity = int(
                rng.integers(250_000, 700_001) // 10_000 * 10_000
            )

            supplier_rows.append(
                {
                    "supplier_id": supplier_id,
                    "supplier_name": f"模拟供应商{supplier_number:02d}",
                    "material_category": material,
                    "region": rng.choice(REGIONS),
                    "risk_profile": risk_profiles[supplier_number - 1],
                    "contract_price": contract_price,
                    "annual_capacity": annual_capacity,
                    "moq": moq,
                    "mpq": mpq,
                    "target_lead_time_days": int(rng.integers(15, 46)),
                }
            )

            supplier_number += 1

    return pd.DataFrame(supplier_rows)


def generate_purchase_orders(
    suppliers: pd.DataFrame,
    orders_per_supplier: int = 60,
) -> pd.DataFrame:
    """根据供应商主数据生成采购订单明细。"""

    order_rows = []
    order_number = 1
    start_date = pd.Timestamp("2025-01-01")

    for supplier in suppliers.to_dict("records"):
        parameters = RISK_PARAMETERS[supplier["risk_profile"]]

        for _ in range(orders_per_supplier):
            po_id = f"PO{order_number:05d}"

            # 在2025年内随机生成下单日期
            order_date = start_date + pd.Timedelta(
                days=int(rng.integers(0, 365))
            )

            # 承诺交期围绕标准交付周期小幅波动
            promised_lead_time = max(
                7,
                supplier["target_lead_time_days"]
                + int(rng.integers(-3, 4)),
            )
            promised_date = order_date + pd.Timedelta(
                days=promised_lead_time
            )

            # 根据供应商风险类型，模拟是否延期
            is_late = (
                rng.random()
                < parameters["late_probability"]
            )

            if is_late:
                delay_days = max(
                    1,
                    int(
                        rng.poisson(
                            parameters["average_delay_days"]
                        )
                    ),
                )
            else:
                # 未延期订单可能提前0—3天到货
                delay_days = -int(rng.integers(0, 4))

            delivery_date = promised_date + pd.Timedelta(
                days=delay_days
            )

            # 生成订单数量，并保证满足MOQ和MPQ
            raw_quantity = int(rng.integers(2_000, 15_001))
            ordered_quantity = max(
                supplier["moq"],
                int(
                    np.ceil(raw_quantity / supplier["mpq"])
                    * supplier["mpq"]
                ),
            )

            # 根据供应商类型模拟到货完整率
            fill_rate = rng.uniform(
                parameters["minimum_fill_rate"],
                1.0,
            )
            received_quantity = int(
                round(ordered_quantity * fill_rate)
            )

            # 根据缺陷率模拟质量拒收数量
            rejected_quantity = int(
                rng.binomial(
                    received_quantity,
                    parameters["defect_rate"],
                )
            )

            # 模拟是否属于非合同采购
            is_contract = int(
                rng.random()
                >= parameters["off_contract_probability"]
            )

            price_change = rng.normal(
                0,
                parameters["price_std"],
            )

            # 非合同采购通常附带额外价格溢价
            if is_contract == 0:
                price_change += rng.uniform(0.03, 0.12)

            actual_unit_price = round(
                max(
                    0.01,
                    supplier["contract_price"]
                    * (1 + price_change),
                ),
                2,
            )

            order_rows.append(
                {
                    "po_id": po_id,
                    "supplier_id": supplier["supplier_id"],
                    "material_category": supplier[
                        "material_category"
                    ],
                    "order_date": order_date,
                    "promised_date": promised_date,
                    "delivery_date": delivery_date,
                    "ordered_quantity": ordered_quantity,
                    "received_quantity": received_quantity,
                    "rejected_quantity": rejected_quantity,
                    "contract_price": supplier["contract_price"],
                    "actual_unit_price": actual_unit_price,
                    "is_contract": is_contract,
                }
            )

            order_number += 1

    orders = pd.DataFrame(order_rows)

    date_columns = [
        "order_date",
        "promised_date",
        "delivery_date",
    ]

    for column in date_columns:
        orders[column] = orders[column].dt.strftime("%Y-%m-%d")

    return orders.sort_values(
        ["order_date", "po_id"]
    ).reset_index(drop=True)


def main():
    suppliers = generate_suppliers()
    purchase_orders = generate_purchase_orders(suppliers)

    supplier_path = DATA_DIR / "suppliers.csv"
    order_path = DATA_DIR / "purchase_orders.csv"

    # utf-8-sig使中文CSV可以直接用Excel正常打开
    suppliers.to_csv(
        supplier_path,
        index=False,
        encoding="utf-8-sig",
    )
    purchase_orders.to_csv(
        order_path,
        index=False,
        encoding="utf-8-sig",
    )

    print("模拟数据生成成功！")
    print(f"供应商数量：{len(suppliers)}")
    print(f"采购订单数量：{len(purchase_orders)}")
    print(f"供应商文件：{supplier_path}")
    print(f"订单文件：{order_path}")

    print("\n供应商风险类型分布：")
    print(suppliers["risk_profile"].value_counts())

    print("\n订单数据前5行：")
    print(purchase_orders.head())


if __name__ == "__main__":
    main()