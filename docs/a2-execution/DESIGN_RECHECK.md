# A2 执行设计再次复核

日期：2026-09-22；复核输入：main `22563ab947a928060e8e3092ef7c8510f1db25b1`，
原拟议文档 A `9cc628c9679e1530a2be3c7e7efec829d559d438`。
范围：Owner 要求再次多角度复核；本轮修订设计并验证既有代码，不开始新 scope 的实现。
规则 R 保持 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，直接读取固定来源；**Gate OPEN**。

## 确认并修订的问题

这些是会误导后续实现的设计缺口，不宣称尚未编写的程序已经存在对应运行漏洞。
四路独立审查分别检查作业恢复、接入交付、固定 Ledger 源码、阶段与治理衔接；重复发现合并计数。

| ID | 具体反例／问题 | 修订与验收映射 |
| --- | --- | --- |
| DR-01 | 已记录意图、manager 尚未启动时取消；当前 cgroup 为空不能排除延迟启动 | A05 同一启动/取消围栏、撤销未来启动证明；V04 |
| DR-02 | 单 job 未超预算，但排队记录、重复核对、原件与 ZIP 并存耗尽账本空间 | A05 全局容量/控制预留、核对预算与封存峰值；V02/V07/V08 |
| DR-03 | JSON 转义与整数精度使 Python/JavaScript 对同一语义生成不同摘要，SDK 可能先覆盖重复 key | A03 完整 typed envelope、ASCII 逻辑引用、安全整数、唯一规范字节和原始解码；V02 |
| DR-04 | 只比 JWT claims，未明确签名/密钥/算法检查；issuer 撤销不一定即时传播 | A08 首版签名 JWT、可信 JWKS、验签/时间/算法、本地授权及实际撤销时限；V09 |
| DR-05 | 分块下载器可能误以为能取得平台 token 或 `_meta` 能自动保存文件 | A07 宿主已认证回调与有界 writer；E2 合成验证、E4 当前 Work 实测；V08 |
| DR-06 | 调用者可绕过流程顺序，凭 prepare 直接提交 NAS，即使必需测试失败 | A02 broker 强制先决证据 DAG，接受及 spawn 前都验证，同候选/环境绑定；V01 |
| DR-07 | “保留失败现场”超过固定上游测试 TemporaryDirectory 自清理能力 | A04 只承诺 broker 管理材料/残留；标记 EPHEMERAL_BY_UPSTREAM_TOOL；V07 |
| DR-08 | TMPDIR 不可用时 Python 回落到系统临时目录或 cwd，环境变量不构成隔离 | A02 实际解释器目录绑定、OS 可写根限制、缺失/只读/满盘负例；V02 |
| DR-09 | E5 包含新 broker，但 S2 的冻结/健康/回退步骤只覆盖旧 v1 | S2 三层加入 MCP/CLI 准入、排队启动、两套账本、authority/epoch 和交叉资源回退；AX-V11/S2-V04/V05 |
| DR-10 | E1–E3 未给具体包/模块落点，MCP extra 或独立包路线未选定 | 实施方案增加最小职责表；同发布独立包、标准库 job 核心、可选 mcp extra、Plugin 独立资产；V10 |

定点回审确认原问题已覆盖；回审提出的 S2 交叉资源恢复措辞差异也已统一：
核对完成、风险解除且有准确恢复决定才恢复，UNKNOWN 继续保持维护态。
补充明确 prepared venv 不移动、源码副本与生成物分离，避免固定 console script 的绝对入口失效。

## 事实核对

- Ledger 固定 `6bd6acfbe5c35d581891eb87275e1173e17848fc` 的 A2_RUNBOOK
  blob `53b90d2f503e6772ee244ee60003f00627639177`：NAS 先决证据、真实文件系统和范围保持一致。
- 同提交 A1 installed walkthrough blob `21ed898c857863f4b897acc92c11a41880750173`：
  使用 TemporaryDirectory；四资源专项的调用与自清理也按固定 GitHub blobs 核对。
- 读取当前 Python 标准库 tempfile 的目录选择实现，确认存在后备目录；未运行故障注入或改写上游。
- 复核 OpenAI 官方鉴权和 MCP server 文档，确认验签、工具内容与宿主边界；
  [鉴权依据](https://developers.openai.com/plugins/build/auth)、[工具返回依据](https://developers.openai.com/plugins/build/mcp-server)。
- S1 三层文档、运行源码、测试、依赖和配置保持原字节；不把新 job 混入 Task v1。

## 本轮实际验证

执行于隔离云端工作树，源码输入精确为 `22563ab947a928060e8e3092ef7c8510f1db25b1`。
Python `3.12.14`；以下命令路径仅以通用占位表示，实际缓存位于仓库外。

| 检查 | 实际命令／结果 | 可证明范围 |
| --- | --- | --- |
| Python 编译 | `python -X pycache_prefix=<isolated-cache> -m compileall -q tools tests setup.py`；52 个既有 Python 文件，退出 0 | 当前已有源码可编译；不是新 job/MCP/Plugin 实现验证 |
| Linux shell 语法 | `bash -n tools/local_hand/bootstrap_linux.sh`；退出 0 | 仅语法，不运行 bootstrap，不改变服务 |
| 输出保存 | 两命令各 stdout/stderr 分别保存，四份均为空 | 每份 SHA-256 均为 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 文档与来源 | 9 份变更 Markdown 的 56 个相对链接、12 项需求/9 个架构节/12 项验收映射、差异空白与披露模式均无错误；64 个非 Markdown 文件及 S1 三文档原字节不变 | 文档结构与修订范围；不代替实现测试 |

编译后工作树保持 clean，之后才编辑文档。未编写新测试或运行新功能；没有用历史全量测试数充当本轮结果。
工具源码、原始异常、修订前失败假设与已知 E4/E5/E6 阻塞分别记账，不宣称真实客户端或 GX10 已通过。

## 准确基线与后续

本次语义修订 supersede 原拟议 A；新的文档提交完整 SHA 由随后独立登记提交写入 AGENTS，
仍为 OPEN。两个新 scope 均未关闭；首批建议仍仅 `LH-A2-EXEC-MCP-v1` E1–E3。
E4 实际宿主桥接/认证、E5 管理入口/双协议切换、E6 挂载保护及真实 NAS 故障项继续各自满足门槛。
本轮没有安装软件、部署 Plugin/MCP、投递 GX10 作业、改变 NAS 或切换服务。
