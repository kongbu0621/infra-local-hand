# Journal proc 限制的精确诊断修复

基线 `170bb6ed912f3706f9925f42c5ceb85a37d72b11`。本次在已有 CLOSED 开发范围内完成离线
诊断修复；没有再开 DR2、sudo/writer 现场调用、SSH 或维护。历史结果以
[已消耗 DR2 记录](Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_FIELD_20261006.md)为准：
`GROWTH_PROC_LIMIT` 的实际触发分支和当时计数仍 UNKNOWN，不能由本次测试补写。

## 已确认问题及修改

原扫描器的多个不同拒绝条件共用 `GROWTH_PROC_LIMIT`。前一轮已保留 reason/errno 的传递，
但该通用 reason 本身仍没有分支、数值和进程上下文，无法指导针对性处理。
本次只在原拒绝点利用已经取得的数据生成有界诊断；不增加任何观察或继续扫描。

失败 reason 格式：

```text
GROWTH_PROC_LIMIT_{STAGE}_N{observed}_MAX{limit}_P{pid}_T{tid}
```

| 固定阶段 | 原上限 | 上下文 |
| --- | ---: | --- |
| `PID_ENTRIES`、`PID_ENTRIES_RECHECK` | 32768 项 | PID/TID 不适用 |
| `TASK_ENTRIES`、`TASK_ENTRIES_RECHECK` | 32768 项 | 所属 PID |
| `FD_ENTRIES`、`FD_ENTRIES_RECHECK` | 65536 项 | PID/TID |
| `TASK_TOTAL` | 65536 次 task 访问 | PID/TID |
| `FD_TOTAL` | 262144 次 FD 访问 | PID/TID |
| `PID_STAT_BYTES`、`PID_STAT_BYTES_RECHECK` | 16384 B | PID |
| `TASK_STAT_BYTES`、`TASK_STAT_BYTES_RECHECK` | 16384 B | PID/TID |
| `FDINFO_BYTES`、`FDINFO_BYTES_RECHECK` | 4096 B | PID/TID |
| `MAPS_BYTES` | 1048576 B | PID/TID |
| `MAPS_TOTAL_BYTES` | 67108864 B | PID/TID |
| `MOUNTINFO_BYTES` | 1048576 B | 源码 fallback；实际 writer 使用既有 kernel reader |

共 17 个固定阶段；非数字 FD 名称另报 `GROWTH_PROC_FD_NAME`，仍先于 `stat` 拒绝。
`N` 是首次拒绝时的已观测数量/字节数，不是完整目录、文件或宿主总量。单文件最多已读至
cap+1；不会补读来计算完整缺口。累计 maps/FD 继续逐 task 计数，不去重或跳过。
PID/TID 只接受最多十位 ASCII 十进制并规范化，`0` 表示不适用或不可安全编码，不冒充实际 PID 0。
不回显路径、非数字名称、maps/cmdline/environ、进程标题或任意异常原文。

生成 payload 显式包含同一诊断函数。五字段失败 schema、请求绑定、160 字符 ASCII reason、
errno 校验和父层传播保持不变。没有提高上限、改变扫描覆盖/读取 flags/顺序/次数/期限，
没有增加权限、重试、现场预算或维护次数。源文件逗号后的机械空白压缩前后 AST 相同；
独立 AST 比较确认本次诊断函数以外的节点与基线相同，字符串未被格式操作修改。

## 验证

Python 3.12.14，十四文件相关回归 **598 passed、3 skipped，21.22s**。
新增 **163 项**隔离测试覆盖源码和真实生成函数、原阈值的等值通过/首次超限、初读/复核、
累计 task/FD/maps 的实际循环、PID/TID 编码及 generated entry → 父解析器 → observe →
CLI safe_reason 全链路。仅合成数据，不对原宿主或 VM 进行读取/调用。

三个 SKIP 为云端 PID/proc 身份不匹配、缺少 native qcow2/ext4 工具、真实普通身份不可用
（errno 1）；它们不计 PASS，也不替代真实宿主验证。源码与生成 payload 的内存编译、
`git diff --check` 通过；准确发布提交的 CI 另行记录，不沿用旧候选的成功结果。

| 源码 | 字节 | SHA-256 |
| --- | ---: | --- |
| `q2_journal_growth.py` | 65195 | `07c36ee7c8c48abfb81fb5b369551ea42ac1ef357b1f2c93d396196ca89efb29` |
| `q2_journal_growth_guest.py` | 65453 | `966e1b0f2c0673d2fb1a18600022f1a8d92cac2965a12d102045537d3f43d0a2` |

两源码仍各不超过 65536 B；生成 payload 为 24528 B，仍低于 32768 B。
本结果解决未来诊断缺失；不表示实际超限原因已解决或扩容已完成。任何新现场窗口仍需准确授权。
