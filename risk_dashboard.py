"""
半导体关键物料供应商风险与订单分配看板。

运行命令：
python -m streamlit run risk_dashboard.py
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from optimize_semiconductor_allocation import optimize_allocation


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
MATERIAL = "MCU控制芯片"


st.set_page_config(
    page_title="半导体供应商风险与韧性采购",
    page_icon="📦",
    layout="wide",
)


@st.cache_data
def load_data() -> pd.DataFrame:
    """读取已经计算完成的供应商风险数据。"""
    return pd.read_csv(
        DATA_DIR / "supplier_risk_score.csv",
        encoding="utf-8-sig",
    )


def percent_text(value: float) -> str:
    """将0—1之间的小数显示为百分比。"""
    return f"{value:.2%}"


risk_data = load_data()


# =====================================================
# 页面标题和核心指标
# =====================================================

st.title("半导体关键物料供应商风险与韧性采购看板")

st.caption(
    "基于模拟采购订单数据构建。所有供应商名称、订单和金额均为虚构，"
    "仅用于供应链分析与优化方法展示。"
)

st.info(
    "分析流程：采购订单 → 供应商KPI → 可解释风险评分 → "
    "风险约束订单分配 → 供应商停供压力测试"
)

high_risk_count = int(
    (risk_data["risk_level"] == "高风险").sum()
)

medium_risk_count = int(
    (risk_data["risk_level"] == "中风险").sum()
)

total_purchase_amount = risk_data[
    "total_purchase_amount"
].sum()

metric_1, metric_2, metric_3, metric_4 = st.columns(4)

metric_1.metric(
    "评估供应商",
    f"{len(risk_data)}家",
)

metric_2.metric(
    "高风险供应商",
    f"{high_risk_count}家",
)

metric_3.metric(
    "中风险供应商",
    f"{medium_risk_count}家",
)

metric_4.metric(
    "模拟采购金额",
    f"{total_purchase_amount / 100_000_000:.2f}亿元",
)


tab_overview, tab_detail, tab_allocation, tab_method = st.tabs(
    [
        "风险总览",
        "供应商风险拆解",
        "订单分配优化",
        "方法说明",
    ]
)


# =====================================================
# 选项卡一：风险总览
# =====================================================

with tab_overview:
    st.subheader("供应商风险分布")

    left_chart, right_chart = st.columns([1, 2])

    with left_chart:
        level_order = [
            "低风险",
            "中风险",
            "高风险",
        ]

        level_counts = (
            risk_data["risk_level"]
            .value_counts()
            .reindex(
                level_order,
                fill_value=0,
            )
            .rename_axis("风险等级")
            .reset_index(name="供应商数量")
        )

        level_chart = (
            alt.Chart(level_counts)
            .mark_bar()
            .encode(
                x=alt.X(
                    "风险等级:N",
                    sort=level_order,
                    title=None,
                    axis=alt.Axis(labelAngle=0),
                ),
                y=alt.Y(
                    "供应商数量:Q",
                    title="供应商数量",
                ),
                color=alt.Color(
                    "风险等级:N",
                    scale=alt.Scale(
                        domain=level_order,
                        range=[
                            "#2E8B57",
                            "#F4A261",
                            "#D62828",
                        ],
                    ),
                    legend=None,
                ),
                tooltip=[
                    "风险等级",
                    "供应商数量",
                ],
            )
            .properties(height=350)
        )

        st.altair_chart(
            level_chart,
            width="stretch",
        )

    with right_chart:
        top_risk = (
            risk_data.nlargest(
                10,
                "risk_score",
            )
            .sort_values(
                "risk_score",
                ascending=True,
            )
        )

        ranking_chart = (
            alt.Chart(top_risk)
            .mark_bar()
            .encode(
                x=alt.X(
                    "risk_score:Q",
                    title="综合风险分",
                    scale=alt.Scale(
                        domain=[0, 100]
                    ),
                ),
                y=alt.Y(
                    "supplier_name:N",
                    title=None,
                    sort=None,
                ),
                color=alt.Color(
                    "risk_level:N",
                    title="风险等级",
                    scale=alt.Scale(
                        domain=[
                            "低风险",
                            "中风险",
                            "高风险",
                        ],
                        range=[
                            "#2E8B57",
                            "#F4A261",
                            "#D62828",
                        ],
                    ),
                ),
                tooltip=[
                    alt.Tooltip(
                        "supplier_id:N",
                        title="供应商编号",
                    ),
                    alt.Tooltip(
                        "supplier_name:N",
                        title="供应商",
                    ),
                    alt.Tooltip(
                        "material_category:N",
                        title="物料类别",
                    ),
                    alt.Tooltip(
                        "risk_score:Q",
                        title="风险分",
                        format=".2f",
                    ),
                ],
            )
            .properties(height=350)
        )

        st.altair_chart(
            ranking_chart,
            width="stretch",
        )

    st.subheader("供应商风险明细")

    selected_level = st.multiselect(
        "按风险等级筛选",
        options=[
            "高风险",
            "中风险",
            "低风险",
        ],
        default=[
            "高风险",
            "中风险",
        ],
    )

    risk_table = (
        risk_data.loc[
            risk_data["risk_level"].isin(
                selected_level
            ),
            [
                "risk_rank",
                "supplier_id",
                "supplier_name",
                "material_category",
                "region",
                "risk_score",
                "risk_level",
                "on_time_rate",
                "fill_rate",
                "rejection_rate",
                "price_volatility",
                "off_contract_rate",
            ],
        ]
        .sort_values("risk_rank")
        .copy()
    )

    percentage_columns = [
        "on_time_rate",
        "fill_rate",
        "rejection_rate",
        "price_volatility",
        "off_contract_rate",
    ]

    risk_table[percentage_columns] = (
        risk_table[percentage_columns] * 100
    )

    st.dataframe(
        risk_table,
        width="stretch",
        hide_index=True,
        column_config={
            "risk_rank": "风险排名",
            "supplier_id": "供应商编号",
            "supplier_name": "供应商名称",
            "material_category": "物料类别",
            "region": "地区",
            "risk_score": st.column_config.NumberColumn(
                "综合风险分",
                format="%.2f",
            ),
            "risk_level": "风险等级",
            "on_time_rate": st.column_config.NumberColumn(
                "准时交付率",
                format="%.2f%%",
            ),
            "fill_rate": st.column_config.NumberColumn(
                "到货满足率",
                format="%.2f%%",
            ),
            "rejection_rate": st.column_config.NumberColumn(
                "质量拒收率",
                format="%.2f%%",
            ),
            "price_volatility": st.column_config.NumberColumn(
                "价格波动系数",
                format="%.2f%%",
            ),
            "off_contract_rate": st.column_config.NumberColumn(
                "非合同采购占比",
                format="%.2f%%",
            ),
        },
    )


# =====================================================
# 选项卡二：供应商风险拆解
# =====================================================

with tab_detail:
    st.subheader("供应商风险来源分析")

    supplier_options = {
        (
            f"{row['supplier_name']}"
            f"（{row['supplier_id']}）"
        ): row["supplier_id"]
        for _, row in risk_data.sort_values(
            "risk_rank"
        ).iterrows()
    }

    selected_supplier_label = st.selectbox(
        "选择供应商",
        options=list(supplier_options.keys()),
    )

    selected_supplier_id = supplier_options[
        selected_supplier_label
    ]

    supplier_row = risk_data.loc[
        risk_data["supplier_id"]
        == selected_supplier_id
    ].iloc[0]

    detail_1, detail_2, detail_3, detail_4 = (
        st.columns(4)
    )

    detail_1.metric(
        "综合风险分",
        f"{supplier_row['risk_score']:.2f}",
    )

    detail_2.metric(
        "风险等级",
        supplier_row["risk_level"],
    )

    detail_3.metric(
        "风险排名",
        f"第{int(supplier_row['risk_rank'])}名",
    )

    detail_4.metric(
        "物料类别",
        supplier_row["material_category"],
    )

    contribution_data = pd.DataFrame(
        {
            "风险维度": [
                "交付风险",
                "质量风险",
                "供货风险",
                "价格风险",
                "合规风险",
            ],
            "风险贡献分": [
                supplier_row[
                    "delivery_risk_points"
                ],
                supplier_row[
                    "quality_risk_points"
                ],
                supplier_row[
                    "fulfillment_risk_points"
                ],
                supplier_row[
                    "price_risk_points"
                ],
                supplier_row[
                    "compliance_risk_points"
                ],
            ],
        }
    ).sort_values(
        "风险贡献分",
        ascending=True,
    )

    contribution_chart = (
        alt.Chart(contribution_data)
        .mark_bar(color="#D62828")
        .encode(
            x=alt.X(
                "风险贡献分:Q",
                title="风险贡献分",
            ),
            y=alt.Y(
                "风险维度:N",
                title=None,
                sort=None,
            ),
            tooltip=[
                "风险维度",
                alt.Tooltip(
                    "风险贡献分:Q",
                    format=".2f",
                ),
            ],
        )
        .properties(height=300)
    )

    st.altair_chart(
        contribution_chart,
        width="stretch",
    )

    kpi_1, kpi_2, kpi_3, kpi_4, kpi_5 = (
        st.columns(5)
    )

    kpi_1.metric(
        "准时交付率",
        percent_text(
            supplier_row["on_time_rate"]
        ),
    )

    kpi_2.metric(
        "到货满足率",
        percent_text(
            supplier_row["fill_rate"]
        ),
    )

    kpi_3.metric(
        "质量拒收率",
        percent_text(
            supplier_row["rejection_rate"]
        ),
    )

    kpi_4.metric(
        "价格波动系数",
        percent_text(
            supplier_row["price_volatility"]
        ),
    )

    kpi_5.metric(
        "非合同采购占比",
        percent_text(
            supplier_row["off_contract_rate"]
        ),
    )


# =====================================================
# 选项卡三：订单分配优化
# =====================================================

with tab_allocation:
    st.subheader(
        f"{MATERIAL}订单分配情景分析"
    )

    st.caption(
        "最低成本方案只考虑采购成本；"
        "风险约束方案在成本最小化基础上，"
        "加入集中度、供应商数量和风险限制。"
    )

    control_1, control_2, control_3 = st.columns(3)

    with control_1:
        annual_demand = st.slider(
            "年度需求量（件）",
            min_value=300_000,
            max_value=900_000,
            value=600_000,
            step=1_000,
        )

        max_share_percent = st.slider(
            "单一供应商最高份额",
            min_value=30,
            max_value=100,
            value=40,
            step=5,
            format="%d%%",
        )

    with control_2:
        minimum_suppliers = st.slider(
            "至少启用供应商数量",
            min_value=1,
            max_value=5,
            value=3,
            step=1,
        )

        max_average_risk = st.slider(
            "组合平均风险分上限",
            min_value=10,
            max_value=60,
            value=30,
            step=5,
        )

    with control_3:
        max_individual_risk = st.slider(
            "供应商风险准入上限",
            min_value=40,
            max_value=100,
            value=60,
            step=5,
            help=(
                "风险分达到该值的供应商"
                "不能进入风险约束方案。"
            ),
        )

        st.write("")
        st.write(
            "调整参数后，模型会自动重新求解。"
        )

    material_suppliers = risk_data.loc[
        risk_data["material_category"] == MATERIAL
    ].copy()

    try:
        baseline_details, baseline_summary = (
            optimize_allocation(
                supplier_data=material_suppliers,
                scenario_name="最低成本方案",
                demand=annual_demand,
                max_share=1.0,
                min_suppliers=1,
            )
        )

        risk_details, risk_summary = (
            optimize_allocation(
                supplier_data=material_suppliers,
                scenario_name="风险约束方案",
                demand=annual_demand,
                max_share=(
                    max_share_percent / 100
                ),
                min_suppliers=minimum_suppliers,
                max_individual_risk=(
                    max_individual_risk
                ),
                max_average_risk=(
                    max_average_risk
                ),
            )
        )

        cost_change_rate = (
            risk_summary["total_cost"]
            - baseline_summary["total_cost"]
        ) / baseline_summary["total_cost"]

        risk_score_reduction = (
            baseline_summary[
                "average_risk_score"
            ]
            - risk_summary[
                "average_risk_score"
            ]
        )

        max_share_reduction_points = (
            baseline_summary[
                "maximum_supplier_share"
            ]
            - risk_summary[
                "maximum_supplier_share"
            ]
        ) * 100

        service_improvement_points = (
            risk_summary[
                "post_disruption_service_level"
            ]
            - baseline_summary[
                "post_disruption_service_level"
            ]
        ) * 100

        result_1, result_2, result_3, result_4 = (
            st.columns(4)
        )

        result_1.metric(
            "风险约束方案成本",
            f"{risk_summary['total_cost'] / 10_000:,.2f}万元",
            delta=f"增加{cost_change_rate:.2%}",
            delta_color="inverse",
        )
        result_2.metric(
            "组合平均风险分",
            f"{risk_summary['average_risk_score']:.2f}",
            delta=f"-{risk_score_reduction:.2f}分",
            delta_color="inverse",
        )

        result_3.metric(
            "最大供应商份额",
            f"{risk_summary['maximum_supplier_share']:.2%}",
            delta=f"-{max_share_reduction_points:.2f}个百分点",
            delta_color="inverse",
        )

        result_4.metric(
            "停供后供应保障率",
            f"{risk_summary['post_disruption_service_level']:.2%}",
            delta=f"+{service_improvement_points:.2f}个百分点",
        )


        combined_details = pd.concat(
            [
                baseline_details,
                risk_details,
            ],
            ignore_index=True,
        )

        st.subheader("两种方案的订单分配对比")

        allocation_chart = (
            alt.Chart(combined_details)
            .mark_bar()
            .encode(
                x=alt.X(
                    "supplier_name:N",
                    title="供应商",
                    axis=alt.Axis(
                        labelAngle=0
                    ),
                ),
                xOffset=alt.XOffset(
                    "scenario:N",
                    title=None,
                ),
                y=alt.Y(
                    "allocated_quantity:Q",
                    title="分配数量（件）",
                ),
                color=alt.Color(
                    "scenario:N",
                    title="方案",
                    scale=alt.Scale(
                        domain=[
                            "最低成本方案",
                            "风险约束方案",
                        ],
                        range=[
                            "#7DBBE6",
                            "#1474C4",
                        ],
                    ),
                ),
                tooltip=[
                    alt.Tooltip(
                        "scenario:N",
                        title="方案",
                    ),
                    alt.Tooltip(
                        "supplier_name:N",
                        title="供应商",
                    ),
                    alt.Tooltip(
                        "risk_score:Q",
                        title="风险分",
                        format=".2f",
                    ),
                    alt.Tooltip(
                        "allocated_quantity:Q",
                        title="分配数量",
                        format=",.0f",
                    ),
                    alt.Tooltip(
                        "allocation_share:Q",
                        title="采购份额",
                        format=".2%",
                    ),
                ],
            )
            .properties(height=400)
        )

        st.altair_chart(
            allocation_chart,
            width="stretch",
        )

        display_details = combined_details[
            [
                "scenario",
                "supplier_id",
                "supplier_name",
                "risk_score",
                "unit_price",
                "allocated_quantity",
                "allocation_share",
                "purchase_cost",
            ]
        ].copy()

        display_details["allocation_share"] = (
            display_details["allocation_share"] * 100
        )

        st.dataframe(
            display_details,
            width="stretch",
            hide_index=True,
            column_config={
                "scenario": "方案",
                "supplier_id": "供应商编号",
                "supplier_name": "供应商名称",
                "risk_score": (
                    st.column_config.NumberColumn(
                        "风险分",
                        format="%.2f",
                    )
                ),
                "unit_price": (
                    st.column_config.NumberColumn(
                        "合同单价",
                        format="%.2f",
                    )
                ),
                "allocated_quantity": (
                    st.column_config.NumberColumn(
                        "分配数量",
                        format="%d",
                    )
                ),
                "allocation_share": (
                    st.column_config.NumberColumn(
                        "采购份额",
                        format="%.2f%%",
                    )
                ),
                "purchase_cost": (
                    st.column_config.NumberColumn(
                        "采购成本",
                        format="%.2f",
                    )
                ),
            },
        )

        st.warning(
            "停供压力测试假定采购量最大的供应商完全停供，"
            "且订单已经承诺，不能临时转移。"
            "供应保障率表示其他供应商原有订单"
            "仍能正常交付的比例。"
        )

    except RuntimeError as error:
        st.error(
            f"当前约束下没有可行方案：{error}"
        )

        st.write(
            "可以适当提高单家供应商份额上限、"
            "提高组合平均风险分上限，或者降低"
            "最少供应商数量后重新尝试。"
        )


# =====================================================
# 选项卡四：方法说明
# =====================================================

with tab_method:
    st.subheader("指标与模型说明")

    st.markdown(
        """
### 1. 供应商绩效指标

- 交付：准时交付率、延期率和平均延期天数；
- 质量：质量拒收率；
- 供货：到货满足率；
- 价格：实际采购价格波动；
- 合规：非合同采购占比。

### 2. 风险评分

综合风险分采用标准化后的线性加权评分：

- 延期风险：30%；
- 质量风险：25%；
- 未足量到货风险：15%；
- 价格风险：15%；
- 非合同采购风险：15%。

风险分表示当前供应商群体中的相对风险，
不代表供应商断供概率。

### 3. 订单分配

订单分配使用混合整数线性规划，即
MILP（Mixed-Integer Linear Programming）。

模型在满足需求、产能、MOQ、MPQ和风险约束的
条件下，寻找采购成本最低的订单组合。

### 4. 数据边界

本项目使用固定随机种子生成的模拟采购数据。
`risk_profile`仅用于验证模拟规律，
不参与风险评分和订单分配。
        """
    )