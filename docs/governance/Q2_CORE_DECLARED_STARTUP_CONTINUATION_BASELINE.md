# 声明目标限定维护：待决基线

**PROPOSED / Gate OPEN / NOT APPROVED**。没有新的 Owner B、独立 C 或实现 D。
Scope `LH-Q2-CORE-DECLARED-STARTUP-CONTINUATION-v1`，DS1–DS3。

R 沿用 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 及 AGENTS 的直接可读来源、
完整性、Owner authority/mandate、无例外和变更规则。
准确三文档 A：`2b13dd653ca19eaaf46a18e6ffc3f447b62eee59`；
tree：`c686e5dbf5454f682603f9b7575cc4292402be34`；
父提交：`b4dde5d387a9206a41925a2d051b51eb74fb0235`。
A 仅新增下列三文档，没有运行源码、测试、配置或新窗口。

| 文档（docs/a2-execution/q2-core-declared-startup-continuation/） | bytes | SHA-256 |
| --- | ---: | --- |
| REQUIREMENTS.md | 6858 | 4ae983f96c2a3e25ebf435b8db2af9abc487c570702a4f8bd7614dc7ac5eb392 |
| ARCHITECTURE.md | 9670 | 61b543eb04810047e9a0f9e0fbeab032de6943792b9e3ca5d4653393da147942 |
| IMPLEMENTATION_PLAN.md | 5327 | 965f841919a015e0f6e6212807fe710c45be21c51b134451d92fe199123e678a |

## 为什么改变推进方式

上次 QI1 的准确来源接线已生效，实际清单为 19/7/7；执行 D fa30146 的首次 CI
三个 job 均成功。08e 被另一服务的直接路径引用挡住，核心仍 NOT_RUN。
当前策略要求全量启动定义预先声明，历史来源却明确不是完整 inventory；每次补一条
没有消除该依赖。现有公开诊断不能证明另一服务活动或无害，本方案不作该推断。

两项独立源码审查确认，全单元/模板枚举仅服务于维护启动覆盖，与 H01/Q4/H11 无
直接功能依赖；声明目标静止、domain 属性、cgroup、当前进程/FD/mmap writer、
持久数据、目标身份、关机/备份/扩容与容量保护是可保留的独立检查。
新方案只去掉全量启动枚举，改为准确声明域检查；明确减少未知自动启动的静态观察，
依赖 Owner 接受并由执行者确认的管理前提，不能声称等价或连续排除。

三文档已完成独立范围/协议/历史兼容/费用及风险表述复核；文件链接、摘要与 diff
格式已核对。没有运行新程序测试或现场动作；现有 QI CI 不作为新 DS 实现的验证。
DS1 必须用实际静态输入验证 marker 等原大小上限；其它现场准入仍可能失败。

## 一个待决批次

请求 Owner 对准确 A 作一次决定：接受保证缩减和管理前提，关闭 DS1–DS3，允许
限定文档/脱敏记录及旧 08e 五件最小索引披露。DS1 先完整实现验证两侧；DS2 一次
新 08f 维护；完整成功后 DS3 发原 07a 核心 H01→Q4→H11。私有原文不公开，
八旧窗口及 UNKNOWN 不更改，失败不重试、不补采、不清理或另开窗口。

本记录是 OPEN 基线定位，不是 C。Owner 决定之前不改新范围源码或配置；获准确 B
后先单独登记 C，再实现 D，范围内不逐子步骤再次审批。不要重新查询另一服务、
泛查历史归档、重做 C10 定位或将本方案拆为新增诊断支线。
