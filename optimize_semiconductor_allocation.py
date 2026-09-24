"""
半导体关键物料订单分配优化。

对比两种方案：
1. 最低成本方案
2. 风险约束方案

输出：
data/allocation_details.csv
data/allocation_summary.csv
"""

from pathlib import Path

import pandas as pd
import pulp


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"

MATERIAL = "MCU控制芯片"
ANNUAL_DEMAND = 600_000


def optimize_allocation(
    supplier_data: pd.DataFrame,
    scenario_name: str,
    demand: int,
    max_share: float,
    min_suppliers: int,
    max_individual_risk: float | None = None,
    max_average_risk: float | None = None,
):
    """
    在满足需求、产能、MOQ、MPQ及风险约束的条件下，
    求解采购成本最低的订单分配方案。
    """

    if supplier_data.empty:
        raise ValueError("供应商数据不能为空。")

    if supplier_data["supplier_id"].duplicated().any():
        raise ValueError("供应商编号不能重复。")

    material_categories = (
        supplier_data["material_category"]
        .dropna()
        .unique()
    )

    if len(material_categories) != 1:
        raise ValueError(
            "每次优化只能包含一种物料类别。"
        )

    material_category = material_categories[0]

    data = supplier_data.set_index("supplier_id")
    supplier_ids = data.index.tolist()

    model = pulp.LpProblem(
        name=scenario_name,
        sense=pulp.LpMinimize,
    )

    # batch表示向供应商采购多少个MPQ批次
    batch = {
        supplier_id: pulp.LpVariable(
            f"batch_{supplier_id}",
            lowBound=0,
            cat="Integer",
        )
        for supplier_id in supplier_ids
    }

    # use表示是否启用该供应商
    use = {
        supplier_id: pulp.LpVariable(
            f"use_{supplier_id}",
            cat="Binary",
        )
        for supplier_id in supplier_ids
    }

    # 实际采购量 = MPQ × 批次数
    quantity = {
        supplier_id: (
            batch[supplier_id]
            * int(data.loc[supplier_id, "mpq"])
        )
        for supplier_id in supplier_ids
    }

    # 目标函数：采购总成本最低
    model += pulp.lpSum(
        data.loc[supplier_id, "contract_price"]
        * quantity[supplier_id]
        for supplier_id in supplier_ids
    )

    # 所有供应商的采购量必须正好满足年度需求
    model += (
        pulp.lpSum(
            quantity[supplier_id]
            for supplier_id in supplier_ids
        )
        == demand
    )

    for supplier_id in supplier_ids:
        capacity = int(
            data.loc[supplier_id, "annual_capacity"]
        )
        moq = int(data.loc[supplier_id, "moq"])

        # 未启用供应商时采购量必须为0；
        # 启用后采购量不能超过其年度产能
        model += (
            quantity[supplier_id]
            <= capacity * use[supplier_id]
        )

        # 启用供应商后必须达到最小起订量MOQ
        model += (
            quantity[supplier_id]
            >= moq * use[supplier_id]
        )

        # 单一供应商采购份额上限
        model += (
            quantity[supplier_id]
            <= max_share * demand
        )

        # 高风险供应商不允许进入风险约束方案
        if (
            max_individual_risk is not None
            and data.loc[
                supplier_id,
                "risk_score",
            ] >= max_individual_risk
        ):
            model += use[supplier_id] == 0

    # 至少启用指定数量的供应商
    model += (
        pulp.lpSum(
            use[supplier_id]
            for supplier_id in supplier_ids
        )
        >= min_suppliers
    )

    # 供应商组合的采购量加权平均风险上限
    if max_average_risk is not None:
        model += (
            pulp.lpSum(
                data.loc[supplier_id, "risk_score"]
                * quantity[supplier_id]
                for supplier_id in supplier_ids
            )
            <= max_average_risk * demand
        )

    model.solve(
        pulp.PULP_CBC_CMD(msg=False)
    )

    status = pulp.LpStatus[model.status]

    if status != "Optimal":
        raise RuntimeError(
            f"{scenario_name}求解失败，状态：{status}"
        )

    result_rows = []

    for supplier_id in supplier_ids:
        allocated_quantity = int(
            round(
                pulp.value(
                    quantity[supplier_id]
                )
                or 0
            )
        )

        if allocated_quantity == 0:
            continue

        unit_price = float(
            data.loc[supplier_id, "contract_price"]
        )

        result_rows.append(
            {
                "scenario": scenario_name,
                "supplier_id": supplier_id,
                "supplier_name": data.loc[
                    supplier_id,
                    "supplier_name",
                ],
                "risk_score": data.loc[
                    supplier_id,
                    "risk_score",
                ],
                "risk_level": data.loc[
                    supplier_id,
                    "risk_level",
                ],
                "unit_price": unit_price,
                "allocated_quantity": allocated_quantity,
                "allocation_share": (
                    allocated_quantity / demand
                ),
                "purchase_cost": (
                    allocated_quantity * unit_price
                ),
            }
        )

    result = pd.DataFrame(result_rows)

    total_cost = result["purchase_cost"].sum()

    average_risk = (
        result["risk_score"]
        * result["allocated_quantity"]
    ).sum() / demand

    largest_row = result.loc[
        result["allocated_quantity"].idxmax()
    ]

    disrupted_supplier = largest_row["supplier_id"]
    disrupted_quantity = largest_row[
        "allocated_quantity"
    ]

    # 完全停供后不重新分配订单，只计算原方案还能交付多少
    surviving_quantity = demand - disrupted_quantity
    post_disruption_service_level = (
        surviving_quantity / demand
    )

    summary = {
        "scenario": scenario_name,
        "material_category": material_category,
        "annual_demand": demand,
        "total_cost": round(total_cost, 2),
        "active_supplier_count": len(result),
        "average_risk_score": round(
            average_risk,
            4,
        ),
        "maximum_supplier_share": round(
            result["allocation_share"].max(),
            4,
        ),
        "disrupted_supplier": disrupted_supplier,
        "disrupted_quantity": int(
            disrupted_quantity
        ),
        "post_disruption_service_level": round(
            post_disruption_service_level,
            4,
        ),
    }

    return result, summary


def main():
    all_suppliers = pd.read_csv(
        DATA_DIR / "supplier_risk_score.csv",
        encoding="utf-8-sig",
    )

    material_suppliers = all_suppliers.loc[
        all_suppliers["material_category"] == MATERIAL
    ].copy()

    # 方案一：只考虑采购成本
    baseline_details, baseline_summary = (
        optimize_allocation(
            supplier_data=material_suppliers,
            scenario_name="最低成本方案",
            demand=ANNUAL_DEMAND,
            max_share=1.0,
            min_suppliers=1,
        )
    )

    # 方案二：加入供应集中度和风险限制
    resilience_details, resilience_summary = (
        optimize_allocation(
            supplier_data=material_suppliers,
            scenario_name="风险约束方案",
            demand=ANNUAL_DEMAND,
            max_share=0.40,
            min_suppliers=3,
            max_individual_risk=60,
            max_average_risk=30,
        )
    )

    allocation_details = pd.concat(
        [
            baseline_details,
            resilience_details,
        ],
        ignore_index=True,
    )

    allocation_summary = pd.DataFrame(
        [
            baseline_summary,
            resilience_summary,
        ]
    )

    baseline_cost = baseline_summary["total_cost"]
    resilience_cost = resilience_summary["total_cost"]

    cost_increase_rate = (
        resilience_cost - baseline_cost
    ) / baseline_cost

    service_improvement = (
        resilience_summary[
            "post_disruption_service_level"
        ]
        - baseline_summary[
            "post_disruption_service_level"
        ]
    )

    allocation_details.to_csv(
        DATA_DIR / "allocation_details.csv",
        index=False,
        encoding="utf-8-sig",
    )

    allocation_summary.to_csv(
        DATA_DIR / "allocation_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print("订单分配优化完成！")

    for scenario in allocation_summary[
        "scenario"
    ]:
        print(f"\n{scenario}：")

        current = allocation_details.loc[
            allocation_details["scenario"]
            == scenario,
            [
                "supplier_id",
                "supplier_name",
                "risk_score",
                "unit_price",
                "allocated_quantity",
                "allocation_share",
                "purchase_cost",
            ],
        ]

        print(current.to_string(index=False))

        scenario_summary = allocation_summary.loc[
            allocation_summary["scenario"]
            == scenario
        ].iloc[0]

        print(
            f"采购总成本："
            f"{scenario_summary['total_cost']:,.2f}"
        )
        print(
            f"组合平均风险分："
            f"{scenario_summary['average_risk_score']:.2f}"
        )
        print(
            f"最大供应商份额："
            f"{scenario_summary['maximum_supplier_share']:.2%}"
        )
        print(
            f"最大供应商完全停供后的保障率："
            f"{scenario_summary['post_disruption_service_level']:.2%}"
        )

    print("\n方案比较：")
    print(
        f"风险约束方案成本变化："
        f"{cost_increase_rate:.2%}"
    )
    print(
        f"停供后的供应保障率提升："
        f"{service_improvement:.2%}"
    )

    print(
        "\n结果已保存至："
        "\ndata/allocation_details.csv"
        "\ndata/allocation_summary.csv"
    )


if __name__ == "__main__":
    main()
