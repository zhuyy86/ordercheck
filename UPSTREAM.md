# Upstream / 上游来源

- Original project: Dataset Cleaner
- Original author: Dendi Rivaldi (Louce)
- Original repository: https://github.com/Louce/dataset-cleaner-and-analyser-tools
- License: MIT; original LICENSE retained unchanged.
- Baseline commit: `7ca63acf2d2719fc3ffa36a386ff7172e67a5251`
- Retrieved: 2026-09-08
- Local extension: OrderCheck / 订单批处理工作台, developed with Codex assistance.

原作者的单表清洗 DataCleaner、可视化和原界面保留；新增的订单入口接入原 DataCleaner 数据/历史管理，调用新的严格订单校验模块。新增文件负责批次读入、列映射、规则配置、异常隔离、跨文件重复判定、可追踪导出、中文界面与 CLI。具体变更和测试以 Git diff 和 TEST_REPORT.md 为准。

项目属于 extension / adaptation，不是从零原创全部代码。未宣称上游背书，也未将上游用户量、性能或商业成果算作本项目成果。

Baseline reproduction：可在上游仓库的 `7ca63acf2d2719fc3ffa36a386ff7172e67a5251` 提交查看原文件。当前公开仓库采用直接发布的完整代码快照，并通过本文件保留固定来源记录。
