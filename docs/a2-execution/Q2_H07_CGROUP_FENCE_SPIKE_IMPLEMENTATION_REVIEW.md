# H07 cgroup 监督原语实验：实现与验证记录

2026-09-29。仅 `LH-Q2-H07-CGROUP-FENCE-SPIKE-v1` 的 F1–F4。

当前状态（2026-09-30）：两轮已运行，额度 **2/3**；**第三轮 BLOCKED / NOT_DISPATCHED**。
首轮账户 setup 失败、probe 与六案 NOT_RUN，原报告 **UNKNOWN_RETAINED / cleanup.verified=false** 保留。
Owner 批准的限定续验 A `a08a5055`、独立 C `7d33c698` 仅接受指定首轮历史未知；后续停止条件保持。

准确 HEAD `9d8328cf742fa130c265de23b1b9085b9e8a0581` 的普通 CI `36655111148`
attempt 1 已 3/3 成功，见[准确证据](evidence/q2-h07-cgroup-fence-spike/round-2-ordinary-ci.json)。
同一 HEAD 的第二轮 `36662298613` attempt 1 为 **FAILURE**：probe 支持，
账户创建与删除完成，原报告 `cleanup.verified=true`、`residuals=[]`；但 C1 缺
launcher/account binding，原报告为 **UNKNOWN_RETAINED**，C2–C6 为 NOT_RUN。
C1 的 `s_exit=-9` 在 `s_created` 后约 2.075 ms，早于 `close_requested` / `b_kill`；
未取得 `s_armed`、`s_credentials`、request 或 worker 证据。该时间线不证明信号发出者或根因。
第二轮新增 UNKNOWN 触发停止条件，首轮限定豁免不覆盖它；当前仅继续只读定位。
完整结果和原件身份见[第二轮结果复核](Q2_H07_ROUND2_RESULT_REVIEW.md)及[第二轮清单](evidence/q2-h07-cgroup-fence-spike/round-2-verification.json)，
续验边界及第三轮既有缺口见[续验实施复核](Q2_H07_R1_CONTINUATION_IMPLEMENTATION_REVIEW.md)。
以下原实现、0/3、[首轮记录](#round-1-2026-09-29)及当时停止状态保留其历史时点，不覆盖后续准确决定。

## Authority 与准确边界

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，直接来源及完整性沿用 AGENTS。
- A：`71c7e842c724650a0e949a63bb898699b41107be`，三文档原字节和历史 OPEN 标签不变。
- B：[准确 Owner 决定](../governance/Q2_H07_CGROUP_FENCE_SPIKE_OWNER_DECISION.md)，2026-09-29 19:01:33 +08。
- 独立 C：`8deeed492edeb7e5fa79cbe95c123a27e69f9f92`，仅关闭 bookkeeping。
- 实验实现提交必须从 C 下降；本记录和源码属于随后独立的实现提交。

## 交付与阶段状态

下表保留首个实现交付时的阶段缺口；第二轮已取得的 probe、C1 与清理事实见页首及第二轮复核，不能由历史 NOT_RUN 覆盖。

| 阶段 | 已交付 | 仍待真实证据 |
| --- | --- | --- |
| F1 | 固定 C11 helper、有界临时 fixture、准确源码与环境准入、独立手动 workflow | 托管 runner 实際能力、唯一 probe 与清理回执 |
| F2 | 原帧与身份、FD 生命周期、双钟截止、严格收件验证器及非特权测试 | 真实进程/过滤器/内核组合的执行证据 |
| F3 | C1–C6 的固定注入点、独立 T/G 收件及预期缺证判据 | 六个实际病例尚未派发 |
| F4 | 本实现审查、逐例原始回执/资源/摘要保存与验证代码 | 真实 run_id、artifact、原件摘要及限定资格判断 |

源码位于 `tests/e3_host/spikes/q2_cgroup_fence/`：`helper.c` 负责原生
T/G/S/W 生命周期；`run_fixture.py` 负责准确来源、setup、预算、实物记录与清理；
`verify_receipt.py` 独立派生证据判据。两个测试文件只运行离线负例。
`.github/workflows/q2-cgroup-fence-spike.yml` 仅 `workflow_dispatch`，不随 push/PR
启动特权实验。现有普通验证 CI 仍会收集新增离线测试；这不消耗实验轮次。

## 实现复核

已完成原生控制、fixture、独立验证器及跨模块的审查。已处理：

- root 对 runner checkout 的 Git 核验仅信任准确目录，不修改全局 Git 配置。
- UID/GID 不错误地排除专属 system 账号；清空 capabilities、附加组，启用 NNP
  和固定 seccomp，并由 G 读取原 S 的实际凭据/过滤状态。
- 保留原 clone/pidfd，关闭所有未登记 FD；原双流只有 T 读取，G 观察真实 EOF 条件。
- 修复 syscall 过滤跳转；以纯 BPF 指令解释检查白名单控制流，真实内核安装留待 probe。
- 原帧携带 S 发生时刻，与 G 收件时刻分开；G/S 都检查原双钟及 17 秒接受截止。
- C2 保留两次晚到尝试及拒绝；C4 在实际双流已有 payload 后才触发 S 崩溃。
- `CLOSE_REQUESTED` 后已接受的在途创建仍可能完成；拒绝新的接受及 FENCED 后创建。
  延迟身份回执不能被伪称为一次新的创建，也不能补发原请求。
- C3/C6 的身份或控制缺证保留 UNKNOWN；T 清理不会合成 G 摘要或业务成功。
- 配置限额后读回，逐 probe/病例保存实际 cgroup 身份及 CPU/memory/pids 计数；
  严格限制诊断与原流，清理拒绝身份已替换的对象，保留失败原件和待上传证据。

原 PRO6000/guest、旧 runtime、原 wrapper/业务输入、原 Q2 唯一批次及生产模块
没有被本实验执行或替换。此实验也不证明任意恶意 native 程序的完整沙箱。

## 验证与派发

[同次提交的离线验证清单](evidence/q2-h07-cgroup-fence-spike/offline-verification.json)
固定全部实验源码的大小及 SHA-256。最终非特权测试 **85 PASS**（收件验证器 73、
fixture 准入/有界清理 12）；严格 C 编译零警告，纯解析/BPF 自检 **39 PASS**。
Python/YAML/Bash 语法与 diff 检查通过。没有在不具资格的 cloud 上运行真实 clone/cgroup probe。
模拟收件负例和纯 BPF 解释结果不能替代 F1/F3 实机结果。

本记录发布时，实验手动派发 **0/3**，真实 fixture 结果 **NOT RUN**。
当前云浏览器的 GitHub 页面呈未登录状态；插件能发布源码和读取 CI，但未提供
新的 workflow_dispatch 能力。实际派发需要该浏览器具备 GitHub 登录状态。
Owner 的实验批准已有效，无需重批相同范围；此处是访问状态，不是新 Gate。

下一次实际派发前，executor 必须核对当前准确 D，登记本轮序号/原因/已用额度，
在 GitHub 页面以完整 `expected_commit` 触发并记录 run_id/attempt。应答不明先查
已有运行，不补发。原 A 的清理、UNKNOWN、UNSUPPORTED 和三轮额度停止条件保持。
后续真实结果需追加准确 D/run_id 的 F4 记录，不能将本文件的离线验证改称实机通过。

## 准确实现 D 的普通 CI 复核

D：`e10dbfcb7f354f27b009c1b63c533fb72ac1a677`，tree
`f60e745fcace90898e92b5717c0d4ef79d5b55a9`，直接 parent 为上述独立 C。
[run 36562115482](https://github.com/kongbu0621/infra-local-hand/actions/runs/36562115482)
为普通 `push` / attempt 1，三个 job 全部 SUCCESS。
[准确 CI 清单](evidence/q2-h07-cgroup-fence-spike/ordinary-ci-verification.json)
保留 job IDs、计数及原日志摘要。

| 检查 | 结果 |
| --- | --- |
| Linux 源测试 | 2831 PASS / 51 SKIP |
| Linux root-only collector | 16 PASS |
| Linux 安装验收 | 94 checks / 292 commands PASS |
| Windows 源测试 | 787 PASS / 996 SKIP |
| Windows 安装验收 | 10 checks / 10 commands PASS |

Windows 的新增 module skip 是 Linux-only fixture driver；收件验证器离线测试
正常收集。没有通过跳过新增跨平台收件测试掩盖失败。

本次只读复核及文档登记没有新实验 dispatch，额度仍为 **0/3**。云浏览器在
安全登录交接后仍呈 GitHub 登录页面，尚无已登录的可见证据；未点击实验运行。
这不是 GitHub 服务不可达或实验 UNSUPPORTED 的证据，真实实验仍为 NOT DISPATCHED。
原 Q2 未发起，F1/F3 实机能力仍未证明。

本后续提交仅登记证据，实验实现文件与准确 D 字节不变。若 main 已包含本登记，
后续派发必须冻结并填写届时当前完整提交、核对实验源码与上述 D 一致，不能
在 main 前进后仍填写旧 D 并将 identity 拒绝视为实验运行结果。

## Round 1 (2026-09-29)

[run 36577764454](https://github.com/kongbu0621/infra-local-hand/actions/runs/36577764454)
为 `workflow_dispatch` / round 1 / attempt 1；准确运行源码
`6b085d9ceb536b9785ea683cd108e92cd8a4eec4`。其 parent 为上述 D，实验源码字节相同。
`main`、完整 `expected_commit`、round 与 reason 均正确；源码准入步骤 SUCCESS。
job `109437700015` 在创建专属账户时退出 3，上传证据步骤 SUCCESS。

[首轮复核清单](evidence/q2-h07-cgroup-fence-spike/round-1-verification.json)
保留身份、输入、artifact 和原件摘要。artifact `11038133434` 为 3830 字节，
ZIP SHA-256 `5a48b64ae1a4c38e2ff33aca7d2c47b046acfb2f1232778d527e852f5e307a8e`；
ZIP、manifest 两项文件摘要和 11 项源码闭包均已独立核对。
原 ZIP 已另行保存，原报告和诊断不被本修复覆盖；公开仓库只记脱敏结果及摘要。

失败诊断为 `configuration error - unknown item 'CREATE_MAIL_SPOOL'`。
`run_fixture.py` 错将 useradd defaults 的设置传给 `--key` 的 login.defs 接口，
重复引入了同仓 `q2_prepare.py` 已修复的参数问题。最小修复只删除
`--key CREATE_MAIL_SPOOL=no`，保留 system/no-home/no-log-init/nologin 等限制。
历史 recovery 中用于核验旧失败的参数保持原样。

真实 capability probe 未运行，C1–C6 **0/6**，没有创建 cgroup 的记录。
helper 已构建且删除有据；账户创建尝试失败后没有建立准确身份，因此账户是否
残留仍未知。报告原值为 `UNKNOWN_RETAINED`、`cleanup.verified=false`；
独立收件器派生相同状态且结构错误为空。此处“结构有效”不代表实验通过。
job 完成、托管 runner 标签和参数错误本身都不能替代原账户清理证据。

[本次修复离线清单](evidence/q2-h07-cgroup-fence-spike/round-1-repair-offline.json)
记录修改后源码摘要与 **88 PASS / 0 SKIP**。新增三个非特权 mock 用例覆盖正常
账户参数/身份，以及非零退出和捕获不完整时不重试、不删除未知账户、保留 cleanup
未证。未在 cloud 执行真实账户/cgroup/probe；该结果不解决首轮清理未知。

根据准确 A 实施方案“非预期 UNKNOWN 或清理未证阻断后续轮次，不能换 runner
遗忘未决”，**剩余 2/3 额度暂不可使用**，不得 Re-run 或派发第二轮。
范围内源码修复无需重复批准，但不能据此豁免停止条件。若无法补足原轮次清理
证据而需改变停止条件，必须先形成具体变更方案并取得对应决定；本记录不构成该决定。
冻结 A/B/C、生产后端和原 Q2 startup 均不变。

## 账户参数修复的最终普通 CI

准确修复提交 `9596c784932dc8990e0225e0f46bf292d7e7b3ea` 的
[run 36579157335](https://github.com/kongbu0621/infra-local-hand/actions/runs/36579157335)
已于 2026-09-29 22:11:44 +08 完成，`push` / attempt 1，三个 job 全部 SUCCESS。
[准确 CI 清单](evidence/q2-h07-cgroup-fence-spike/round-1-repair-ci.json)
分别记录源测试、root collector、安装验收以及获取的解码日志摘要。

| 检查 | 结果 |
| --- | --- |
| Linux 源测试 | 2834 PASS / 51 SKIP |
| Linux root-only collector | 16 PASS |
| Linux 安装验收 | 94 checks / 292 commands PASS |
| Windows 源测试 | 787 PASS / 996 SKIP |
| Windows 安装验收 | 10 checks / 10 commands PASS |

新增三个账户 mock 在 Linux 收集，Windows 沿用 Linux-only fixture module 的
整模块 skip；该边界没有扩大。源码修复完成，不将普通 CI 成功转记为首轮清理、
真实 cgroup 资格或第二轮准入。当前总额度仍 1/3。
