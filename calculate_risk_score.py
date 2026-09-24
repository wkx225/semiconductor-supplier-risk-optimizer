"""
基于供应商KPI构建可解释的加权风险评分。

输出：
data/supplier_risk_score.csv
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"


# 风险维度权重，总和必须为1
RISK_WEIGHTS = {
    "delivery": 0.30,
    "quality": 0.25,
    "fulfillment": 0.15,
    "price": 0.15,
    "compliance": 0.15,
}


def min_max_normalize(series: pd.Series) -> pd.Series:
    """
    将指标转换到0—1区间。

    0表示在当前供应商群体中风险最低，
    1表示在当前供应商群体中风险最高。
    """

    minimum = series.min()
    maximum = series.max()

    if maximum == minimum:
        return pd.Series(
            0.0,
            index=series.index,
        )

    return (
        (series - minimum)
        / (maximum - minimum)
    )


def main():
    supplier_kpi = pd.read_csv(
        DATA_DIR / "supplier_kpi.csv",
        encoding="utf-8-sig",
    )

    risk_data = supplier_kpi.copy()

    # 未足量到货率：订购数量中未能到货的比例
    risk_data["shortage_rate"] = (
        1 - risk_data["fill_rate"]
    )

    # -------------------------------------------------
    # 计算各维度风险得分
    # 每项得分已经乘以对应权重，合计最高100分
    # -------------------------------------------------

    risk_data["delivery_risk_points"] = (
        min_max_normalize(risk_data["late_rate"])
        * RISK_WEIGHTS["delivery"]
        * 100
    )

    risk_data["quality_risk_points"] = (
        min_max_normalize(risk_data["rejection_rate"])
        * RISK_WEIGHTS["quality"]
        * 100
    )

    risk_data["fulfillment_risk_points"] = (
        min_max_normalize(risk_data["shortage_rate"])
        * RISK_WEIGHTS["fulfillment"]
        * 100
    )

    risk_data["price_risk_points"] = (
        min_max_normalize(risk_data["price_volatility"])
        * RISK_WEIGHTS["price"]
        * 100
    )

    risk_data["compliance_risk_points"] = (
        min_max_normalize(risk_data["off_contract_rate"])
        * RISK_WEIGHTS["compliance"]
        * 100
    )

    # 五个风险维度相加，得到0—100分的综合风险分
    point_columns = [
        "delivery_risk_points",
        "quality_risk_points",
        "fulfillment_risk_points",
        "price_risk_points",
        "compliance_risk_points",
    ]

    risk_data["risk_score"] = (
        risk_data[point_columns].sum(axis=1)
    )

    # 风险等级：
    # 低于25分：低风险
    # 25—60分：中风险
    # 60分及以上：高风险
    risk_data["risk_level"] = pd.cut(
        risk_data["risk_score"],
        bins=[
            float("-inf"),
            25,
            60,
            float("inf"),
        ],
        labels=[
            "低风险",
            "中风险",
            "高风险",
        ],
        right=False,
    )

    # 风险排名：风险分越高，排名越靠前
    risk_data["risk_rank"] = (
        risk_data["risk_score"]
        .rank(
            ascending=False,
            method="min",
        )
        .astype(int)
    )

    # 保留4位小数
    numeric_columns = risk_data.select_dtypes(
        include="number"
    ).columns

    risk_data[numeric_columns] = (
        risk_data[numeric_columns].round(4)
    )

    # 按风险分从高到低排列
    risk_data = risk_data.sort_values(
        by="risk_score",
        ascending=False,
    ).reset_index(drop=True)

    output_path = (
        DATA_DIR / "supplier_risk_score.csv"
    )

    risk_data.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print("供应商风险评分完成！")
    print(f"供应商数量：{len(risk_data)}")
    print(f"输出文件：{output_path}")

    print("\n风险等级分布：")
    print(
        risk_data["risk_level"].value_counts(
            sort=False
        )
    )

    print("\n风险排名前10的供应商：")
    print(
        risk_data[
            [
                "risk_rank",
                "supplier_id",
                "supplier_name",
                "material_category",
                "risk_profile",
                "risk_score",
                "risk_level",
                "delivery_risk_points",
                "quality_risk_points",
                "fulfillment_risk_points",
                "price_risk_points",
                "compliance_risk_points",
            ]
        ].head(10)
    )

    print("\n各模拟风险类型的平均风险分：")
    print(
        risk_data.groupby(
            "risk_profile",
            observed=True,
        )["risk_score"]
        .mean()
        .sort_values(ascending=False)
        .round(2)
    )


if __name__ == "__main__":
    main()