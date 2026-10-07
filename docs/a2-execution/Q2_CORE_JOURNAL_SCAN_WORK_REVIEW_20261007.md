# Journal 扫描工作量：W1 验证与候选冻结

2026-10-07（Asia/Shanghai）。**本记录描述 W1 完成并冻结交接时的状态。**
准确 D 的首次 CI 全部通过；当时 W2 未开始。后续 [W2 现场返回](Q2_CORE_JOURNAL_SCAN_WORK_FIELD_20261007.md)
已记录唯一替代窗口 CONSUMED / FAILED，冻结交接不得再次执行。
所有旧窗口继续消耗；固定工作预算和进度不保证现场通过，历史 UNKNOWN 不改写。

## 准确批准和候选

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本执行者在本会话已直接完整读取固定规则，
  SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 匹配。
- 准确 A：`42a66be98c45e817e866d3fb86a1c184c2ce55f9`，
  `LH-Q2-CORE-JOURNAL-SCAN-WORK-v1` / W1–W2；三文档摘要及历史 OPEN 字节不变。
- [Owner B](../governance/Q2_CORE_JOURNAL_SCAN_WORK_OWNER_DECISION.md)：事件
  `LH-Q2-CORE-JOURNAL-SCAN-WORK-CLOSURE-20261007-01`，逐字保留紧邻请求与 Owner 批准。
- 独立 C：`1f656f7dab12ddb02c6927d3fc08c2fbe81ffebc`，仅 AGENTS.md 与决定，没有实现。
- 实现 D：`57c7f8e19e047d8caeea401593d8e4bbd4dc373d`，是 C 的直接子提交；tree
  `3d77eee6ad4b41de2c7a4aad29bbd17335d65e11`。两提交已分别保留并非强制发布到 main。

独立干净源码检出保持准确 D；后续文档提交不替换执行候选。全部旧候选、交接、失败及输出保留，
不能复用旧报告、旧窗口或清除 shell 标记来重开。未构造新现场 Window 或进行原现场观察。

## 实现和保留边界

初始 snapshot、复核 snapshot 的 `entry.stat`，以及匹配 FD 的额外 `os.stat`，
现在共享每调用固定 2097152 次尝试预算。真正调用前收费，异常不退款；第 2097153 个候选
以 `FD_STAT_CALLS` 拒绝，未发起的调用不计入 progress。原每 snapshot 65536 项门仍在收费前。
旧事后 `FD_TOTAL` 门被明确替代，没有通过保留旧门或跳过 task 使新计量失效。
这是 stat 尝试计数，不冒充全部系统调用数；fdinfo/proc 读取仍服从原文件和时间门。

逐 task 的完整读取与复核保留；没有 PID 去重、缓存、线程省略、自动调额或停止宿主应用。
maps 单文件 1 MiB、累计接受 512 MiB，其余 16 个 proc limit 位点及原身份/集合/writer 判据不变。
host 的既有声明 AST 变化只在 WriterObserver、snapshot/scanner、source_bundle 和 growth_sources；
新函数仅为 progress 初始化与 stat 收费。guest 的既有声明变化只在 payload 生成、失败解析与
WriterProtocol；另新增 progress 校验，并更新固定 WRITER_ENTRY 和必要的 GUEST_LOADER 文本。
源码变化没有进入 VM 增长、guest 维护效果、核心 dispatcher 或其它分支。

结果严格使用 `lhq-journal-writer-result/v2`。成功/失败各包含固定 progress；合法 request
不得缺失进度，request-null 的早期失败只允许 progress-null。字段、类型、范围、关系和
canonical 4096 B 界均校验，拒绝旧 v1、混用、额外字段、bool/float 计数及伪 complete。
最后成功双钟样本只从既有 check 保存；失败处理不另取时钟、不补读。

最终 PID 集合与 WRITER_ENTRY 最后期限检查通过后，才设置 REPORT/scan_complete。
后续 usage 或编码/大小准备失败可保留扫描完成事实，但结果仍失败；父层 writer 集合准入
仍独立必需。完整合法失败的 progress 随 child_failure 传播，超时/TTY 等更早首因保留。
缺少完整子报告时保留缺失，不补造进度。没有刷新 15s/900s/780s 或添加认证调用。

准确 WORK_A/C、三文档摘要和 A→C→D 校验已接入；C 本身不能执行。
writer 清单显式绑定结果 v2、三类 stat 计费规则、2097152、progress 4096 与维护源 98304。
原 R/A/C、两诊断批准、maps 批准、认证、工具及全部输入绑定继续保留。

## 隔离验证

普通宿主 Python 3.10.12 / pytest 8.4.2。相关十五文件完整回归 **635 passed、0 skipped，34.58s**。
随后仅补充匹配 stat 异常不退款的源函数/生成 payload 两用例：**2 passed，0.24s**；实现源码不变。
此前六组集中回归为 **390 passed，29.95s**。本次没有失败后重跑现场或新增现场探针。

本范围专属用例与保留回归共同证明：

- 源函数和实际生成 payload 运行真实扫描循环，512 个 task 各 2048 个 FD，初查与复核
  恰好 2097152 次 stat，同时逐 task 完整读取累计 512 MiB maps；重用 1 MiB 数据块。
  下一 task 的首个 stat 在调用前被拒绝，没有读取其 maps 或继续后续 task。
- 三类共用计数；初查、复核及匹配 stat 抛错均保留已收费次数。第 65537 snapshot 条目
  不收费也不 stat。越过旧逻辑 FD 门后，末尾 task 私有 FD writer 和 mapped writer 仍被识别。
- 原单文件/累计 maps 边界、读取失败、身份/集合漂移、FD drift、认证及双钟期限仍拒绝。
  已完整文件与读取失败前缀分开，真实生成入口保留最后成功时钟、阶段和完成数。
- 旧 v1、缺失/额外/畸形进度、错 request、伪完成及旧 retained preflight 均拒绝；
  允许失败复核多读新增 FD 的真实前缀，允许 REPORT 失败保留 scan_complete，但不能准入。
  既有 EOF/真实退出、TTY/超时首因、无重试与两 CLI 同一清单/窗口交接回归保持。
- 两维护源 98304 B、guest bundle 源 98304 B 的等值/超一边界通过；reader/descriptor
  仍为 65536 B。真实无特权 loader 拒绝超界；payload 32768、压缩 49152、解压 393216、
  完整 argv 65536 的拒绝门保留。没有扩大其它输入界或新增实现模块。

这些是隔离证据，不能推算真实宿主需求或保证 15s 内完成。既有局部资源观察不是全过程峰值。

## 准确源码与静态输入

准确 D 的十二成员 source admission、所有旧/新祖先与文档 pins，以及 payload 内存编译通过。

| 对象 | 字节 | SHA-256 |
| --- | ---: | --- |
| host maintenance source | 67975 | `dd6bd30e7b5885d7d45340a1038d3eae7669db26ea0e4fd5143accf19724d17a` |
| guest maintenance source | 68195 | `47bd23ac35a00a79b58f132363ec198f5690b62262493e2ecaead5b975bdfc97` |
| fixed kernel reader | 15055 | `947469560ca3bdc4997a56739b42561c4a616a5dc8b250b919db589689eecc02` |
| unchanged guest reader | 13357 | `9c91b70cefce29e2f49fe0428caaa3b4196d6a5fed05a8d4a08691a4759d6744` |
| exact D root writer payload | 26285 | `9f83db296a55c36e8fb753549cfef959ff0cc69b91d6a907381cedc95aeb544d` |

root writer loader SHA-256 仍为 `081d3bed41e9f49153096cb893ee20980182831d551c41b9504b886fd0c46aca`。
guest loader 按批准只调整 guest 源界，SHA-256 为
`dbe142b96c7dd49c00f68c7a0fd4df16c6ab19b9bb6aa1984e5583cef946a191`。
准确两源加 reader，以明确 24 B 合成 descriptor 做传输尺寸检查：压缩 bundle 36347 B，
完整合成 remote argv 50539 B。它不是实际现场 pre/post 包；实际 descriptor、bundle、argv
仍须在原 W2 CLI 内分别通过原检查，不能为构造它们提前调用现场或沿用模拟准入。

八份原静态输入在普通宿主身份下，使用原 no-follow/O_NOATIME、保护、身份、摘要及 recheck
规则通过，没有复制输入、改变权限或弱读回退；没有构造 Window、读取当前 boot/proc/VM、
执行工具资格探针或发送 SSH。与 MB1 冻结完全相同的绑定为：

- source：`2cb178702a4aedfc1b9366eab4d8e111f73d8130bf38be96460116ceebb14caa`；
- plan：`efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c`；
- inventory：`a5ea03d6311884a8ff47244271b3ccfecc18d934db9ca66172668cf8078851fd`；
- description：`64c6cfc7b773aa51af33cf971da672786c49965e16cc75923fc6fc25b1ac4814`；
- horizon：`3ecc6bd649d4e33bdc08283c8b76984fad286a1b484f7df0452b59a470033c82`。

## 最终 CI 与一次交接

[准确 D 的 CI 37555791202](https://github.com/kongbu0621/infra-local-hand/actions/runs/37555791202)
为 attempt 1，已 completed/success，head 为准确 D。classify-change、Linux、Windows
三个 job 全部成功；两个平台的源码测试与独立安装 wheel 步骤都已成功，没有重跑。
平台不适用的 SKIP 保持为 SKIP，不冒充特定宿主或 Windows 现场准入。

私有最终交接文本 6343 B，SHA-256
`fad08f6295f506cd2609693b86bbe28e2c1546943798daf6a4d624954d848b8f`，mode 0600。
它是终端交接文本，不是新增可执行 helper；待决草稿另行保留，不能使用。
Bash 语法及两段 JSON 处理代码编译通过；仅对文本处理器的隔离检查证明准确绑定、错误 C
拒绝、完整失败进度和明确缺失，不运行现场 CLI。最终文本绑定准确 D、全部新旧批准及 v2，
成功时原样交接同窗 manifest/window/writer，失败没有重试分支。
摘要保留合法 failure_progress 和明确区分的 last_successful_writer_progress；缺失为 null。
摘要长度/哈希对应去除末尾换行后的 shell JSON，不冒充原始 CLI stdout。

冻结交接时 W2 未开始，尚未消费本次替代窗口；本执行者未执行现场 writer/sudo、marker、SSH、关机、备份、
镜像增长、VM 启动或 ext4 增长。原 session、输入/对象、普通身份、真实前台终端认证、原时钟
起点与累计次数保持；shell STARTED 仅防误粘贴，不冒充跨进程硬性防重启。
工具和全部现场资格仍由原准确 CLI 检查；不增加 helper、探针、预热、权限或预算池。

未知、漂移、失败或超时即停，不重试、重连、补采、强杀、清理、恢复或回滚。
全门通过才同窗完成未消费的原 journal 维护，原合格 receipt 才证明维护成功；
新 boot 核心采用、H01/Q4/H11 及所有扩展支线继续不执行。
