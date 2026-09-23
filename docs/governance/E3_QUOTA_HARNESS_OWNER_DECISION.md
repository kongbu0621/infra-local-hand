# E3 quota/harness Owner 开工决定

- Decision authority / speaker：Owner，本会话用户。
- Record event ID：`LH-E3-QUOTA-HARNESS-CLOSURE-20260923-01`，仓库事件标识，不冒充平台消息 ID。
- Observation time：`2026-09-23T16:19:16.364002+00:00`，executor 记录已收到决定的时间，不声称是原始发信时间。
- Source：Owner 紧接下列准确基线/范围请求的直接答复。
- Stable retained reference：本文件在独立 CLOSED 登记 C 中的副本；准确 C 由 Git history 定位。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，根 AGENTS 固定的直接来源，executor 已读取。
- A：`415327ebdcc251bb055da9931a7a88990f750b7a`。
- Authorized implementation scope：`LH-E3-QUOTA-HARNESS-v1` 的隔离开发及明确交付 fixture 上的测试。

## 保留的直接上下文

助手上一条请求原文：

> 这里需要你确认一次：新增组件涉及主机权限，仓库 `AGENTS.md` 引用的门禁规则要求先批准准确的新方案。**是否同意按[已提交的基线与范围](https://github.com/kongbu0621/infra-local-hand/blob/1c7f49e7d9be0bbe480c8ddd2239e8bdff33adc7/docs/governance/E3_QUOTA_HARNESS_BASELINE.md)，关闭这项变更的开工门禁，开始隔离实现？** 该范围不包含 GX10 现役服务部署或切换。

该固定链接明确给出完整 R、A、scope、三份文档、权限变化与分阶段实施顺序；
所引用记录在本次决定前已存在于 main，不追随后续可变内容。

Owner 随即回复，完整原文：

> 同意，然后呢？需要我做什么？

## 上下文绑定及范围

“同意”接受紧邻请求中固定的 R/A 和范围；后半句询问下一步分工，不撤回批准。
本记录保留其原文，不合成 Owner 未说过的长句，也不将批准扩大为主机安装或生产使用。
据此仅将上述准确基线下的 scope 登记为 CLOSED。

允许独立管理侧固定对象 quota observer、有界无特权客户端、准确事实/原分配/预算/代次绑定，
以及真实 bootstrap/helper/reader test-only harness 的隔离实现与验证。
执行顺序为 Q1 最小可行性、Q2 绑定/预算、Q3 正常链、Q4 故障/恢复。
没有已交付隔离 fixture 时，可以完成源码和合成负例；Q1 实测仍 BLOCKED，不假定成功进入 Q3。

GX10 账户创建、特权服务安装、委派、mount/quota 设置、现役切换及 E4–E6 不在本次批准内。
普通作业隔离与生产 `E3_SUPERVISION_UNVERIFIED` 保持；实现/CI 通过不等于 E3 PASS。
后续主机操作须先形成准确、可审阅的私有装配与影响交接。

本 C 只保存批准副本及状态登记，不修改 A 三份权威文档，不加入源码、测试、依赖或运行配置。
实现 D 必须以 C 为祖先。原 S1、Ledger A2 及不受影响的 E1–E3 范围保持；实质变化仍按原规则处理。
