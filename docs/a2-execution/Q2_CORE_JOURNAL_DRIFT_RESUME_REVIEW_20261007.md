# Journal 漂移诊断后接续：DR1 验证与准确候选冻结

2026-10-07（Asia/Shanghai）。本记录对应准确批准的 DR1–DR2。
候选已发布，新增绑定、本地离线核对、准确 CI 与最终交接冻结全部完成；DR1 完成。
DR2 **NOT STARTED**，本次唯一替代窗口尚未消耗。所有旧窗口仍 CONSUMED，旧 W2 交接禁止重跑。

## 准确批准与候选

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本执行者在本会话完整读取固定规则，
  源 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 匹配。
- A：`4f2a6a37ad5afd027dbde0f1656a3552750cb3b2`，
  `LH-Q2-CORE-JOURNAL-DRIFT-RESUME-v1` / DR1–DR2；三文档摘要和历史 OPEN 字节保持。
- [Owner B](../governance/Q2_CORE_JOURNAL_DRIFT_RESUME_OWNER_DECISION.md)：
  `LH-Q2-CORE-JOURNAL-DRIFT-RESUME-CLOSURE-20261007-01`，逐字保留紧邻请求和批准。
- 独立 C：`e13f8efcb8dee4e4280dd722f7836ea94a27b83b`，只含 AGENTS.md 和 Owner 决定。
- 直接实现子提交 D：`309c6e1cacfdf05cabeeac9d27f487acad524b61`，tree
  `f5d8d720eb34f1165cfe026db1a13e1c1e78a223`；C/D 分开提交并已非强制发布至 main。
- 已验证诊断修复：`711932aae3370c7f2ed5c1a51ac82d3b0f67a6e5`。
  原 663 项本地测试、八输入绑定和准确 CI 的 [既有记录](Q2_CORE_JOURNAL_DRIFT_DIAGNOSTICS_REVIEW_20261007.md)
  继续有效；本次新增差异单独核对，不合并测试计数或沿用旧 CI 代替新 D。

## 最小实现与验证

实现只修改 host 的新增 DRIFT 常量、`growth_sources` 和 `WriterObserver.binding`。
来源门固定修复→A→C→D 祖先链，C 本身拒绝作为 D；三文档 SHA-256 必须匹配。
原全部来源、祖先、源码字节/长度和输入检查保持。writer manifest 新增
`drift_resume={A,C,repair}`，交给原 manifest 摘要及两 CLI 的同窗校验。

独立完整 host AST 对比证明除此三处外无变化。guest、kernel 及其余依赖字节不变；
用同一准确 D 从修复版与新 host 生成的完整 writer payload 字节相同。
scanner、payload 提取函数、固定入口、拒绝条件、读取顺序、v2/progress、期限和预算没有变化。
实际生成 payload 内存编译通过，没有执行原现场 writer。

普通宿主 Python 3.10.12 / pytest 8.4.2 的相关回归 **106 passed、0 skipped，1.31s**：

```text
python3 -B -m pytest -q -p no:cacheprovider tests/test_e3_q2_journal_diagnostic_resume.py tests/test_e3_q2_journal_host_read.py tests/test_e3_q2_journal_growth_coordinator.py tests/test_e3_q2_journal_scan_work.py::test_source_admission_98304_boundary_only_for_maintenance_sources
```

覆盖准确来源、断开的旧/新祖先、修复身份、三文档摘要及 bookkeeping 候选拒绝；
旧 W2/未绑定修复不能充当新候选。两 CLI 合成验证保留首次报告和 checkpoint 1→2 顺序，
相同静态 manifest 不代表复用旧 PASS；另一 D 的报告被拒绝且不触发新扫描。
manifest 缺少本范围、错误 A/C/repair 或错误摘要均在 marker/transport 前拒绝。
原源码等值/超界、认证、失败不可重试及原维护动作顺序的隔离回归保持。
这些测试不调用原现场，不证明实际准入、扫描稳定或维护成功。

## 准确源码与静态输入

独立干净检出固定于 D。原 `growth_sources` 验证十二源码成员、旧/新批准和准确身份。
原 `Inputs` / `freeze_growth_inputs` 在普通身份下通过八份原静态输入的 no-follow、
O_NOATIME、保护、长度/摘要及 fd/name/atime recheck，无弱读回退或权限变更。

| 对象 | 字节 | SHA-256 |
| --- | ---: | --- |
| host 源 | 68917 | `f07522e158448b17cdc18eb634d6af6478f5aa021460e567ea9bc7d68b3dc26d` |
| guest 源 | 68195 | `47bd23ac35a00a79b58f132363ec198f5690b62262493e2ecaead5b975bdfc97` |
| root writer payload（准确 D） | 26405 | `cc0f0dbc9268cb79baa9e045b102a1cbbd4d0cc984412dcf39eb6b633bea2a3d` |

writer / guest loader 摘要分别仍为
`081d3bed41e9f49153096cb893ee20980182831d551c41b9504b886fd0c46aca` 和
`dbe142b96c7dd49c00f68c7a0fd4df16c6ab19b9bb6aa1984e5583cef946a191`。
明确 24 B 合成 descriptor 的压缩 bundle 为 36342 B、完整 remote argv 为 50531 B；
明确合成 request 的 writer argv canonical 为 36282 B。均在原界内，未生成真实现场
pre/post descriptor 来提前取证；实际包和工具资格仍在原 DR2 窗口内逐项检查。

五个原静态绑定继续与 W1 和前次本地核对一致：

| 绑定 | SHA-256 |
| --- | --- |
| source | `2cb178702a4aedfc1b9366eab4d8e111f73d8130bf38be96460116ceebb14caa` |
| plan | `efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c` |
| inventory | `a5ea03d6311884a8ff47244271b3ccfecc18d934db9ca66172668cf8078851fd` |
| description | `64c6cfc7b773aa51af33cf971da672786c49965e16cc75923fc6fc25b1ac4814` |
| horizon | `3ecc6bd649d4e33bdc08283c8b76984fad286a1b484f7df0452b59a470033c82` |

## CI 与交接状态

[准确 D 的 CI 37575372661](https://github.com/kongbu0621/infra-local-hand/actions/runs/37575372661)
为 attempt 1，已 completed/success，head 为准确 D。classify-change、Linux、Windows
三个 job 全部成功；两平台源码测试及独立安装 wheel 验证步骤均 success，没有重跑。
平台不适用的 skipped 步骤不冒充现场能力。本地没有启动或重跑现场窗口。

最终独立私有交接已冻结，6810 B、mode 0600，SHA-256
`6fe7fe1bd0de8df3464c920740bde4758ebb4424c0d30644be511007c6f5ef00`。
它保留原参数、原终端认证和同窗三项
manifest/window/writer 传递，新增准确本范围绑定；原文件和所有旧 shell 变量保留。
Bash 语法、两段 JSON 处理器编译及合成数据检查通过：准确三项交接原样保留，11 类错误
绑定拒绝，失败首因/子报告进度与最后成功报告分别保留，缺失明确为 null。
没有执行 shell 主体或现场 CLI。最终 CI 通过后，只将待决文本的 CI 说明更新为准确完成
状态；已验证的 Bash 主体逐字不变，语法再核对通过。待决草稿另行保留，禁止执行。
原 W2 6343 B 交接摘要仍为
`fad08f6295f506cd2609693b86bbe28e2c1546943798daf6a4d624954d848b8f`；原件未改动。
新 `LH_Q2_DRIFT_*` 变量仅防同终端误粘贴，不冒充跨进程硬性防重启，不能通过换 shell、
unset、改 ID 或删除对象重开窗口。摘要长度/哈希对应 shell 保留 JSON，不冒充原 CLI stdout。

现阶段无现场 Window/observer、sudo/writer、当前 boot/proc/VM 读取、工具资格探针或 SSH。
DR2 只能由 Owner 在已有真实本机前台终端按准确交接一次执行。新窗口开始即消费；
失败不退款、不重试、不补采、不重连、不改变检查/预算、不清理、恢复或回滚。
预检全部通过，原 execute 仍保留再次准入、checkpoint 2 和本地 SSH 配置检查，随后
同窗完成尚未消费的原 journal 维护。只有原合格 receipt 才证明维护成功。
新 boot 核心采用、H01/Q4/H11 和扩展支线保持不执行。
