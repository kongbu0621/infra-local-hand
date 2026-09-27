# Q2 host 窗口消费：组件实施与现场阻断复核

本轮已登记 Owner 对准确 A 的批准，并实现专用合同、消费记录、共同账单与传输/封存组件。
**现场接线与 H5 尚未完成，入口在现场读取、双钟窗口、消费记录和远端探测以前 BLOCKED。**
原因是执行前提缺证，不是重复等待同一 A 的批准。未消费原唯一窗口，未发行 owner。

## 准确授权与保留项

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，原规则 SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- A：`8402f0cc82d8a0ac0b9a56716bf276f41cafea37`；三文档字节及历史 OPEN 标签不变。
- B：[准确 Owner 决定](../governance/Q2_HOST_WINDOW_CONSUMPTION_OWNER_DECISION.md)，
  event `LH-Q2-HOST-WINDOW-CONSUMPTION-CLOSURE-20260927-01`。
- C：`271c07cd16140aa5942dcf3fad468003c58b6b0e`，只包含 AGENTS 与决定登记；D 单独继承 C。
- 原 startup/对账批准链、旧 v1、冻结 runtime `b49d3df3d1e76813faf08e59ab4975e25279c2fc`
  与原 wheel 均不修改。不新增依赖，不释放其它承诺，不扩预算。

D 的源码逐文件摘要与本轮实际测试结果见
[validation.json](evidence/q2-host-window-implementation-20260927/validation.json)。
固定 D 后的真实私有来源核验另作后继证据，不用自引用假 D。

## 实际交付范围

| 阶段 | 本轮成果 | 尚未证明的部分 |
| --- | --- | --- |
| H1 | 准确新权威、两固定原件的 AST/JSON 解码、不可由 attempt 改名的消费位置、原双钟/计划/config/工具摘要绑定 | wrapper 完整 bytes 与已授权来源的现场对应 |
| H2 | held fd、固定单目录/单意图、排他创建、同步与实物复核、既存/部分拒绝；独立进程竞争与同步故障隔离验证 | 实际 host 的文件系统、分配峰值与掉电持久性；正式入口仍拒绝 |
| H3 | host/guest 共用原 capture 上限；guest LIVE/ACK/receipt/collector 字节关系；后续捕获实物 seal 原语 | 完整真实派发接线及准入未完成；没有已封存 host/guest 现场结果 |
| H4 | 受影响组件和旧接口定向回归；真实临时文件/进程测试与显式模拟资格分开记录 | 隔离测试不替代 guest 硬截止、独立停止、真实 FS 资格 |
| H5 | 准确 D 的私有离线核验材料；只允许 `--check-offline` | NOT DISPATCHED / NOT READY；无运行选项，无新窗口 |
| H6 | 公开脱敏索引、私有原件和缺项继续保留 | Q2/Q3/production 均未通过 |

消费组件只支持能取得明确本地资格的窄文件系统分支；无试写、删除试探、时间戳恢复、
换名或接管。测试中的文件系统资格与现场事实门替代只用于隔离 syscall 验证。
当前容器的 overlay/volatile fsync 不能作为真实持久性 PASS。
窄 ext4 几何检查只推导对象映射块上界，不证明 allocator/journal 的完整同步峰值；
当前固定事实阻断也防止将这一局部推导用于真实落盘。

host 捕获文件 raw 总量另保守限制为 3 MiB，marker 仍按原 16 KiB logical / 64 KiB
allocated / 4 inode 子预留单计，二者都在原共享 64 MiB / 4096 inode 内。
seal 仅列实际 held 成员的元数据和摘要，不重复嵌入双流 raw，也不引用自身摘要。
它的证明范围是 `HELD_FILES_ONLY`，不能替代原管道 EOF、原 client exit、远端 stop 或树空。

传输组件保留单 stdin 帧与唯一 ACK；所有脚本/header/ACK 仍合计不超过 16 MiB。
整配置 gzip 的解压硬限 32 MiB 是 RAM 解析界限，**不是** stage、磁盘或传输额度增加。
stage 的 `reconciliation-inputs.json` 仍不得超过原 16 MiB。

## 不得由模拟或新布尔值补齐的缺项

1. 两份准确旧 clock anchor 只有 guest boot、guest BOOTTIME 与 host MONOTONIC；没有历史
   host boot 与 host BOOTTIME 对应。当前采用的 host boot 不能倒绑定旧采样。
   原 `RuntimeMaxSec=270s` 配置无法单凭这些材料证明首次探测及运输/排队都受原绝对截止覆盖。
   `remote_deadline_proof` 复算真实原件后明确拒绝；不接受调用者自报 ADMITTED。
2. 返回的旧 host 留存材料未给出完整 actual allocated、未释放 future 的准确来源以及
   原生 SSH/管理 audit 的可证上界。不得补零、重复抵扣 guest owner pool 或自动释放旧义务。
3. 精确 host attestation 中的其它当前元数据不自动获得新采用用途。新 A 对该原件采用的
   host boot 用途不能扩成 wrapper 全文件执行证据；wrapper 原 bytes 与完整来源仍缺。
4. 当前工作容器不是授权 host，也没有可调用的既有私有 host 连接。未使用猜测的 SSH 参数、
   主机或新凭据。实际 host 存储资格、既有 Q1 owner map 和完整现场 inventory 仍需证明。

host `run_host`、guest bootstrap/backend 构造及 collector CLI 都在现场作用前拒绝。
纯来源/账单/marker 字节验证只证明其限定关系；不是绕过现场事实门的许可。
首探测硬期限或来源采用若必须改变既有机制，先按原 R 明确受影响方案，不能通过更换
入口、新增 supervisor、增加日志设施或刷新时钟悄然扩展本次批准。

## 独立复核修正

已修正动态 helper 导入时的代理构造、marker scan API、140 秒准备期限误用于
140–300 秒终态复核、collector 在阻断前读取现场、host/guest 身份投影差异与
LIVE/READY 的 host 四摘要绑定。最终验证只覆盖修正后的准确源码。
旧两次 INCOMPLETE、历史 atime 未证明、原独立停止/EOF 证据界线均保持。
