# Q1 systemd 默认 root 启动修正

源码本地检查点 `3d074795eb3d69f3e4d81205085af36e5fb7ae61`，tree `d82ec1c3194bb39da07545fff0429e4466abc68e`，父提交
`37a24a1a0c3d28f89a7d0bfa53e8efdc42729db1`。本报告与开发日志在后续提交记录。

## 问题与修正

显式 `User=0` 配合 seccomp 限制时，systemd 255 的 setuid/seccomp 准备路径会
调用 `keep_capability(CAP_SYS_ADMIN)`；该函数同时设置 inheritable/permitted/effective。
当能力已包含在服务 bounding set 中，收尾不会删除它。这与 worker 要求零 inheritable
能力的准入条件冲突。

依据是固定 [systemd v255 exec-invoke.c](https://github.com/systemd/systemd/blob/v255/src/core/exec-invoke.c)
和 [capability-util.c](https://github.com/systemd/systemd/blob/v255/src/basic/capability-util.c)。
前者 Git blob `74c910fc1239dedc9994caa2beef94194e7232d6`；其 `uid_is_valid`、
`keep_seccomp_privileges` 和保留 bounding set 能力分支解释了这次启动差异。
这些上游来源不冒称目标发行版完整源码的逐字节验证。

`unit_command` 仅将 `User=0` 改成空 `User=`，使用已经固定的 `--system` manager
默认 root。Group、NNP、能力上界、ambient 清空、namespace/设备/网络/挂载保护、
资源限制、原 deadline 和命令路径保持原值。worker 继续核验实际 UID/EUID 0、
Prm/Eff/Bnd 恰好 `0x200004` 且 Inh/Amb 为零；worker/native/journal 源码未改。

## 验证与证据边界

- 开发回归先在旧 runtime 上确认 `User=0` 被新增断言拒绝：14 项中 1 项预期失败。
- 修正后运行完整 Q1 测试组：**235 项通过，0 跳过**，退出码 0。
- 修改的 Python 文件内存编译、差异空白及批准文档/产品包边界检查通过。
- 严格能力检查新增 `CapInh=0x200000` 反例，仍要求拒绝。
- 用户提供的私有隔离 VM 截图报告候选参数下 UID/EUID 为 0、Inh/Amb 为零、其余
  能力集合及 NNP 满足原检查，安装和 slot 挂载检查通过，三棵资源树为空。
  这是用户提供的只读 pre-exec 结果；本执行器未直接连接该 VM，也未取得完整原始
  现场日志。截图和原始主机路径、身份与日志不放入公开开发证据。

候选参数诊断未执行原生 quota 调用。首次真实查询尝试的 UNKNOWN、原启动意图、
allocation、slot/root/project 预留继续保留，不能覆盖为成功或靠换请求/代次重投。
后续固定源码交接保留原安装；另行准入不同 slot/root/project 后使用同一持久 journal，
继续保留旧记录。一次启动检查成功不代表配额 enforcement、Q1 出口或 E3 验收通过。
生产 `E3_SUPERVISION_UNVERIFIED` 不变，未进入 Q2/Q3/Q4。

开发命令、UTC 时间、退出码和日志摘要见
[commands.json](validation/q1-default-root-20260924/commands.json)，
[原始开发日志](validation/q1-default-root-20260924/unittest.log)，
[修正前失败](validation/q1-default-root-20260924/pre-fix-regression.log)，
[源码摘要](validation/q1-default-root-20260924/source-map.json)及
[边界检查](validation/q1-default-root-20260924/boundary-check.json)。

本地没有重复整个产品安装矩阵；新候选 CI 在发布后按准确 head 单独核对，
不得沿用旧 run 的通过数。发布身份和 CI 状态以同目录 publication-status.json 为准。

## 发布身份

已发布源码 `45ebc2fd1fe70cfa4680f6ad71f0badc2a4ec0a3`，与本地被测源码
tree `d82ec1c3194bb39da07545fff0429e4466abc68e` 完全相同；初始开发证据发布为
`97e12d86d52243747f694827415066c593f851b0`。GitHub 接口生成的提交元数据不同，
原本地提交保留，逐文件摘要和文件树均已比对，详见
[publication-map.json](validation/q1-default-root-20260924/publication-map.json)。

VM 固定新源码时应并排安装发布提交 `45ebc2f`，保留原 `37a24a1` 及其配置、
原票据、永久 journal 和证据。源码 staging 不代表新配置准入，不执行 quota 查询。

## 准确候选 CI

[run 35975888188](https://github.com/kongbu0621/infra-local-hand/actions/runs/35975888188)，
attempt 1，head `97e12d86d52243747f694827415066c593f851b0`，三项 job 全部 success。

| 平台 | 源码通过 | 源码跳过 | 独立安装 |
| --- | ---: | ---: | --- |
| Linux | 1122 | 1 | PASS：94 checks、292 commands |
| Windows | 261 | 343 | PASS：10 checks、10 commands |

准确 job/步骤、规范化完整日志摘要及逐项跳过原因见
[CI 元数据](validation/q1-default-root-20260924/ci-runs.json)，
原始对应行见 [CI 摘录](validation/q1-default-root-20260924/ci-excerpts.log)。
Linux 的唯一跳过仍是缺少专用 non-root / predelegated manager 准入的真实 cgroup 集成，
明确报 `E3_SUPERVISION_UNVERIFIED`。Windows 的平台跳过单列，不计入通过。
本次补记只涉及文档和开发证据，不改变已验证源码、测试或 workflow。
