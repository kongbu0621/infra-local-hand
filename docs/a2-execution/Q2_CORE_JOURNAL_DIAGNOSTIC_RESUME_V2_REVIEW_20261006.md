# Journal 诊断替代窗口 v2：DR1 候选验证

2026-10-06（Asia/Shanghai）。本记录冻结时点：**DR1 完成；DR2 未开始，唯一替代窗口尚未使用。**
旧窗口仍已消耗，旧 `GROWTH_PROC_LIMIT` 的具体分支和计数仍 UNKNOWN；本次诊断不证明现场问题已解除。

后续 [v2 DR2 现场返回](Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_V2_FIELD_20261006.md)已将本次窗口状态
更新为 CONSUMED / FAILED：首次 writer 检查点报告累计 maps 文本超过原 64 MiB 上限。
以下未开始/零动作描述只属于 DR1 冻结时点，不能据此再次执行交接。

## 准确链与发布

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接固定规则已完整读取，源 SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 匹配。
- A：`4341487c9be9ef64cf6fccbd973ed438a66e7483`，仅
  `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v2` / DR1–DR2；三文档及历史 OPEN 标签 byte-identical。
- [准确 B](../governance/Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_V2_OWNER_DECISION.md)：
  `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-V2-CLOSURE-20261006-01`，逐字保留 Owner 回复及紧邻请求。
- 独立 C：`807d61b75841a416064f4c1ec1d7c2e0187e0d49`，仅 AGENTS.md 和 B，没有实现。
- 执行候选 D：`4236ac62e61c0cdf62b49f3620c325454e8fba99`，C 的直接子提交；tree
  `7e26a8a4267fa2379eff9dea92ecfb853633f6ef`。C 与 D 已分别保留并非强制发布到 main。

前置诊断修复 `03cfb183d05c55258bb2da01e8c3cf77ea06fe63` 及其成功 CI `37475992159`
保持历史事实，不代替新 D 的 CI 或原宿主准入。独立源码 worktree 冻结准确 D，后续证据提交不改变执行候选。

## 变更与隔离验证

新 `DRV2_A/C/PINS` 固定本范围批准，`growth_sources` 检查 A→C→D、拒绝 C 本身冒充 D，
逐一验证 v2 三文档；全部原批准与文档检查保持。writer 清单新增 `resume_v2.A/C`，同时保留
原 `resume.A/C`、host-read、terminal-auth、工具、payload 和窗口绑定。两 CLI 原清单一致性检查
覆盖新增字段，不复用上次 PASS。

仅为保持原 65536 B 源码上限，按 Python token 删除比较运算符旁与冒号后的机械空白；
65884 B 压缩至 65397 B，变换前后完整 AST 相同。另与 C 的源码做 AST 比较，除新 pins、
`growth_sources` 和 writer 的 `binding` 外全部节点相同。guest 文件没有改动。
没有新增现场读取、认证方式、helper、探测、阈值、覆盖裁剪、预算或维护次数。

普通宿主 Python 3.10.12 / pytest 8.4.2：十二份 `test_e3_q2_journal_*.py`、
`test_e3_q2_host_kernel_facts.py` 和 `test_e3_quota_q2_journal_chain.py` 共十四文件，
**494 passed，0 skipped，16.81s**。包含源与生成 payload 的全部 proc 限制诊断、两 CLI 交接、
v1/v2 祖先与三文档拒绝、真实普通身份 pidfd 和合成终端/磁盘 fixture。
没有真实 sudo、原 VM、全宿主 proc writer 或 SSH 调用。当地 Python 结果不冒充产品 Python 3.12 验证。
`git diff --check`、payload 内存编译和准确 D 的十二源码成员准入通过。

| 冻结对象 | 字节 | SHA-256 |
| --- | ---: | --- |
| host source | 65397 | `3d425667e6fd93d7aea2e1a98c1c0349f6895c801f08ca450d9efc954aa81792` |
| guest source | 65453 | `966e1b0f2c0673d2fb1a18600022f1a8d92cac2965a12d102045537d3f43d0a2` |
| fixed kernel reader | 15055 | `947469560ca3bdc4997a56739b42561c4a616a5dc8b250b919db589689eecc02` |
| 绑定准确 D 的 root writer payload | 24484 | `59e21da2418d05cefe76d760eebf89fa7a94dc4bfddf11cb1f17293827592a78` |

loader SHA-256 保持 `081d3bed41e9f49153096cb893ee20980182831d551c41b9504b886fd0c46aca`。
固定 argv 仍是原 `sudo -- env -i ... python3 -I -B -c loader payload sha request`；
仅由 Owner 在已有真实本机前台终端认证。没有 `-n/-S/-A/-v`、askpass、整体提权或工具新建 PTY。

## 原静态输入与保留的环境拒绝

首次仅调用 `freeze_growth_inputs` 时，沙箱把固定父目录的 root 所有者映射为 uid 65534，
原 `open_directory` 在 `LOCAL_PARENT` 拒绝；没有构造 Window 或读取原输入正文。
只读比较同一固定目录链证实真实宿主父目录为原 root 0755，普通身份 uid 1000 不变。
随后在普通宿主环境沿用原 no-follow/O_NOATIME 和全部保护检查，八份原静态输入全部通过。
没有改权限、复制原件、弱读回退或新增现场观察；该环境拒绝保留，不算现场窗口。

- source binding：`2cb178702a4aedfc1b9366eab4d8e111f73d8130bf38be96460116ceebb14caa`；
- plan：`efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c`；
- inventory：`a5ea03d6311884a8ff47244271b3ccfecc18d934db9ca66172668cf8078851fd`；
- description：`64c6cfc7b773aa51af33cf971da672786c49965e16cc75923fc6fc25b1ac4814`；
- horizon：`3ecc6bd649d4e33bdc08283c8b76984fad286a1b484f7df0452b59a470033c82`。

全部与前次原静态绑定相同。完整原件及机器细节留在私有原位置；静态冻结不证明当前 VM/writer、
工具资格、完整预算或准入。它们仍须在唯一原流程预检中共同通过。

## 最终 CI 与 DR2

准确 D 的 [CI 37482894717](https://github.com/kongbu0621/infra-local-hand/actions/runs/37482894717)
attempt 1 已 completed/success；head 为准确 D。classify-change、Windows、Linux 三个 job
全部成功，两个平台的源码测试和独立安装 wheel 验证均通过，没有重跑。
各平台不适用的 SKIP 保留为 SKIP，不补作原宿主准入或现场验收。

私有交接文本已完成 Bash 语法校验及两段 JSON 处理代码的内存编译，没有执行该文本。
文件 4742 B，SHA-256 `1259362a1856403ed3c050e78a8a56a996493a969d20f4910b163771ff890ca6`。
它只交接原 CLI 的一次预检和成功后的同窗 execute；断言准确 D、新旧 A/C 和原零消费预检状态，
原样传递 manifest/window/writer 绑定。新的 shell 变量保留旧 v1 变量，只防同一终端误粘贴，
不是跨进程硬性防重启机制，也不是新增 helper 或预算池。
summary 的字节数与摘要针对 shell 保留的 JSON，命令替换已去除末尾换行，不冒充原始 stdout。

当前执行者没有启动 v2 现场窗口、sudo/writer、marker、SSH、关机、备份、镜像增长、VM 启动、
ext4 增长或 H01/Q4/H11；这描述本次动作，不冒充远端完整状态证明。
现在可由 Owner 在已有真实本机前台终端开始唯一一次 DR2；密码仅进入 sudo 自己的控制终端。
保留所有旧终端变量和原候选证据；新的 v2 交接标识不构成新预算或旧窗口退款。
预检失败即停，全门通过才同窗完成原 journal 维护；15s/900s/780s、预算、累计次数和所有禁止事项不变。
