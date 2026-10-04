# 核心 host writer 传输：架构

Authority、R、OPEN 状态、范围及不变项见 [需求](REQUIREMENTS.md)。本文不授权实现。

唯一数据流：原 held writer → 原 local binding → v3 package.entry.writer →
guest 重建原 marker v2 → BIND consumption 摘要相等 → session 摘要/长度 → host 实际 marker 比对。
host 拥有 writer 的当前观察和持久化证据；guest 只验证收到的同一个冻结 preimage，
不能声称独立观察 host，不能以自己的 namespace/UID/PID 代替。

职责与边界：

- host contract/package/freezer：保留原 writer 严格结构及锚点关系；只接纳同一原始时限内的 held
  binding，构造 v3 唯一新字段；独立 builder/parser 比较完整 package，随后保持既有 absence/marker 顺序。
- standalone bootstrap：固定 v3 顶层及 entry exact key、writer 类型/范围/4096 B 限额；只读取同一
  package，不增加 field member、进程、请求、输入帧或握手轮次。
- standalone dispatcher：从 manifest/BIND/package 自包含重建 marker v2，不额外 import 未验证模块；
  校验摘要后再构造 session，后续完整 admission 与 H01 intent 顺序不变。
- host return verifier：独立重算并逐值比较实际 marker、package、BIND/session，原 live finalizer
  仍负责真实 wait/EOF、六文件 fsync/同 inode 回读、分配与时限，盘上 COMPLETE 不自证成功。

版本变更采用 strict v3，避免同一 v2 名字接纳两个 exact shape；BIND/wire magic 未变不构成降级依据。
package SHA 覆盖新增 writer，marker 的 package SHA 与 BIND 的 consumption SHA 形成单向关系，
不将 marker SHA 回填 package，因此没有循环摘要。

本协议只补字节传输，不补当前 guest policy/容量/身份准入，也不证明所有 D2 效果。
任何错误沿原 NOT_ISSUED / STOP_AND_RETAIN 规则处理。旧包只保留作历史证据；不能回退执行 v2，
不能在 HELLO 后重冻 v3，不能重发消费过的批次。raw writer 只留在原私有包/marker 范围，
公开报告仅留源码/版本、摘要和脱敏结论，不新增机器原始证据披露。
