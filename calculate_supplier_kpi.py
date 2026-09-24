"""
根据采购订单明细计算供应商绩效KPI。

输出：
data/supplier_kpi.csv
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"


def main():
    # 读取供应商主数据
    suppliers = pd.read_csv(
        DATA_DIR / "suppliers.csv",
        encoding="utf-8-sig",
    )

    # 读取采购订单，并将日期字段转换为日期格式
    orders = pd.read_csv(
        DATA_DIR / "purchase_orders.csv",
        encoding="utf-8-sig",
        parse_dates=[
            "order_date",
            "promised_date",
            "delivery_date",
        ],
    )

    # -------------------------------------------------
    # 第一步：计算每笔订单的基础指标
    # -------------------------------------------------

    # 实际到货日期不晚于承诺日期，则为准时交付
    orders["is_on_time"] = (
        orders["delivery_date"]
        <= orders["promised_date"]
    ).astype(int)

    orders["is_late"] = 1 - orders["is_on_time"]

    # 延期天数：提前或准时到货记为0天
    orders["delay_days"] = (
        orders["delivery_date"]
        - orders["promised_date"]
    ).dt.days.clip(lower=0)

    # 采购金额：订购数量 × 实际采购单价
    orders["purchase_amount"] = (
        orders["ordered_quantity"]
        * orders["actual_unit_price"]
    )

    # 实际价格相对合同价格的偏差
    orders["price_deviation_rate"] = (
        orders["actual_unit_price"]
        - orders["contract_price"]
    ) / orders["contract_price"]

    # 非合同采购标识：合同采购为0，非合同采购为1
    orders["is_off_contract"] = (
        1 - orders["is_contract"]
    )

    # -------------------------------------------------
    # 第二步：按照供应商汇总订单
    # -------------------------------------------------

    supplier_kpi = (
        orders.groupby("supplier_id")
        .agg(
            total_orders=("po_id", "count"),
            total_ordered_quantity=(
                "ordered_quantity",
                "sum",
            ),
            total_received_quantity=(
                "received_quantity",
                "sum",
            ),
            total_rejected_quantity=(
                "rejected_quantity",
                "sum",
            ),
            total_purchase_amount=(
                "purchase_amount",
                "sum",
            ),
            on_time_rate=("is_on_time", "mean"),
            late_rate=("is_late", "mean"),
            avg_delay_days=("delay_days", "mean"),
            average_unit_price=(
                "actual_unit_price",
                "mean",
            ),
            unit_price_std=(
                "actual_unit_price",
                "std",
            ),
            average_price_deviation_rate=(
                "price_deviation_rate",
                "mean",
            ),
            off_contract_rate=(
                "is_off_contract",
                "mean",
            ),
        )
        .reset_index()
    )

    # 到货满足率：实际到货数量 ÷ 订购数量
    supplier_kpi["fill_rate"] = (
        supplier_kpi["total_received_quantity"]
        / supplier_kpi["total_ordered_quantity"]
    )

    # 质量拒收率：拒收数量 ÷ 实际到货数量
    supplier_kpi["rejection_rate"] = (
        supplier_kpi["total_rejected_quantity"]
        / supplier_kpi["total_received_quantity"]
    )

    # 价格波动系数：价格标准差 ÷ 平均价格
    # 使用相对波动而不是直接比较标准差，
    # 可以避免高单价物料天然波动金额更大的问题。
    supplier_kpi["price_volatility"] = (
        supplier_kpi["unit_price_std"]
        / supplier_kpi["average_unit_price"]
    )

    # -------------------------------------------------
    # 第三步：补充供应商主数据
    # -------------------------------------------------

    supplier_kpi = supplier_kpi.merge(
        suppliers[
            [
                "supplier_id",
                "supplier_name",
                "material_category",
                "region",
                "risk_profile",
                "contract_price",
                "annual_capacity",
                "moq",
                "mpq",
            ]
        ],
        on="supplier_id",
        how="left",
    )

    # 调整字段顺序
    column_order = [
        "supplier_id",
        "supplier_name",
        "material_category",
        "region",
        "risk_profile",
        "total_orders",
        "total_purchase_amount",
        "on_time_rate",
        "late_rate",
        "avg_delay_days",
        "fill_rate",
        "rejection_rate",
        "average_unit_price",
        "average_price_deviation_rate",
        "price_volatility",
        "off_contract_rate",
        "total_ordered_quantity",
        "total_received_quantity",
        "total_rejected_quantity",
        "contract_price",
        "annual_capacity",
        "moq",
        "mpq",
    ]

    supplier_kpi = supplier_kpi[column_order]

    # 保留4位小数，方便查看和后续计算
    numeric_columns = supplier_kpi.select_dtypes(
        include="number"
    ).columns

    supplier_kpi[numeric_columns] = (
        supplier_kpi[numeric_columns].round(4)
    )

    # 保存结果
    output_path = DATA_DIR / "supplier_kpi.csv"

    supplier_kpi.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print("供应商KPI计算完成！")
    print(f"供应商数量：{len(supplier_kpi)}")
    print(f"输出文件：{output_path}")

    print("\n核心KPI前5行：")
    print(
        supplier_kpi[
            [
                "supplier_id",
                "supplier_name",
                "on_time_rate",
                "fill_rate",
                "rejection_rate",
                "price_volatility",
                "off_contract_rate",
            ]
        ].head()
    )

    print("\n不同模拟风险类型的平均KPI：")
    print(
        supplier_kpi.groupby("risk_profile")[
            [
                "on_time_rate",
                "fill_rate",
                "rejection_rate",
                "price_volatility",
                "off_contract_rate",
            ]
        ].mean().round(4)
    )


if __name__ == "__main__":
    main()