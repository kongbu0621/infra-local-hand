# 固定 cloud-init 授权绑定实施与发行复核

2026-10-05 +08:00。只继续核心 G1–G3；namespace/watchdog 暂停，production
`E3_SUPERVISION_UNVERIFIED` 保持。本记录的包审查不等于真实任务执行。

## 批准、源码与来源关系

直接读取原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，源 SHA-256 仍为
`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
准确 A `018bdd7f09998290f536ab5a3726ccb4123dffa3` 的三文档保持原 bytes/历史 OPEN 标签。
[Owner B](../governance/Q2_CORE_CLOUD_INIT_GRANT_BINDING_OWNER_DECISION.md) 保留本轮实际批准原文。
独立 bookkeeping-only C 为 `6013436554b51576e321ec08b0de2643efd5c3bc`，tree
`32321531cae9f60aec274600340cf027958a2e1f`，仅登记决定和 CLOSED，不含实现。

首个 D `0293c4668da10341a1ea60db6aea438bba4258e3` 直接继承 C，tree
`4e5bb05a501da7f41ce8bc808ca45baef2bfb39f`。host builder 和独立 source-aware consumer
分别验证唯一 users/name/sudo 同 mapping，再投影原 canonical grant；不调用 YAML、cloud-init
或 guest helper，不放宽 source pin、账号、权限、current sudoers/HELLO/程序身份条件。
freezer 添加第四条修订 A/B/C→D 核验，同时保留原核心及前三条修订 authority 检查。
没有新增 wire descriptor、field module、runtime 或现场配置。

回归含实际形状的脱敏输入，以及 27 组错误/歧义结构、原件摘要、派生字段和第四条
authority tamper/document drift；consumer 在 builder 被禁止调用时仍能独立验证。
合成测试替换 pin 只测试拒绝分支，真实原件另行核对。

## 准确 D 的验证

- core 回归：990 passed / 35 skipped，17.72s。
- 完整源码：4901 passed / 126 skipped，451.10s。保留报告
  `lh-core-grant-source.OKo6p0/source.xml`，SHA-256
  `0358773ec6c1af66d0711bc95715826cafa37849e58e24d0c3dc56e6cfdb038b`。
- 从准确 D 独立 clone、构建和安装：原 installed verifier PASS，94 checks / 292 commands。
  报告 `lh-core-grant-installed.EQzgrJ/acceptance/report.json`，SHA-256
  `24dcb9b23697680b9e6e4eb223bd4f0180e16014b647fed3d9df2960edb94f03`。
  测试 wheel SHA-256 `91a09c7bae135ef5e27bd990a7a6708307988f5ed82fc98eaee9560052209758`；
  它不替换现场 wheel。
- [D 的 CI 37217961194](https://github.com/kongbu0621/infra-local-hand/actions/runs/37217961194)
  在本段登记时 Linux 尚在运行，classify-change/Windows 已成功；未提前宣称全绿。

源码反向复核由结果闭包追至 `dispatch → _case_outcome → _exec_case`：admit 在安装/intent
之前；正常启动前仍检查空 ledger；H01 依赖实际 gateway/InvocationID/wait、三份业务证据及 seal；
Q4 依赖 RUNNING-only helper 和唯一 cancel event；H11 只恢复自己的原 ledger/unit/grant/deadline，
不读取业务 result 或重启业务。前项未通过不会创建下一 intent。host 仍须严格校验收到的原始成员、
实际 wait/双 EOF、六文件 fsync/回读/分配及原双钟；无证据时不将 UNKNOWN 改为成功。
这些是源码与失败回归审查，不是现场 PASS。

## 真实私有输入和准确双构建包

原 clean candidate `4b6e4a7c403362358192086b88679e1326dcb2e1`、wheel SHA-256
`ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`、projection SHA-256
`55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d` 均保持且逐字验证。
静态包为 859 members / 100 derived directories / 17452254 logical member bytes。
loader/bootstrap/dispatcher 长度仍为 2160/49102/412466 B，SHA-256 分别为：

- `6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61`
- `039fe87cc91a64c0327dc404e0ccf9728c32a1cc07e3e6fb11ed74c979f904f3`
- `06f5e5b659967a5a8375d981fe6e58401bba65b29054df50be363501f98ce79f`

保留 locator carriers、六份 horizon archives、42-file Git-pinned historical verifier、legacy frame
及 source relations 均通过。core_20261003a nonissuance 使用原固定
`9a87df50c51d863014723aa6c3c3584077429fd3` 文档，而非最新同路径 bytes。
静态门后取得原 900 秒双钟，在同一 caller 中验证真实 held anchor/writer、固定管理原件、
key relation、依赖、cwd/环境/argv/ARG_MAX；没有执行 SSH wrapper 或观察 current guest。

真实 pinned cloud-init 同 mapping 聚合现在通过。approved-input 为 311075 B，SHA-256
`f7e69c6b25d1b56217f555b240de5bace7f903249da3c6162413a57616c2cb15`；policy basis SHA-256
`1e74b18b2d4a4331a362e54d5823aba142551d38e1fe7b0519080fd889652412`。
两次完整 build/parse 相等，host parser 与独立 bootstrap parser 逐成员一致：
18111397 B，包 SHA-256 `78c84727ed903f74375abe9d98d76d8e3688926af1a0b73dd2c01d13b1b03826`。

上述是内存中的准确审查包，不是已发行现场包。该只读 caller 已结束；其 writer、origins 和 package
不得借给后续执行。本次没有做 marker/output absence，没有创建 marker 或 carrier，F1 未消费。
之前的[来源冲突与失败](Q2_CORE_PRIVATE_PACKAGE_REVIEW_20261005.md)原样保留。

## 单次交付前剩余门

在以上验证后，仅登记上述唯一 dispatcher digest；任何改变的 blob、未清空 readiness、缺源、
错误 lineage 或当前绑定仍须拒绝。该登记不自动执行，也不授权生产入口。
登记提交需冻结实际 D 并验证，原 live caller 随后从静态源开始，在自己的同一 900 秒窗口内
重新取得 held binding、构造准确包并双 build/parse，再核对唯一 marker 和五个 output 均 absent。
只有全部通过才按原 O_EXCL → 单次 carrier → H01 → Q4 → H11；任一失败停止留存，不重连/重试。
原 180 MiB/13440、276 MiB/16512、2090 CPU-s、2624 MiB/1160 pids、32/60 MiB I/O、
64 MiB/16 inode capture 及 900/800/750 秒时限保持。非 quota 池的应用记账/边界观察不冒充
全文件系统瞬时硬上限。此处不推断 guest 正在运行、支持 systemd/quota 或不存在旧 marker。

截至本段登记，真实任务执行 0，业务结果证据收回 0；后续准确发行与现场结果必须另记，不能用
本测试或审查包替代。私有原件、机器路径/身份、key、临时审查脚本和 raw machine evidence 均未入库。
