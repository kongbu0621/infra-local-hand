# 核心 host writer 传输：实施方案

Authority、R、OPEN 状态和准确边界见 [需求](REQUIREMENTS.md)，责任划分见 [架构](ARCHITECTURE.md)。
本 scope 尚无 Owner B/C，不能新增该范围 source/test/schema 实现。原 CLOSED D1–D4 不受影响工作可继续。

1. 准备三文档准确 A 及独立 OPEN 登记。Owner 对 R/A 与 T1–T3 准确批准后，保留原文 B，
   单独提交 bookkeeping-only CLOSED C；三文档历史 OPEN 字节不改；新实现 D 以 C 为祖先。
2. T1：改 `q2_core_delivery_contract/package/freeze/entry` 与 standalone `bootstrap/dispatcher`：
   v3 strict schema、唯一 entry.writer、原 held binding 同值检查、准确 marker v2 重建和
   BIND/session/host marker 交叉验证。同步各既有纯结构/隔离回归；不创建现场 marker 或连接 guest。
3. T2：完成需求全部负例，以及全真实效果尚缺时仍拒绝 release 的回归；bootstrap/dispatcher
   实际 blob 不超过原大小。验证原生产 guard、空 ledger、H11 原身份和一次性逻辑未弱化。
   必要 source/installed suite、独立审查和原 D4 的其它缺项仍须完成，不把 T2 等同整个 D4。
4. T3：冻结最终准确 D/tree；offline source-lineage 同时证明本 C 与原 C、manifest 的同一 D，
   并绑定本 A/B/C 的准确记录。按原顺序在原 900 秒 origin 内双 build/parse 私有 package，
   复算每个 field blob、writer、manifest/package/marker 预算和 release digest；失败不更新 release。
   不在批准时预写未知 D/hash，不在已有 HELLO 后替换包。

T3 完成也不是新现场授权。原未消费 F1 仅在全部原门及本修订门通过后才条件继续。
同一次 carrier 内 H01 语义 PASS 后才 Q4，再 H11；失败立即保留。若 marker 已存在或发现新义务、
真实身份/资源/时限不匹配则停止，不能通过本修订重新取得一次运行。

报告须分开：T1/T2/T3 状态、准确 D/package、marker/request/case 次数、真实任务/退出/结果/证据、
live acceptance。未观察到的事实继续 UNKNOWN，未执行写 NO；安装子进程测试不写成业务任务已运行。
