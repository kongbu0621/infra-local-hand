# GX10 E3 输入确认包独立核验

日期：2026-09-23。交接基线 `5257f42d1358be67b6d13377d99ef3465131bd54`。
本记录核对收到的原始文件，不宣称审阅者直接连接或观察了 GX10。

**结论：本次有界确认支持 E3 输入为 NOT_PREPARED。结束现场盘点，转入实现方案。**
这不是 E3 运行失败，也不是 E3 PASS；不能自动采用桌面账户或现役 S1 账户。
先前 nsfs 解析修复的实机验证结论保持；本次没有重跑探针、quota syscall 或三单元 harness。

## 收到的证据与独立校验

| 项目 | 独立核验值 |
| --- | --- |
| ZIP | `infra-local-hand-gx10-e3-input-confirmation-5257f42-evidence-20260923.zip` |
| 字节数 | 24,934 |
| SHA-256 | `3385e31c2ba954ac3104e495eb960023fd3b0d2b9e77a6b7835dcea9dcc96603` |
| 成员 | 44，含 MANIFEST.json |
| MANIFEST SHA-256 | `1b1095b87ecda7c21f93cbdf466b0c73365ffc49c24881734c2d63df88385d51` |
| 完整性 | 44 个成员 CRC；43 个 payload 的大小、SHA-256、准确成员集合；名称唯一、相对路径、无链接或加密成员 |
| 命令 | 13 组、26 份双流摘要；8 组 exit 0，5 组 exit 1，原值保留 |
| 交接连续性 | 包内交接文字与前轮交付逐字节一致；前轮 audit ZIP 的大小、摘要、成员数及 manifest 摘要一致 |

包内 identity 与 manifest 一致，外置 verification 的值与本次独立计算一致。
只解析成员，不执行上传的脚本或命令。独立审计程序、原始审计双流和核验 JSON 私有保存。
摘要只能证明收到的文件相互一致，不能单独证明宿主事实或无任何未记录操作。

## 输入与失败语义

六项必要输入均未形成可准入依据：专用账户/UID、该账户的 user manager、专用 slice、
对应 cgroup、与现役环境的隔离关系、专用委派及 controller。slot roots、project hard quota、
evidence store 容量和绑定仍为 UNVERIFIED；本任务不要求 NAS target。
共享用户 manager 的可达性、controllers 和 cgroup.procs 可写性不能升级为专用 E3 输入。

| exit 1 记录 | 可支持的判断与限制 |
| --- | --- |
| active-service-account | 前面的账户查询有输出；最后 loginctl 明确报告未登录且未 linger。不能解释成账户不存在 |
| current-user-manager-and-slices | 组合命令前部有 manager/slice 输出，末尾 unit-file 查询无输出；保留组合 exit 1，不给全部子命令补写 PASS |
| lhj-unit-files | 指定模式查询返回空双流和 exit 1；不扩大为全机不存在任何测试配置 |
| related-system-slices | 管道最终匹配器无匹配；没有 pipefail，也未分别捕获上游 systemctl 退出码，不能独立证明其成功 |
| tracked-live-config-declarations | 指定 tracked 配置格式和字段无匹配；不代表扫描了私有配置或所有可能格式 |

上述限制不要求再做一轮无目标盘点：当前没有被指定且可核对的专用输入，已足以保持 NOT_PREPARED。
现役服务属性快照报告仍运行；这是记录时点的观察，不是全过程服务监控证明。
私有账户、路径、进程及完整命令记录不复制到 Public。

## 准确源码边界

现场 checkout 保持 `475cfcbd79c2f8eb151bb4f0b385dbcc22ad3179`，
origin/main 与交接基线为 `5257f42d1358be67b6d13377d99ef3465131bd54`，当时落后三个提交。
工作区未 reset 或更新。日志中的 AGENTS、实现缺口文档摘要与两版本均一致；
宿主 runbook 摘要对应旧 checkout，不能写成读取了新 main 的全部文件。
准确新交接文字已单独逐字节核验，故这一区别不改变本轮“输入未准备”的结论。
探针 `88b78b6ef908026b763f307c4d78ab3d0c0e6521` 是前轮来源，不是本轮执行源码。

## 下一步

先审阅 [quota 与真实 harness 的需求](e3-quota-harness/REQUIREMENTS.md)、
[架构](e3-quota-harness/ARCHITECTURE.md)和[实施顺序](e3-quota-harness/IMPLEMENTATION_PLAN.md)。
新增受信权限组件属于明确的架构变更，按根 AGENTS 的受影响范围处理；本记录不作 Owner closure。
在准确实现、测试入口和隔离装配清单形成前，不再要求现场重复运行无参数探针，也不进入 H01–H13。
