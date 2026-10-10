# 固定历史接线与原核心执行链

**PROPOSED / Gate OPEN / NOT APPROVED**；`LH-Q2-CORE-IDENTITY-RESOURCE-CONTINUATION-v1`。
实现[需求](REQUIREMENTS.md)，复用既有维护 host/guest/custodian、approved-input、
核心 entry/dispatcher；不增加运行服务或可选旁路。

## 身份策略与历史保留

采用已实现的 v6 输入和 v5 guest：四个历史 quota 目录来自原计划的固定 path/dev/ino，
仅这些叶节点使用对象身份策略。由第一次既有扫描取得当前 UID/GID/mode，此后准备、
关机前、post 准入及完成均要求一致。原写位和祖先保护保持；不能把不同所有者的任意
路径纳入该策略。维护生产方及两个独立消费者必须对相同四行和前后证明严格一致。

旧 55 原件由原 custodian 连续继承同一 open-file descriptions；旧09c、旧10a归档
保持。将当前 activation 输入替换为一个固定外层 USTAR，仍占一个输入 FD：

- `prior/persistent-retained-input.tar` 是完整旧 522240 B 归档，不改字节。
- old10d 下保留五个实际维护原件、原索引、PP1 immutable freeze、独立终态、summary、
  caller 实际完成、started 记录、caller/preflight/execute 各 stdout/stderr。
- 最后一份固定索引绑定其余18成员。原件私有核对及内存编码为 **798720 B / 19成员**，
  上限 1048576 B；未创建拟执行归档文件。旧五原件不增加成不存在的 post/backup。

外层仅接受固定名称/顺序/编码/大小及冻结的 private pins；无链接、扩展头、重复成员、
追加数据或磁盘解包。解析固定旧 persistent envelope，再调用已有 activation reader；
该固定结构不提供任意递归。旧记录依旧 schema 读取，不能用新的 v19/v6 校验旧 v18/v4。
保持外层 FD 和原 recheck，完整旧逻辑、VM/source 关系和 actual completion 单独核验。

核对 marker ↔ preflight manifest，原 receipt hash ↔ coordinator completion，
caller stdout/stderr hash ↔ 实际完成记录，并核对 terminal 与原 freeze/callers。
当前只读核对已验证12个旧 caller/dependency hashes；记录实际3/0是旧失败事实，
不能当作新维护成功。两次路径读取和固定保护读取留在各自原位置，通过旧冻结/终态
准确索引保留；不声称其原件由外层或55-FD custodian连续持有。

## 历史编码与独立消费

新 resume 只加入 old10d 准确失败摘要和新11a会话。从固定 old10d marker 解开原
一层 reference，再从固定内层 old10c marker 还原完整历史；两个固定位置明确界定，
不做搜索、不接受任意引用。新 wire 只引用这一准确前代；原 canonical logical history
及源摘要必须完整还原。缺项、循环、替代字段/会话、引用丢失或格式漂移都拒绝。

接线包括 journal-growth manifest/receipt v20、preflight v19、journal-transition v20、
host-capacity-condition v21、historical-capacity-obligations/reconciliation v22；
approved-input 外层仍 v1。旧 parser 按历史版本保留，新独立 dispatcher 对原件派生的
summary、四叶身份、完整成本和实际成功完成重复验证，不能仅信 producer 自述。
新固定 source proof 为 `local-hand-q2-identity-continuation-archive/v1`，磁盘索引保持
固定 files 映射；private 索引 pin 在最终 caller 冻结，公开源码不写入原件索引。

## 入口、资源与失败

现有两个 caller 已终态，必须从其逻辑准备独立新文件；旧字节不变。新 caller 对准确
Owner决定、R/A/C/D、首次CI、安装、来源/旧原件、schema、预算及固定目的地作冻结，
actual catch/finally/result/summary 必须保留完整诊断。字段浮点规范化、截断标记和
原 reason 沿用 PR #11，不增加采集。串联 IR2 成功才允许 IR3，失败写独立终态。

新批完整核验前保留现有 dispatcher release pin；只能在 IR1 精确源码独立审查完成后
采用新的准确摘要，不能移除白名单或放行任意代码。原验收用例、管理来源、进程/写入者、
数据完整性及 boot/VM 关系全部保持。core dispatch 的额外1次原连接属于 IR3，故本批
总计最多2次维护连接加1次条件核心连接；没有预探测连接。

固定归档上限1MiB、当前 source/bundle/manifest/receipt/stream和核心载荷沿用档位2；
真实256-FD全生命周期验证仍覆盖父/子峰值与原55原件。源码/argv/包体、最终实际及允许
最大返回、全部device成本必须独立核算。新2200MiB维护中904MiB档位余量只计一次；
旧16代原额保留，原09c/10b仍是已调用未消费，不把历史成本转成可重用窗口。

没有当前guest观察，故现场是否满足身份、权限、空闲容量和静默前提仍未证明；普通
一次preflight和原同窗准入负责核对，未知停止。798720B只证明固定历史包可容纳，
不代替实现、最终依赖大小、实际完整FD/CPU/RSS或现场可运行证明。
