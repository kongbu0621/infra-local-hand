# 首次公开发布：Owner 决定

- Decision authority: repository Owner (`kongbu0621`)。
- Event ID: `LOCAL-HAND-PUBLICATION-20260921-01`。
- 决定来源：本会话 Owner 的明确指令；下列原文是 committed decision copy。
- 已批准候选：`b763bd6714721d22278086db559fa3f6684aad7b`。
- 候选 Git tree：`0dbf04548f42bbb3693524ae5bd8adedeecd2de1`。

> 公开 `b763bd6` 候选及其中的治理摘录，暂不添加许可证；不上传 SOP 历史和实机原始证据

## 生效范围

批准公开该候选的 54 个源码、测试、构建、工作流和文档文件，包括治理摘录。保留本产品从文档 A、独立 CLOSED 记录 C 到实现 D 的 7 个原始提交；这条独立历史不是 SOP Git 历史。上游 SOP 原始仓库、被排除的部署脚本、实机 Task/Result、凭据、机器日志及其他原始证据不在发布范围。暂不添加 LICENSE，也不从 Public 可见性推导许可证授予。

本决定批准治理摘录的公开披露；不自动批准等价采用，也不替换 AGENTS.md 的固定 Private companion rule source。规则 R 和 S1 批准文档 A 均保持不变，三份批准文档保持原始字节。

本决定不把云端隔离验证变成 GX10 实机验收，不完成 S2 服务切换或 artifact-ledger A2。Owner 已要求 Windows 延后、先运行 GX10；状态分别记录。

## 可核实历史

| 对象 | 完整 SHA |
| --- | --- |
| 规则 R（仅引用，不导入其 Git 历史） | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| 批准文档 A | `7246b850ffdc2709e359b09cac99f0fb88bda209` |
| 独立 CLOSED 记录 C | `48730d037a1d5c50e8380a60d5b8399e90e1e01c` |
| 已验证并批准公开的实现 D | `b763bd6714721d22278086db559fa3f6684aad7b` |

发布过程中仅增加批准记录、状态说明与 GX10 验收文档，不改变候选产品代码、测试、构建依赖或 CI 内容。首次公开交付使用一次性 GitHub Actions 导入经过摘要核对的独立 Git bundle，以保留原始 SHA 和 A/C/D 顺序；随后通过包含 D 的合并提交发布 main，不强制改写已有 refs。临时导入 workflow 从最终 main 文件树移除。此记录本身不宣称远端导入已经成功；以远端 commit、ancestry 和文件摘要检查结果为准。
