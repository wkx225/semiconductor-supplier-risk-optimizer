"""按顺序运行半导体供应商风险与订单分配完整流程。"""

from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent

PIPELINE_STEPS = [
    ("生成模拟数据", "generate_semiconductor_data.py"),
    ("校验数据质量", "validate_semiconductor_data.py"),
    ("计算供应商KPI", "calculate_supplier_kpi.py"),
    ("计算供应商风险分", "calculate_risk_score.py"),
    ("优化订单分配", "optimize_semiconductor_allocation.py"),
]


def main() -> None:
    for step_name, script_name in PIPELINE_STEPS:
        print(f"\n{'=' * 60}", flush=True)
        print(f"开始：{step_name}", flush=True)
        print(f"{'=' * 60}", flush=True)

        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / script_name)],
            cwd=PROJECT_ROOT,
            check=True,
        )

    print("\n完整流程运行成功。")
    print("运行看板：python -m streamlit run risk_dashboard.py")


if __name__ == "__main__":
    main()
