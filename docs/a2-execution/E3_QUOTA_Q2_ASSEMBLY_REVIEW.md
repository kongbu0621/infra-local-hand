# Q2 第十批：实机交接审阅与装配契约修复

2026-09-26。本批延续 `LH-E3-QUOTA-HARNESS-v1` 已 CLOSED 的隔离开发范围，
并单独提出仍为 OPEN 的 `LH-Q2-FIXTURE-PREP-v1`。两个范围不能互相代替。

## 已收到的实机交接

Owner 已交付第九批 exporter 及其实际 JSON 报告。脚本与已发布的固定字节一致，
SHA-256 为 `a5265e00222eb9cea4a9675627650c4a51adeac69c6383732a3aac0e3a3b8deb`。
本次审阅报告摘要为 `0183b985fdab6a755e96c916617484e274f38e284e575dcb298349d44ccba1e9`。
原始报告及主机身份保持私有，本文只发布结果分类。

报告为 `local-hand-q2-host-export/v1`，状态 `EXPORTED`，28 项所选检查均为
`OBSERVED`。这些检查关联所选 Q1 配置字节、声明的 guest、程序摘要、挂载对象及
原目录身份；没有重做 quota 查询，没有证明完整源码树洁净或独立管理权限，也没有
枚举全部 Q1 历史域。报告自身准确保留 `Q1_EVIDENCE_ONLY`、
`complete_q1_domain_inventory=false`、`fixture_generated=false`。

报告的九组 Q2 输入均为 `NOT_DELIVERED`：新根分配、普通 policy/空账本、普通
user manager/委派、原 supervisor/独立停止、容量声明、空输出与声明目录、原操作
预算、专用进程父组，以及同一源码的安装产物。因此无需再让 Owner 重复读取旧库存；
下一项实际工作是准备新 fixture，而不是将旧 Q1 对象改名为 Q2 输入。

## 两个已确认的代码问题

1. 上一批公共 source `303f9ca027a883f62763ed23279afd3174293b5e` 的
   [CI run 36222011920](https://github.com/kongbu0621/infra-local-hand/actions/runs/36222011920)
   在 Ubuntu 上为 1486 passed、1 failed、12 skipped；Windows 和分类任务成功。
   失败测试假定调用者可以用 `O_NOATIME` 打开 root 所有的 `/`，非 root runner
   实际得到 `EPERM`。本批只修正测试对实际拒绝路径的断言，并单独验证可写祖先、
   不降级重试及非法路径提前拒绝。exporter 的保护规则没有改变。
2. 三阶段 chain 的历史 `RETAINED_BINDING` 要求 evidence store 复用 preflight
   根；真实 `Policy` 却要求 `bootstrap_evidence_store` 与全部执行根分离。
   合成 fixture 掩盖了两条合同无法同时满足的问题。本批修复须使用 policy 固定的
   独立 store，并以真实 policy 校验和原 reservation 贯通检查证明该绑定；不得
   放宽普通 policy 的路径/inode 隔离规则来让旧合成 fixture 通过。

## 一次完整装配所需的新增范围

三份 [准备文档](q2-fixture-preparation/IMPLEMENTATION_PLAN.md) 给出具体影响：
在已提供的隔离 guest 中建立专用普通账户及 manager/委派、两套各三个新 slot 根和
一个独立 evidence store、受保护的安装与管理记录，以及外层独立监督入口。
preflight/business 共用第一套三根，evidence 使用第二套三根，store 独立：共七根。

现有 supervisor 要求自己的原 MainPID、InvocationID、cgroup 和期限已经准确绑定。
静态 JSON 无法预言这些未来运行身份；准备范围必须包含同 MainPID 的实际绑定入口，
由独立外层 owner 保留客户端退出、双流 EOF 和停止证据。不能用新启动时间延长原期限。

根 `AGENTS.md` 明确把 host provisioning 排除在已有 closure 之外，故新范围仍需
Owner 对具体文档基线的一次决定；本批不把“继续修复”解释为自动扩大该范围。
已授权的 source/test 修复与验证继续完成，不因新范围 OPEN 而停止。

本地验证结果、准确源码及公共树映射随本批单独记录。源码或模型通过不代表实机
Q2/Q3 通过；历史 UNKNOWN/INCOMPLETE 和生产 `E3_SUPERVISION_UNVERIFIED` 均保留。
