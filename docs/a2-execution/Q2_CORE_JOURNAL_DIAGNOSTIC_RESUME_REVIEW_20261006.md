# Journal 诊断替代窗口：DR1 验证与准确候选

2026-10-06（Asia/Shanghai）。**DR1 完成；DR2 尚未开始。** 本记录登记源码、静态输入与发布验证。
旧窗口保持消耗，历史 writer 根因及 root payload 是否执行仍 UNKNOWN。

后续状态：Owner 返回的 [DR2 现场截图结果](Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_FIELD_20261006.md)
已将本记录冻结时的 NOT_STARTED 更新为 CONSUMED / FAILED；本文件的原零计数仍仅描述 DR1 交接时点。

## 准确链

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。本执行者直接完整读取固定规则，
  并验证原 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- A：`ef46ac169fd9084875cb5c5148a9c4985ace680c`，仅
  `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v1` / DR1–DR2。
- [准确 B](../governance/Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_OWNER_DECISION.md)：
  `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-CLOSURE-20261006-01`。
- 独立 C：`65026c8c7722bc487c317d392b50b017a7350dee`，仅 AGENTS.md 与 B；没有实现。
- 准确候选 D：`deab8acdabf0d35294f55fa87f2bc86d542fdf2e`，C 的直接子提交；tree
  `ee9d848085ad89ec953b9f102da8217bf193c147`。C 与 D 已分别非强制发布到 main。

三份批准文档与 A byte-identical，历史 OPEN 标签不变。既有诊断修复
`aba18e33f79295f3df1964606e389297d1a8a26a` 的准确 CI `37450280680` 已独立查询确认 success；
它不代替新 D 的验证，也不证明旧现场根因已解决。

## 最小绑定变更

`growth_sources` 增加 A→C→D 的祖先校验，拒绝将 C 本身作为 D，并逐一校验新 A 三文档摘要。
writer 清单新增 `resume.A/C`，保留原 host-read、terminal-auth 批准及全部原输入、工具、窗口绑定。
同窗两 CLI 的清单相等验证覆盖新字段；writer 请求/失败 schema、认证、读取与维护流程不改。

为保留 65536 B 源码上限，仅机械删除 host 文件赋值等号两侧空格，格式变换前后 AST 相同。
`git diff -w` 的行为差异仅为上述准确绑定。七项新拒绝/接纳测试覆盖祖先不匹配、C 冒充 D、
三份批准文档各自变更及正常接纳；已有两 CLI 回归同时确认新旧批准都被保留。

| 冻结对象 | 字节 | SHA-256 |
| --- | ---: | --- |
| host source | 65469 | `59eb79ea4934d04eed70b3f4ed34d0535f143eb3933e65366fd39cd5edb1ca78` |
| guest source | 65438 | `49e2aefe3e5ff7b702133125d8da7007c05ee0021e64e150ce2d419583614f55` |
| fixed kernel reader | 15055 | `947469560ca3bdc4997a56739b42561c4a616a5dc8b250b919db589689eecc02` |
| 绑定准确 D 的 root writer payload | 23786 | `c9119c0650e72e28bdb95d95d134fb386fd84ac8247f253c4db70a2afe7ce4e0` |

loader SHA-256 仍为 `081d3bed41e9f49153096cb893ee20980182831d551c41b9504b886fd0c46aca`。
准确 D 的 `growth_sources` 已实际通过全部十二源码成员、原依赖及源码上限校验。
writer argv 仍是固定 `sudo -- env -i ... python3 -I -B -c loader payload sha request`；
没有 `-n/-S/-A/-v`、认证预热、探测、额外 helper 或第三条 SSH。

## 验证结果

真实普通宿主 Python 3.10.12 / pytest 8.4.2，在冻结 D 上复跑十一份 journal 测试文件、
host kernel facts 与 journal chain 共十三文件：**325 passed，0 skipped，5.67s**。
其中包含真实 pidfd、合成 qcow2/ext4 及终端 fixture；无真实 sudo、原 VM 或现场 writer 扫描。
这不是产品 Python 3.12 发行验证；正常 CI 按其原矩阵独立验证。`git diff --check` 通过。

准确 D 的 [CI 37458930058](https://github.com/kongbu0621/infra-local-hand/actions/runs/37458930058)
attempt 1 已完成，head SHA 为准确 D，结论 success；classify-change、Windows 和 Linux
三个 job 全部成功，包括 Linux 的独立安装 wheel 验证。没有重跑；该结果不证明原主机准入或维护成功。
Linux 日志保留：前置独立检查 16 passed；源码 6047 passed / 89 skipped；安装验证
`PASS`、94 checks / 292 commands。SKIP 仍为 SKIP，不能替代具体现场资格。

## 原静态输入

通过已有严格 `freeze_growth_inputs` 核对八份原件：frame、原 plan archive 与六份历史 archive。
先前私有记录中的 Downloads 别名是符号链接，首次静态读取在父链处以 ENOTDIR 拒绝；
核对该别名实际指向的原规范目录后，使用规范路径和原 no-follow/O_NOATIME 规则通过。
没有复制、更换、修改权限或弱读回退。该调用没有构造 Window、读取 host boot 或调用现场入口。

- source binding：`2cb178702a4aedfc1b9366eab4d8e111f73d8130bf38be96460116ceebb14caa`；
- plan：`efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c`；
- inventory：`a5ea03d6311884a8ff47244271b3ccfecc18d934db9ca66172668cf8078851fd`；
- description：`64c6cfc7b773aa51af33cf971da672786c49965e16cc75923fc6fc25b1ac4814`；
- horizon：`3ecc6bd649d4e33bdc08283c8b76984fad286a1b484f7df0452b59a470033c82`。

以上全部与此前冻结摘要一致，不是新的现场准入、当前 writer 排他性或工具身份观察。
完整现场清单仍由同一窗口的原预检形成，execute 原样继承其 manifest、window 和 writer handoff。

## DR2 交接边界

准确 D 已在独立源码 worktree 冻结；其后验证记录的提交不改变该候选。该 worktree 是开发源码
检出，不是 helper 安装、VM 部署或新预算池。私有原件与现场输出留在原位置。
Owner 必须在已有真实本机前台终端启动原 CLI，密码仅交给 sudo 自身的终端界面。
不能用工具新建 PTY 冒充 Owner 在场，不能在无真实终端时先启动预检消耗窗口。

本次 DR2 窗口数、writer、marker、SSH、关机、备份、镜像增长、VM 启动、ext4 增长及
H01/Q4/H11 均为 0；本记录只描述当前执行者尚未启动这些动作，不是远端完整状态证明。
这一次替代窗口仍未使用。原 15s/900s/780s、八检查点、预算和跨方案累计次数保持。
失败即停、不自动重试/重连/补采/强杀/清理/回滚；全门通过后仅完成既有 journal 维护。
