"""
检查模拟供应商数据和采购订单数据是否满足基本业务规则。
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"


def main():
    suppliers = pd.read_csv(
        DATA_DIR / "suppliers.csv",
        encoding="utf-8-sig",
    )

    orders = pd.read_csv(
        DATA_DIR / "purchase_orders.csv",
        encoding="utf-8-sig",
        parse_dates=[
            "order_date",
            "promised_date",
            "delivery_date",
        ],
    )

    # 将供应商的MOQ、MPQ和物料类别合并到订单表
    checked_orders = orders.merge(
        suppliers[
            [
                "supplier_id",
                "material_category",
                "moq",
                "mpq",
            ]
        ],
        on="supplier_id",
        how="left",
        suffixes=("_order", "_supplier"),
    )

    checks = {
        "供应商数量为30家": len(suppliers) == 30,
        "采购订单数量为1800笔": len(orders) == 1800,
        "供应商编号没有重复": suppliers["supplier_id"].is_unique,
        "采购订单编号没有重复": orders["po_id"].is_unique,
        "供应商数据没有缺失值": not suppliers.isna().any().any(),
        "订单数据没有缺失值": not orders.isna().any().any(),
        "订单供应商均存在于主表": checked_orders["moq"].notna().all(),
        "订单物料与供应商物料一致": (
            checked_orders["material_category_order"]
            == checked_orders["material_category_supplier"]
        ).all(),
        "承诺日期不早于下单日期": (
            orders["promised_date"] >= orders["order_date"]
        ).all(),
        "到货日期不早于下单日期": (
            orders["delivery_date"] >= orders["order_date"]
        ).all(),
        "订购数量均为正数": (
            orders["ordered_quantity"] > 0
        ).all(),
        "到货数量不超过订购数量": (
            orders["received_quantity"]
            <= orders["ordered_quantity"]
        ).all(),
        "拒收数量不超过到货数量": (
            orders["rejected_quantity"]
            <= orders["received_quantity"]
        ).all(),
        "订单数量满足MOQ": (
            checked_orders["ordered_quantity"]
            >= checked_orders["moq"]
        ).all(),
        "订单数量满足MPQ整数倍": (
            checked_orders["ordered_quantity"]
            % checked_orders["mpq"]
            == 0
        ).all(),
        "采购价格均为正数": (
            orders["actual_unit_price"] > 0
        ).all(),
        "合同采购标识只有0和1": (
            orders["is_contract"].isin([0, 1])
        ).all(),
    }

    print("数据质量检查结果：")
    print("-" * 50)

    for check_name, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"{status:<4} | {check_name}")

    print("-" * 50)

    failed_checks = [
        name for name, passed in checks.items()
        if not passed
    ]

    if failed_checks:
        print(f"检查未通过，共有{len(failed_checks)}项问题。")
        raise SystemExit(1)

    print("全部检查通过，数据可以进入KPI计算环节。")


if __name__ == "__main__":
    main()