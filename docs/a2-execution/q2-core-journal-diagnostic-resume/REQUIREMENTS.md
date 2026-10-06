# Journal 诊断修复后的一次替代预检

状态 **PROPOSED / Gate OPEN / NOT APPROVED**。Scope：
`LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v1`，仅 DR1–DR2。
原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、Owner authority、无例外及
准确 A→Owner B→独立 C→D 顺序保持；本文与[架构](ARCHITECTURE.md)、
[计划](IMPLEMENTATION_PLAN.md)构成待批准方案。

## 事实与唯一新增范围

目标仍为原 journal 256→512 MiB 扩容，解除 Local Hand 核心链的容量阻塞。
[终端认证现场记录](../Q2_CORE_JOURNAL_TERMINAL_AUTH_FIELD_20261006.md)明确：
候选 `202c70a15c0e52940d8544c3ae3c41e0b57ebaec` 的唯一 T3 替代窗口已消耗并关闭；
checkpoint 1 返回 exit 3，marker、SSH、关机、备份、镜像增长、VM 启动、ext4 增长均为 0。
stdout 仅留 648 B 长度及摘要，没有原文；具体 writer 根因和 root payload 是否执行均为 UNKNOWN，
不能由提示、长度、摘要或后续测试恢复。

`ac08b519f741b301f37959808749cb9755359123` 保留未来有效失败报告的 reason；
后续隔离审查又定位到生成 payload 的异常类型不一致及安全错误信息丢失。
诊断保留修复已发布为 `aba18e33f79295f3df1964606e389297d1a8a26a`，本地验证为
**428 passed、3 skipped**；其 [CI 37450280680](https://github.com/kongbu0621/infra-local-hand/actions/runs/37450280680)
仍在进行中，尚无成功结论。
这些是确定的代码/诊断缺陷修复，不是已查明或解决历史现场根因；SKIP 不计 PASS。

本提案唯一新增现场范围：修复验证、发布及准确绑定完成后，明确允许**一次**替代预检窗口，
沿用 `lhqjgrow-20261006a`、原对象、输入和维护流程。所有旧窗口继续保持失败/已消耗。
普通“继续推进”指令、代码修复或 CI 成功均不代替本范围的准确 Owner B。

## 全部继承边界

原扩容 A `59948ec4fedb807a31cdbff77acc134e84414160`、宿主读取 A
`2b4448c7b89d1910840f7aee2ae2b781f970e179`、终端认证 A
`2b236865dc0a89e475c4021cac44d7193f252f67` 的未受影响要求完整继承。
原安全校验、五镜像身份、writer 排他检查、输入 pin、正常锁、内容保留及容量门均不得放宽。

- 本人仍在真实本机前台终端以普通身份运行，仅固定只读 writer 沿用已批准的终端 sudo 认证。
  不增加 helper、权限、sudo 探测、认证预热、askpass、整体提权或系统配置变更。
- 窗口前仅做原静态准备与 TTY 资格检查；首次新预检起同一双时钟 900s，780s 后不启新修改。
  两次 CLI 绑定同一准确 D、终端、输入、nonce 和窗口；认证仍计入单调用 15s，不暂停或刷新时钟。
- 替代窗口仍只有原八个 writer 检查点，每点一次；历史调用单独保留，不挪用旧 PASS。
  任一失败立即停止，不以剩余检查点重试，不再开窗口、不重连、不补采、不清理或自动回滚。
- 原预算与观测限制保持；旧承诺及已发生用量/UNKNOWN 不置零、不退款，不新开独立预算池。
  跨全部维护方案累计仍最多一个 marker、两条维护 SSH，以及正常关机、完整备份、镜像增长、
  VM 启动和 ext4 增长各一次。只在全部原门通过后使用尚未消费的维护动作。

成功定义仍为原身份/内容保留、备份、两层增长及普通可用至少 400 MiB/32768 inode 的完整维护结果。
失败可能停留在 guest 已关闭或增长部分完成的状态；不保证认证或诊断修复后后续条件一定通过。
本范围不执行 H01/Q4/H11，不批准新 boot 的核心采用；支线及 production
`E3_SUPERVISION_UNVERIFIED` 状态保持。维护完成后再根据真实 receipt 准备核心验收。
