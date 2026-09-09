"""Chinese, local-first batch workspace extending Dataset Cleaner."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
import streamlit as st
from order_batch import read_tables, suggested_mapping, run_batch, report_zip, report_xlsx, MAX_FILES
from order_demo import ROOT, demo_inputs
from order_rules import validate_config, FIELDS

st.set_page_config(page_title="OrderCheck · 订单批处理", page_icon="📋", layout="wide")
st.markdown("""<style>
.block-container {max-width:1200px;padding-top:2.5rem}
[data-testid="stMetric"] {background:#f3f6fa;border:1px solid #dfe6ee;
border-radius:8px;padding:16px}
header {background:transparent!important}
</style>""", unsafe_allow_html=True)
st.caption("DIGITAL NOMAD OS  /  PROJECT 001")
st.title("OrderCheck · 订单批处理工作台")
st.markdown("合并不同门店的订单表，找出错误与冲突，让每一条结果都有来源。")

with st.sidebar:
    st.header("本地数据工作台")
    st.write("01 选择文件\n\n02 确认列名\n\n03 校验并下载")
    st.divider()
    st.caption("基于 Louce / Dataset Cleaner · MIT\n\n独立二次开发 · Codex 辅助编码")
    st.caption("数据在本机处理；无需 AI 接口。")
    st.caption("单批 ≤20 文件、20,000 行；单文件 ≤5 MB。\nCSV：UTF-8；Excel：.xlsx，不含公式。")

mode = st.radio("数据来源", ["合成示例", "上传自己的文件"], horizontal=True)
uploads = None
if mode == "合成示例":
    st.info("演示使用 3 份合成文件（2 CSV + 1 Excel），含 12 条记录和预设错误；不代表客户数据。")
    inputs = demo_inputs()
else:
    uploads = st.file_uploader("选择 CSV / Excel（可以多选）", type=["csv", "xlsx"],
                               accept_multiple_files=True)
    if len(uploads or []) > MAX_FILES:
        st.error("单批最多 20 个文件")
        st.stop()
    inputs = [(f.name, f.getvalue()) for f in uploads or []]

with st.expander("业务规则 · 查看或修改 JSON"):
    rule_text = st.text_area("规则配置", (ROOT / "config/orders.json").read_text(encoding="utf-8"), height=260)
    st.caption("默认：同门店 + 订单号为重复键；金额使用小数点、最多两位小数；不猜测缺失值。")
try:
    config = validate_config(json.loads(rule_text))
    tables = [table for name, content in inputs for table in read_tables(name, content)]
except (ValueError, TypeError) as exc:
    st.error(f"无法处理：{exc}")
    st.stop()

if not tables:
    st.info("请上传文件，或切回“合成示例”开始体验。")
    st.stop()

st.subheader("1 · 确认列名映射")
st.caption("左边是程序理解的字段，右边选择原表中的列。未映射的额外内容仍保存在 raw_json 中。")
mappings = {}
labels = {"order_id": "订单号", "store": "门店", "date": "日期", "amount": "金额"}
for table in tables:
    with st.expander(f"{table.key}  ·  {len(table.rows)} 条记录", expanded=len(tables) == 1):
        suggested = suggested_mapping(table, config)
        mapping = {}
        columns = st.columns(4)
        for column, field in zip(columns, FIELDS):
            options = ["", *table.headers]
            key = hashlib.sha256((table.key + "|" + "|".join(table.headers) + "|" + field
                                  + "|" + rule_text).encode()).hexdigest()
            mapping[field] = column.selectbox(labels[field], options,
                index=options.index(suggested[field]), key=key,
                format_func=lambda x: x or "— 请选择 —")
        mappings[table.key] = mapping
        st.dataframe(pd.DataFrame([v for _, v in table.rows[:5]], columns=table.headers),
                     use_container_width=True, hide_index=True)

# Bind results to visible input + rules + mappings. A change hides stale downloads.
signature = hashlib.sha256(json.dumps(
    {"inputs": [(t.key, t.sha256) for t in tables], "rules": config, "mappings": mappings},
    sort_keys=True, ensure_ascii=False).encode()).hexdigest()
if st.session_state.get("signature") != signature:
    st.session_state.pop("batch", None)
    st.session_state["signature"] = signature

if st.button("校验并生成报告", type="primary", use_container_width=True):
    try:
        result, manifest = run_batch(tables, config, mappings)
        st.session_state["batch"] = (result, manifest, report_zip(result, manifest),
                                     report_xlsx(result, manifest))
    except (ValueError, TypeError) as exc:
        st.error(str(exc))

if "batch" in st.session_state:
    result, manifest, archive, workbook = st.session_state["batch"]
    st.subheader("2 · 检查结果")
    stats = st.columns(4)
    for col, label, value in zip(stats, ["输入记录", "通过校验", "待复核 / 重复", "通过金额合计"],
        [result.summary["input_rows"], result.summary["accepted_rows"],
         result.summary["rejected_rows"], result.summary["accepted_amount_total"]]):
        col.metric(label, value)
    st.caption("金额合计仅包含通过校验的记录；所有门店须使用同一币种。重复键冲突整组待复核。")
    tabs = st.tabs(["通过记录", "待复核记录", "修改记录", "运行依据"])
    with tabs[0]:
        st.dataframe(result.clean.drop(columns=["raw_json"]), use_container_width=True, hide_index=True)
    with tabs[1]:
        review = result.rejected[["order_id", "reason", "status", "store", "date", "amount",
                                  "source_file", "source_sheet", "source_row"]].copy()
        review["status"] = review["status"].replace(
            {"invalid": "值无效", "conflict": "内容冲突", "duplicate": "完全重复"})
        st.dataframe(review, use_container_width=True, hide_index=True, column_config={
            "order_id": st.column_config.TextColumn("订单号"),
            "reason": st.column_config.TextColumn("需要复核的原因", width="large"),
            "status": st.column_config.TextColumn("类型"),
        })
    with tabs[2]:
        st.dataframe(result.changes, use_container_width=True, hide_index=True)
    with tabs[3]:
        st.json(result.summary)
        st.json(manifest)
        with st.expander("查看原始字段（完整内容也在下载报告中）"):
            st.dataframe(pd.concat([result.clean, result.rejected], ignore_index=True)[
                ["source_file", "source_sheet", "source_row", "raw_json"]],
                use_container_width=True, hide_index=True)
    st.subheader("3 · 保存报告")
    a, b = st.columns(2)
    a.download_button("下载完整报告包 ZIP", archive, "ordercheck-report.zip", "application/zip",
                      use_container_width=True)
    b.download_button("下载 Excel 报告", workbook, "ordercheck-report.xlsx",
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      use_container_width=True)
    st.caption("报告包含 Excel、CSV、规则和来源清单。CSV 中以 = + - @ 开头的文本加前导单引号，避免被表格软件当公式执行。")
