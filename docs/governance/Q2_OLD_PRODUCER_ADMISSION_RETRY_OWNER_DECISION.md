# Q2 旧生产者准入解析失败后的单次替代批次：Owner 决定

- Decision Authority / Owner：当前项目 Owner（本工作会话用户）。
- 决定记录时间：2026-10-02 12:59:30 +08:00（紧随准确用户回复取得的本机时间）。
- 本地可追溯事件：`LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-CLOSURE-20261002-01`；
  不是平台消息 ID。
- 稳定来源：本文件保留本次准确 Owner 回复与紧邻确认请求，供 Owner 核验。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本次 executor 已直接读取
  private companion source 的该固定 commit，规则内容 SHA-256 为
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`，与本地采用记录匹配。
- Documentation A：`68424df2ddbf812b9479ffa7a64dcaa59a2a9f76`。
- Scope：`LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1`，P1–P3 实施与 P4 合同/资格验证；
  不含 `20261002a` 现场运行或可现场 ZIP 的生成/执行。

## 紧邻确认请求

助手给出准确 R、A、scope、trusted-storage/no-same-UID-tamper 前提、四字段解析修复、
两项固定内核视图 reader 的 consumer 窄集成，并明确区分 P1–P3/P4 合同资格与后续
独立现场 P4。请求 Owner 如批准则完整回复同一决定文本。

## Owner 准确回复 B

> 按规则 R 10d2a5c827964989f41ca6e8eeac3d44de6d0f04，批准文档基线 A 68424df2ddbf812b9479ffa7a64dcaa59a2a9f76 的旧生产者准入单次替代批次方案（LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1），接受该 A 披露的 trusted-storage/no-same-UID-tamper 治理前提，批准四字段解析修复及两项固定内核视图 reader 的 consumer 窄集成，关闭该范围 Gate，并授权 P1–P3 实施以及 P4 合同/资格验证；不发行 20261002a 现场运行，不授权生成或执行可现场 ZIP。

## 决定边界

本 B 明确绑定上述 R、准确 A 和 scope。Owner 接受 A 披露的可信存储及
no-same-UID-tamper 外部治理前提；这不把 0700/0400 转换为技术性防回滚证明。
授权实现严格限于：

- 私有 `old_producers.py::_show()` 解析后，仅为 `ExecStartPre`、`ExecStartPost`、
  `ExecStop`、`ExecStopPost` 四个可省略的空数组属性补空字符串默认值；
- 把 CLOSED K A/C/D 的专用 reader 窄接入本范围新 consumer，且只在准确 ordinary
  identity guard 后读取 boot_id 与本进程 mountinfo；旧 K 的包、批次、marker 和
  现场授权不转移；
- 按准确 A 完成 P1–P3 的实现、隔离测试、合同 fixture、非执行原型与资格验证。

已消费的 `20261001e` 保持 `FAILED_RETAINED`；旧产品实现
`1a900e4a38e9567655f21cbf3c3f17941de1a8d5` 不冒充本范围 D。当前 H07 与消费/evidence
双 parent 的文件系统、峰值和持久资格仍未闭合，因此 `field_ready=false`、
`allow_run=false`，不能生成含可执行 `TASK.txt` 的现场包、创建 host 消费对象或连接 guest。
未来 P4 仍须 Owner 另发独立稳定 event/ref，准确绑定 A/C/D、包和 evidence 限制；本 B、
C/D、CI/READY、ZIP 或裸“继续”均不能替代。

本文件与根 `AGENTS.md` 的 CLOSED 登记共同构成独立 bookkeeping-only C。A 的三份文档、
其历史 OPEN 标签及 OPEN baseline 登记保持字节不变。后续实现 D 必须以本 C 为祖先。
本 C 不包含 production/test source、可执行 prototype、runtime configuration、依赖或现场操作，
也不消费批次或 P4 event。
