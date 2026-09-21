# 首次公开发布复核

日期：2026-09-21。复核代码及文档交接基线：`3a8591cf8d175d7ab157aca68ba5bc488c51733a`。随后仅增加本状态记录，不改变冻结产品候选。

## 发布与来源

- 冻结候选：`b763bd6714721d22278086db559fa3f6684aad7b`。
- 原始 tree：`0dbf04548f42bbb3693524ae5bd8adedeecd2de1`。
- 从 GitHub 全新 clone，核对候选全部 54 个文件的 Git blob、SHA-256 和大小；通过。
- 原始 7 个独立提交完整，A、C、D 顺序保留，C 是 D 的祖先，D 是公开 main 的祖先；通过。
- `git fsck --full`、工作树 clean、三份批准文档相对 A 原始字节不变；通过。
- main 相对候选仅有公开决定、披露状态说明、来源清单及 GX10 任务书等文档变化；产品源码、测试、依赖和原 CI 工作流字节未变。
- 未添加许可证；未导入 SOP Git 历史、上游原始规则全文或实机原始证据。规则 R 对象不在新仓库。
- 一次性导入任务第 1 次在发布分支时被 Actions token 的 workflow 权限拒绝，文件/历史验证已通过；由现有 GitHub 连接单独发布准确 CI 文件后，第 2 次导入成功。未扩大 token 权限，失败记录保留。临时导入 workflow 与 bundle 从当前 main 文件树移除，其独立发布记录仍在历史中。

[独立历史导入记录](https://github.com/kongbu0621/infra-local-hand/actions/runs/35578331863)；[候选逐文件清单](governance/PUBLISHED_CANDIDATE_MANIFEST.json)。

## 首轮 GitHub CI

验证提交为上述 main 基线，完整工作流总体为 **FAIL**，因为 Windows job 有失败。

| 项目 | 实际结果 |
| --- | --- |
| Linux / Python 3.12 源码编译 | PASS |
| Linux 源码测试 | 139 passed，38.86 秒 |
| Linux 独立 wheel 构建、runtime venv 安装 | PASS |
| Linux 源码外安装态验证 | PASS：25 checks、66 commands |
| Linux bootstrap 语法与重复 bootstrap 身份检查 | PASS |
| Windows 源码测试 | FAIL：1 failed、129 passed、9 skipped，107.08 秒 |
| Windows 后续 wheel/平台步骤 | 未执行；不能由 Linux 结果替代 |
| GX10 本机验收、新版服务切换 | 尚未执行 |

[Linux job 与证据](https://github.com/kongbu0621/infra-local-hand/actions/runs/35578834478/job/106266768844)；[Windows 失败记录](https://github.com/kongbu0621/infra-local-hand/actions/runs/35578834478/job/106266768781)。

Windows 失败用例为 `tests/test_local_hand_configuration.py::ConfigurationTests::test_linux_bootstrap_rejects_bad_profile_before_filesystem_mutation`，实际断言为 `invalid_profile` 未出现在捕获的空 stderr 中。此处记录观察结果，不把它推断为已定位的根因。Owner 已要求 Windows 延后；本次不修改冻结候选来处理 Windows，也不把跨平台状态写成 PASS。

Linux CI 运行于 GitHub hosted runner，验证的是发布基线的代码，不能代替 GX10 Linux/aarch64 实机。随后已在 GX10 按 [GX10 S1 任务书](GX10_S1_RUNBOOK.md) 从准确候选 D 开始，使用全部新的 checkout/build/runtime/evidence 目录执行验收；发现的失败和修复没有改写原始候选身份。

## GX10 修复候选主干发布

GX10 隔离验收以原始输入 `b763bd6714721d22278086db559fa3f6684aad7b` 开始，发现缺陷后保留失败轮次并形成修复链。最终修复候选为 `1e2f9dce87e57c34a35fe3a6a75a8c784181ba83`，tree `12190df12ec03c120e397b6f6606168cce337197`。Owner 随后明确要求将其提交并直接推送主干，不使用功能分支；决定副本见 [Q6_MAIN_PUBLICATION_OWNER_DECISION.md](governance/Q6_MAIN_PUBLICATION_OWNER_DECISION.md)。

该授权不改变三份批准文档基线 A，不批准上传实机原始证据，也不表示 Windows、现役服务切换、S2 或 artifact-ledger A2 已完成。完整机器日志、wheel 和 evidence ZIP 继续只保留在 GX10 本地。
