# sudo 修复后单次核心验收：准确提案基线

- Authority：Owner；状态 **OPEN / NOT APPROVED**，不是 Owner B 或 CLOSED C。
- Scope：`LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1`，仅 S1–S3。
- 准确 A：`f9ba6fbc2fa983c46322a00f3385af172fed7cb4`；tree：`45b9d9dff11e87a8c83453bdab5d93c0b1ab5734`。
- 源码修复基线：`432f3f4c5a36735d38869261968fc44583f14023`，不是本新增范围的实现D。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；[直接固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)已读取。
- 规则SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；Owner mandate、no exceptions、原change control保持。

| 准确 A 中的权威文档 | SHA-256 |
| --- | --- |
| [ARCHITECTURE.md](../a2-execution/q2-core-post-sudo-acceptance/ARCHITECTURE.md) | `1470cba64730bdfdfc6db806fe8ad1e0cf5f2e12c2af3f3bfdfd2c9fe40f8ae4` |
| [IMPLEMENTATION_PLAN.md](../a2-execution/q2-core-post-sudo-acceptance/IMPLEMENTATION_PLAN.md) | `63138edbba669c7d2ea111f7ad8041aa2e30b039c7d730ecea15d45a3f37bb1d` |
| [REQUIREMENTS.md](../a2-execution/q2-core-post-sudo-acceptance/REQUIREMENTS.md) | `40430bf96501bcf738bb3137a509ce8600844398d442ed5906764646151c34ab` |

## 已完成和为什么还需本次决定

上一修复的[CI 37270712716](https://github.com/kongbu0621/infra-local-hand/actions/runs/37270712716)已3/3 success，Linux 5157 passed / 88 skipped及独立installed 94 checks / 292 commands，Windows 1808 passed / 1327 skipped及installed 10/10。
截图报告本地321通过/10跳过和两次私料内存构包一致；这不是新现场执行或新身份包发行。
两次准确旧批均已消费；根AGENTS明确新的现场请求须独立准确批准链。既有sudo修复和其它不受影响CLOSED开发不需重新批准。

本A只新增一次固定 `lhqcore-20261005b`：S1接齐双旧原件、新身份、保留承诺与准入；S2验证准确D和真实包；S3按H01→Q4→H11运行一次并收回真实证据。
两个旧批的十原件、历史UNKNOWN、各完整承诺全部保留，不重装旧安装或清理现场。
同设备三批guest逻辑基准828MiB/49536、CPU累计6270s，另加更早guest义务；host当前条件192MiB/48，未计入的更早host覆盖/金额仍UNKNOWN，不宣称完整或排他预留。
核验前三个carrier的配置上界为3GiB/384pids，两个旧scope各两次观察全部通过后才进入新批原2624MiB/1160界；不新增整机内存探针。
四次有界SHOW计入新原窗口/预算，不构成额外SSH轮次。凭据、权限、原每批上限和停止规则保持。

两份独立只读审查核验了UUID、总额、schema、第二旧非零传输及pre-business前提，修清了不应新增的内存准入歧义、helper计数、最终basename复核和离线发行/live消费先后。
A提交只有三份提案文档；未新增实现、测试、fixture、发行摘要、marker或现场请求。

## 建议决定文字（尚未收到）

> 按原 R，批准 A `f9ba6fbc2fa983c46322a00f3385af172fed7cb4` 的 `LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1`，接受双旧历史 UNKNOWN、全额保留承诺及文档中的 host 容量和前置并发边界，关闭该范围 Gate，执行 S1–S3；先独立 C 再实现，仅新增一次固定 05b 请求，失败不重试、不重连、不清理，支线暂停，生产 E3 限制保持。

收到准确Owner决定后，保留逐字B及稳定事件来源，另作仅bookkeeping的C；不能把C与实现合并或伪造已批准状态。
一般“继续”、本A发布或CI不授予新现场请求。批准前本地Codex只复核既有私料与方案，不实现或发新批次；无需再向Owner索取已有十原件或未保存的sudo原stdout。
