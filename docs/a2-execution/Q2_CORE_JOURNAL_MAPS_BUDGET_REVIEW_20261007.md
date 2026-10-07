# Journal maps 预算修正：MB1 验证与候选冻结

2026-10-07（Asia/Shanghai）。**本记录描述 MB1 完成并冻结交接时的状态。**
当时 MB2 未开始；后续 [MB2 现场返回](Q2_CORE_JOURNAL_MAPS_BUDGET_FIELD_20261007.md)
已确认唯一替代窗口 CONSUMED / FAILED，冻结交接不得再次执行。
全部旧窗口继续消耗，历史 UNKNOWN 不补写；固定 512 MiB 不保证现场准入或维护成功。

## 准确链

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本执行者在本会话已直接完整读取固定规则，
  源 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 匹配。
- A：`d18b490a7cdb63ee43044a29a89746ef78fccff3`，仅
  `LH-Q2-CORE-JOURNAL-MAPS-BUDGET-v1` / MB1–MB2；三文档与历史 OPEN 标签 byte-identical。
- [准确 Owner B](../governance/Q2_CORE_JOURNAL_MAPS_BUDGET_OWNER_DECISION.md)：
  `LH-Q2-CORE-JOURNAL-MAPS-BUDGET-CLOSURE-20261007-01`，保留准确回复和紧邻请求。
- 独立 C：`3d928a323d1aad12c20a66594bb295d4df14fab0`，只含 AGENTS.md 和 B，没有实现。
- 候选 D：`68b63da88d70cfb8151f66a75c7f523baaf012d2`，为 C 的直接子提交，tree
  `6b5a5b993aac33132e3a2e64f6ac318add0bd6d3`。C/D 保留独立历史并已非强制发布到 main。

准确 D 已在独立源码 worktree 冻结；此后验证文档的提交不改变执行候选。旧 v1/v2 候选、
交接和失败记录保留，不能再次执行。本记录不把旧 CI 或旧观察转成新窗口的 PASS。

## 最小修改与 AST 证据

扫描器唯一算法变化是 `MAPS_TOTAL_BYTES` 的比较 cap 从 `64 * MIB` 改为 `512 * MIB`。
将基线该常量替换为 512 后，旧/新扫描函数完整 AST 一致；所有逐 task 读取、解析、FD/flags、
身份/集合复核、失败顺序和其它 cap 均未变。guest 文件没有修改，生成 payload 仍提取同一源函数。

另加入本范围 `MB_A/C/PINS`、A→C→D 祖先和三文档完整性校验，拒绝 C 本身作为 D；
writer 清单新增 `maps_budget.A/C`，保留全部旧批准、工具、窗口及输入绑定。
两 CLI 清单一致性回归确认新旧批准都保留，不复用旧窗口或旧成功报告。

绑定初稿 66060 B；首次仅压缩运算符旁空白的候选仍为 65689 B，长度断言拒绝写入。
随后仅追加括号内续行前导空白的 token 级压缩，最终 host 65494 B。格式变换前后完整 AST
相同；另证明整个文件除新 MB pins、admission、manifest 和该单个 cap 外 AST 与 C 一致。
未增大源码上限、删除检查/pins、建立第三实现或新增依赖。

## 隔离验证

普通宿主 Python 3.10.12 / pytest 8.4.2；没有真实 sudo、原 VM、全宿主 proc writer 或 SSH 调用。

- 四文件核心回归：**258 passed，0 skipped，13.51s**。
- 十二份 `test_e3_q2_journal_*.py`、`test_e3_q2_host_kernel_facts.py` 和
  `test_e3_quota_q2_journal_chain.py` 共十四文件：**524 passed，0 skipped，17.80s**。
- `git diff --check`、准确源码 admission 的十二成员和 payload 内存编译通过。

源函数和实际生成 payload 均用合成数据证明：

- 512 MiB 精确等值完成；多 1 B 或再读一份 1 MiB 文件时返回正确 N/MAX/PID/TID，
  并且不读取下一 task。重用一份有界数据块，未分配 512 MiB 夹具。
- 同内容仍逐 task 读取/计数；达到旧现场值 67,115,642 B 后继续，后续 FD/mapped writer
  正确识别，正常完成路径仍到达 task/PID 最终复核。
- 越过旧界后，畸形 maps、读取失败、task/PID 身份变化、task/PID 集合变化、FD drift
  和 deadline 仍拒绝，不被提高 cap 吞掉。
- 单文件 1 MiB 和其余 16 个原 proc limit 位点、初读/复核、固定失败 schema、父层传播、
  认证/EOF/真实退出与原期限的既有回归保留；新旧授权祖先、三文档漂移及两 CLI 绑定通过。

这些是隔离证据，不证明实际宿主完整扫描能在 512 MiB/15s 内完成，也不替代产品 CI。

| 冻结对象 | 字节 | SHA-256 |
| --- | ---: | --- |
| host source | 65494 | `d27e8bd55da1c8dc7cf95018e8e49aa4aa64eb2b44ead79a076893863bc36f91` |
| guest source | 65453 | `966e1b0f2c0673d2fb1a18600022f1a8d92cac2965a12d102045537d3f43d0a2` |
| fixed kernel reader | 15055 | `947469560ca3bdc4997a56739b42561c4a616a5dc8b250b919db589689eecc02` |
| 准确 D 的 root writer payload | 24411 | `3bae3a1faa520708cbc687deca3af4d91bd8600b5de53acca11c27c683522d7b` |

loader SHA-256 仍为 `081d3bed41e9f49153096cb893ee20980182831d551c41b9504b886fd0c46aca`。
固定 argv 及工具资格校验不变，未提前启动工具/权限探针。完整工具身份仍由原唯一预检核验。

## 原静态输入

八份原件在普通宿主身份下，用原 no-follow/O_NOATIME、保护/身份/摘要和 recheck 规则通过；
沿用已确认的规范路径，没有复制、换输入、改权限或弱读回退。已知沙箱父目录映射问题见
[v2 冻结记录](Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_V2_REVIEW_20261006.md)，本次未重复该已知不适用环境。
该调用未构造 Window，未读取当前 boot/proc/VM，不构成现场预检或窗口消费。

- source binding：`2cb178702a4aedfc1b9366eab4d8e111f73d8130bf38be96460116ceebb14caa`；
- plan：`efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c`；
- inventory：`a5ea03d6311884a8ff47244271b3ccfecc18d934db9ca66172668cf8078851fd`；
- description：`64c6cfc7b773aa51af33cf971da672786c49965e16cc75923fc6fc25b1ac4814`；
- horizon：`3ecc6bd649d4e33bdc08283c8b76984fad286a1b484f7df0452b59a470033c82`。

全部与原绑定相同。原件、机器路径和完整现场证据保持私有；不将静态核验当作完整现场准入。

## 最终 CI 与唯一交接

准确 D 的 [CI 37500889014](https://github.com/kongbu0621/infra-local-hand/actions/runs/37500889014)
attempt 1 已 completed/success，head 为准确 D。classify-change、Linux、Windows 三个 job
全部成功，两个平台的源码测试与独立安装 wheel 验证均通过；没有重跑。
各平台不适用的 SKIP 保持为 SKIP，不补作具体宿主准入或真实现场验收。

私有交接文本 5122 B，SHA-256
`b73dfc6dec4285a0f8fad91d48bae97de50866977e67f2c2286d27930b1bda0f`。
Bash 语法及两段 JSON 处理代码编译通过，未执行交接文本。它断言准确 D 和所有新旧 A/C，
只调用一次原预检，并在成功时原样传递 manifest/window/writer 绑定至同窗 execute。
新的 `LH_Q2_MB2_*` 变量保留旧 `LH_Q2_DR2_*` / `LH_Q2_DRV2_*`；同终端 STARTED 标记仅防误粘贴，
不冒充跨进程硬性防重启机制。summary 长度/摘要对应去除末尾换行的 shell JSON，不是原始 stdout。

冻结交接时 MB2 尚未开始，本执行者没有进行现场 writer/sudo、marker、SSH、关机、备份、镜像增长、
VM 启动、ext4 增长或 H01/Q4/H11。这个零动作描述不冒充远端完整状态认证。
当时交接允许 Owner 在已有真实本机前台终端开始一次替代窗口，密码仅交给 sudo；
该窗口随后已消耗，见上述现场返回，不再允许启动。
沿用原 session、原 CLI 时钟起点和同窗两阶段交接，不新增 helper、探测、认证预热或预算池。

除明确批准的累计 maps cap 外，原认证、完整扫描、其它 cap、15s/900s/780s、资源预算、
最多八检查点和跨历次维护次数保持。固定 512 MiB 不动态调整，不保证现场完成。
失败、未知、超时或漂移即停；不重试、重连、补采、强杀、清理或回滚。
全门通过才同窗完成尚未消费的原 journal 维护，合格 receipt 才记成功；H01/Q4/H11 与支线不执行。
