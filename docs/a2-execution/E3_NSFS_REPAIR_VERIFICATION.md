# E3 只读探针 nsfs 修复验证

后续更新（2026-09-23）：两份原始 GX10 ZIP 已收到并完成独立核验，固定源码的现场 nsfs 修复结果通过；详见 [GX10 原始证据核验](GX10_E3_NSFS_RETEST_VERIFICATION.md)。以下保留云端修复交付时的结果和证据边界，文中的“尚未取得”是当时状态。整体 E3 验收仍未完成。

日期：2026-09-23。结论：**已修复合法 nsfs 挂载记录的解析误判，准确 main CI 通过；目标宿主修复后重测尚未取得，E3 实机验收仍未完成。**

本轮起因是目标宿主只读盘点截图报告 `MOUNTINFO_FORMAT`。用户随后提供了原始证据 ZIP 的摘要、大小和成员数，但尚未提供 ZIP 文件本身。截图和预期摘要不构成独立完整性验证；以下回归使用合成内核格式记录，不冒充原始宿主 mountinfo 重放。

## 根因与修复范围

旧探针对所有文件系统的 mountinfo root 都要求绝对路径。固定 [Linux nsfs 源码](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/fs/nsfs.c) 中，`nsfs_show_path` 输出命名空间类型与 inode 组成的标识，例如 `net:[4026531840]`；该 root 不是绝对目录。
来源 Git blob 为 `c675fc40ce2dc674f0dafce5c4924b910a73a23f`，文件 SHA-256 为 `00352d816aada15622fae9da72b7c749abc26539534cbe649ef4f4a172784080`。这证明该格式的合法来源，不认证目标内核版本或回移补丁。

`tools/probe_e3_host.py` 现在仅对 `nsfs` 接受有界的命名空间 root 标识，保留该挂载记录；其他文件系统 root 和全部 mount point 继续使用原严格路径校验。没有通过丢弃 nsfs 行掩盖问题：nsfs 覆盖请求的 cgroup 时仍不能报告为 cgroup2，同点歧义仍为未知。既有绝对路径形式仍兼容，报告字段类型不变。

本轮没有修改产品四包、Plugin、依赖、生产支持判定或三个固定 false 字段。`E3_SUPERVISION_UNVERIFIED` 保留；没有执行目标宿主、quota syscall、真实 NAS、服务切换或真实监督 harness。

## 准确来源

| 项目 | 身份 |
| --- | --- |
| 已推送 main 的修复源码 | `88b78b6ef908026b763f307c4d78ab3d0c0e6521` |
| Tree | `be5e00c2e7b768b61cf34aa19b70d1cd1452e667` |
| Parent | `475cfcbd79c2f8eb151bb4f0b385dbcc22ad3179` |
| 探针大小 | 31,209 bytes |
| 探针 SHA-256 | `29ba728639a4674b53799f805abfe31e075f6260ce68f64e2410370210eae651` |
| 探针 Git blob | `a01f5354dfb6e160b8dc42acc1dbffc1697144f7` |

R 仍为 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，本轮已直接读取固定规则并核对既有完整性摘要。三份权威文档逐字节匹配已批准 A `79f73faedcd9cde4164b0d1625782dae27db6c2f`；实现仍为独立 CLOSED 记录 C `367632126c1930983a06b1854f63789448633148` 的后裔。E1–E3 原范围未扩大，E4、E5/S2、E6 未关闭。

## 验证结果

| 验证 | 实际结果 |
| --- | --- |
| 旧源码上的四项新增回归 | **4 failed、18 deselected，0.26 s，exit 1**；原失败双流和命令已保留 |
| 修复后工作区探针测试 | **22 passed、0 skipped，1.00 s** |
| 干净准确源码探针测试 | **22 passed、0 skipped，1.13 s**，启用 `-W error` |
| 仓库外独立执行 | Python 3.12.14，从 `/tmp` 以 `-I -B` 执行固定脚本；exit 0、stderr 0 bytes、JSON 3,163 bytes、来源摘要吻合；云端结果 **BLOCKED** |
| 兼容性检查 | 编译与 Python 3.9 grammar 解析通过；未运行真实 3.9 或目标 aarch64 解释器 |
| Linux CI 源码 | **887 passed、1 skipped，347.34 s** |
| Linux CI 独立安装 | **94 checks、292 commands，PASS** |
| Windows CI S1 源码 | **211 passed、158 skipped，358.20 s** |
| Windows CI 独立安装 | **10 checks、10 commands，PASS** |

新增回归验证合法 nsfs 与其他挂载共存、错误文件系统和格式拒绝、挂载覆盖与歧义保留，以及缺少私有输入时仍保持 INCOMPLETE 和三个 false。云端观察不是目标宿主重测。

准确 [push/main CI run 35857781291](https://github.com/kongbu0621/infra-local-hand/actions/runs/35857781291)，attempt 1，head 为上述 `88b78b6`，整体 SUCCESS。
Linux / Windows job 分别为 `107170387587` / `107170387577`，classify job 为 `107170339344`，均 SUCCESS。证据包含 run/jobs 元数据、完整解码日志及产物元数据；产物摘要来自 GitHub API，未另行下载 CI 二进制产物作独立字节复验。本报告的后续文档提交不冒充该源码 CI 的 head。

## 私有证据与后续

本轮私有修复证据包 `infra-local-hand-e3-nsfs-88b78b6-evidence-20260923.zip`：

- 64,666 bytes，30 members（含 MANIFEST）；ZIP CRC、唯一成员名、逐成员大小与 SHA-256 均通过核验。
- ZIP SHA-256：`09dfe15ecc6b537e28f8145c802d26ce396cd96845f059fa84fff6b35332f23f`。
- MANIFEST SHA-256：`ebfc9a65f623988932201e27cda7eb3080af7aaaacb893b9dbce9cd2bbdfdf6f`。

该包是云端修复材料，不是用户原始宿主包。包内 `GX10_RETEST_HANDOFF.md` 固定本轮提交、脚本大小和摘要，要求导出成功且大小／摘要匹配后才能执行；空文件或部分输出不得执行，失败材料独立保留。

下一步取得原始 ZIP 做独立核验，并在目标宿主按交接任务重跑只读盘点，分别保留两次证据。expected UID、私有 slice/cgroup 和 mount target 未确认时继续记缺项，不以猜测值补齐。修复后即使格式误报消除，也不代表 E3 PASS。
本地 quota 查询机制、真实三 unit harness 和现场准入仍按 [实现缺口](E3_IMPLEMENTATION_GAPS.md)及 [宿主验收准备](E3_HOST_ACCEPTANCE_RUNBOOK.md)推进。
