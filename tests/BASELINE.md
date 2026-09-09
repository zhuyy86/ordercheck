# 改造前检查说明

目标提交：7ca63acf2d2719fc3ffa36a386ff7172e67a5251。
初次执行 tests/test_upstream.py 前，不修改任何 src/ 文件。
检查范围：原版 Streamlit 初始页面无异常；三行数据的缺失值识别、按中位数填补、保留原表、历史记录、Excel 保存并重新读取；有效/空 CSV 判断。
这是限定范围的 baseline，不等于上游所有功能都通过全面测试。
实际结果和运行环境统一记录到 TEST_REPORT.md。
