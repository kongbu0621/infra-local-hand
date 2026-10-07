# Journal 一致性拒绝的分支诊断修复

源码基线 `a64a76dadf75d995d049f08c96c94db855ec56ff`。本次为已有 CLOSED 开发范围内的
离线诊断修复，不修改批准文档、扫描策略或现场次数。最新 W2 仍为 CONSUMED / FAILED；
其 `PID_RECHECK` / `GROWTH_PROC_DRIFT` 只能证明该阶段拒绝，不能由新测试反推历史分支。
原现场事实保留于 [W2 返回](Q2_CORE_JOURNAL_SCAN_WORK_FIELD_20261007.md)。

## 修改与边界

只修改 `q2_journal_growth.py` 的原拒绝点；实际 writer payload 从同一函数生成。
原通用前缀保留，细分为以下固定后缀，不输出路径、进程标题、文件内容或异常原文。

| `GROWTH_PROC_DRIFT_` 后缀 | 实际拒绝条件 |
| --- | --- |
| `DUPLICATE_PID_ENTRIES` / `DUPLICATE_PID_ENTRIES_RECHECK` | 初始 / 最终 PID 枚举出现重复名称 |
| `DUPLICATE_TASK_ENTRIES` / `DUPLICATE_TASK_ENTRIES_RECHECK` | 初始 / 复核 task 枚举出现重复名称 |
| `FD_IDENTITY` | 匹配镜像的 FD 再次 stat 身份不一致 |
| `FDINFO` | 匹配 FD 的两次完整 fdinfo 字节不一致，不仅指 flags |
| `FD_SNAPSHOT` | 同一 task 的两次 FD 名称到身份映射不一致 |
| `TASK_START` | task starttime 复核不一致 |
| `PID_TASK_SET` | 同一 PID 的前后排序 task 列表不一致，包括数量相同但成员变化 |
| `PID_START` | task 列表相同后，PID starttime 复核不一致 |
| `PID_SET` | 最终全局 PID 列表与初始列表不一致 |

PID 复核原 `require(A and B)` 拆成两个顺序 require；A 失败后依旧不执行 B 的读取。
所有拒绝仍停止扫描；不会把正常线程活动假定成安全，也不将部分扫描写成成功。
不增加读取、时钟采样、输出字段、重试、补采、缓存或去重；全部覆盖、预算、权限与期限保留。
v2 的 160 字符 ASCII reason 和固定 progress 合同不变；11 个可达新码最长 48 字符。
旧通用 reason 仍是合法历史结果，不修改旧证据或 guest 中无关的 `proc_bytes`。

独立 AST 复核：仅归一化诊断文字、将该 PID require 对重组成旧逻辑后，整个 host AST
与基线完全一致；真实生成 payload 的完整 AST 同样一致。guest、kernel 源字节未变。

## 验证

Python 3.12.14。两个直接相关测试文件 **217 passed，0 skipped，14.56s**；
十五文件 journal / proc / payload / transport / coordinator 相关回归
**773 passed，3 skipped，35.53s**。SKIP 不计 PASS，不代替普通身份与真实现场验证。
新增 26 个参数化用例覆盖 source/generated 双路径、四种重复枚举、PID 复核稳定与各拒绝
分支、同数量不同成员的 task 集合、匹配 FD 身份和 fdinfo 的先后顺序。
完整合成 I/O 序列证明失败后无新增读取；实际生成入口经 v2 parser、父 observer、CLI
safe_reason 保留精确原因，失败后仍禁止第二次调用。全部使用隔离夹具，无原现场扫描。
内存编译、独立 AST 对比及 `git diff --check` 通过；准确发布提交的 CI 状态另行核对，
不沿用旧 W1 候选的 3/3 success。

## 静态尺寸

host 源 68095 B，SHA-256 `9b833210ed79eb82ead9b6813daf7cacec73be0e67b026beee7668140a7d58c7`；
guest 源 68195 B。用明确合成 D（40 个 `d`）生成 payload 为 26405 B，内存编译通过。
两源 98304 B、payload 32768 B 限额保持。合成 writer argv 的 canonical 字节数为 36282。
19 B 合成 descriptor 的压缩 bundle 为 36335 B，合成 remote argv 为 50523 B；
原 49152/65536 B 门通过。这些只是静态尺寸验证，不能替代原私料或实际现场准入。

## 后续交接

本地 Codex 可同步并继续同范围离线复核，保留旧 terminal 变量、失败输出与冻结交接。
本修复解决的是“同一错误掩盖具体检查项”，没有证明宿主一致性问题或 journal 扩容已解决。
不再次执行旧 W2，不调用 sudo/writer/proc/SSH，不补采、重装或清理现场。
依据 AGENTS 的已消费 W2 边界，新的现场窗口或实质一致性策略变更仍需准确范围与 Owner 决定。
不要再次单纯提高 maps/FD 预算：本次观察到的首因是一致性拒绝。
H01/Q4/H11 与扩容后新 boot 的核心接续尚未完成，支线继续暂停。

## 本地准确提交与原私料离线核对

2026-10-07（Asia/Shanghai），本地 main 已快进至准确诊断修复提交
`711932aae3370c7f2ed5c1a51ac82d3b0f67a6e5`，tree
`8661f1693219e4c04b62731b1ea019afaf995a90`。其父为上文源码基线；
原 W1 独立 C `1f656f7dab12ddb02c6927d3fc08c2fbe81ffebc` 仍是祖先。
本次没有新的 Owner B、C 或现场窗口登记，现有批准文档保持原字节。

普通宿主 Python 3.10.12 / pytest 8.4.2 的以下十五文件回归为
**663 passed、0 skipped，35.16s**。这是本地准确命令的独立结果，不与上文云端计数合并：

```text
python3 -B -m pytest -q -p no:cacheprovider tests/test_e3_q2_journal_*.py tests/test_e3_q2_host_kernel_facts.py tests/test_e3_quota_q2_journal_chain.py
```

本地独立 AST 核对仅归一化新增 reason 文本，并将 PID_TASK_SET / PID_START 的相邻
require 重组为原短路 and；host 完整 AST 与父提交一致。用同一个准确提交身份分别从
新旧 host 生成的实际 payload 也得到相同 AST。guest 源字节未变，实际新 payload 内存
编译通过，26405 B，SHA-256
`75cacd327f561252f390fb909d39497d484e21adc955dd9e4e1addd6454d5288`。
host 的 68095 B 和上述 SHA-256 相符；guest 68195 B，SHA-256
`47bd23ac35a00a79b58f132363ec198f5690b62262493e2ecaead5b975bdfc97`。
writer / guest loader 摘要分别保持
`081d3bed41e9f49153096cb893ee20980182831d551c41b9504b886fd0c46aca` 和
`dbe142b96c7dd49c00f68c7a0fd4df16c6ab19b9bb6aa1984e5583cef946a191`。

原 `growth_sources` 通过十二成员来源、准确 HEAD、旧/新祖先和文档 pins 核对。
原 `Inputs` / `freeze_growth_inputs` 在普通宿主身份下通过八份原静态输入的
no-follow、O_NOATIME、保护、大小/摘要及 fd/name/atime recheck；未改变输入权限或使用弱读回退。
各绑定与 [W1 原冻结记录](Q2_CORE_JOURNAL_SCAN_WORK_REVIEW_20261007.md) 完全相同：

| 绑定 | SHA-256 |
| --- | --- |
| source | `2cb178702a4aedfc1b9366eab4d8e111f73d8130bf38be96460116ceebb14caa` |
| plan | `efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c` |
| inventory | `a5ea03d6311884a8ff47244271b3ccfecc18d934db9ca66172668cf8078851fd` |
| description | `64c6cfc7b773aa51af33cf971da672786c49965e16cc75923fc6fc25b1ac4814` |
| horizon | `3ecc6bd649d4e33bdc08283c8b76984fad286a1b484f7df0452b59a470033c82` |

这些调用仅核对已有静态材料，没有构造现场 Window、实例化现场 observer、执行生成 payload、
读取当前 boot/proc/VM、运行 sudo/工具资格探针、发送 SSH 或补采失败原始流。
原 W2 干净冻结工作树仍为 `57c7f8e19e047d8caeea401593d8e4bbd4dc373d`；
原终端交接仍为 6343 B，SHA-256
`fad08f6295f506cd2609693b86bbe28e2c1546943798daf6a4d624954d848b8f`，只核对字节而未执行。
本次没有替换该交接或生成新的现场执行命令。

[准确修复提交的 CI 37569620992](https://github.com/kongbu0621/infra-local-hand/actions/runs/37569620992)
已在 attempt 1 completed/success，head 为上述准确提交。classify-change、Linux、Windows
三个 job 全部成功；两平台的源码测试及独立安装 wheel 验证步骤均 success，未触发重跑。
平台不适用的 skipped 步骤不计入现场能力证明。

离线复核已完成。W2 仍 CONSUMED / FAILED，历史 PID_RECHECK 的具体分支仍 UNKNOWN；
journal 维护未启动，扩容、新 boot 核心采用和 H01/Q4/H11 没有因此通过。
新的受影响现场窗口仍须按 AGENTS 的现有规则取得准确范围的 Owner B 和独立 C。
