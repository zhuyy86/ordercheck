# OrderCheck KPI 汇总

```powershell
python scripts/kpi_summary.py outputs/accepted.csv -o outputs/kpi.json
```

脚本读取 OrderCheck 生成的 `accepted.csv`，输出总订单数、有效金额行数、金额合计、平均客单价，以及按门店和日期的汇总。金额使用 `Decimal` 计算，避免二进制浮点误差；坏金额不会被悄悄计入合计，而会进入 `amount_error_rows`。

输出是稳定的 UTF-8 JSON，可继续被 Excel、BI 工具或后续 API 读取。脚本只使用 Python 标准库，不依赖网络，也不会修改原始 CSV。

金额限定为 0 至 1e12，最多两位小数；也接受正确分组的千分位，例如 `1,234.50`。`NaN`、无穷大、科学计数法、错误分组和超过两位小数的金额均计入错误行，不参与合计。CSV 必须包含不重复的 `store`、`date` 和 `amount` 表头，记录列数须与表头一致。文件或结构错误返回退出码 2，并保留已有输出文件。
