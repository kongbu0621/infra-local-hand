# Q2 固定内核事实读取：待审基线

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Scope：`LH-Q2-KERNEL-FACT-READ-v1`。
- 状态：**PROPOSED / OPEN / AWAITING OWNER**；无本范围 B/C/D。
- Documentation baseline A：`887b640b394f9983f37dfe97c58ba35aaa099359`。
- A tree：`e9fb422e99f42a76554a3bc5d646482fead349be`。
- 三文档目录：[q2-kernel-fact-read](../a2-execution/q2-kernel-fact-read/REQUIREMENTS.md)。

| 文档 | bytes | SHA-256 |
| --- | ---: | --- |
| `REQUIREMENTS.md` | 4231 | `8fff20a7a6c9b08a427ff6768b567d4a38cd0441e4a54ceaf8b3786c6abb1268` |
| `ARCHITECTURE.md` | 5261 | `c18ef78c8fa22994d0270ce8e731d5a690c1f38fa5d2ba9fdb23491127572954` |
| `IMPLEMENTATION_PLAN.md` | 3357 | `810c0f2d274b18536249076e0de8278b012b00d5f23fb6ea0ed6d569f65d61f8` |

本次仅请求固定 boot 与自身 mountinfo 两项经 fd/procfs/挂载身份资格核验后的普通
只读例外，含明确的原 host namespace 环境假设和内核视图元数据披露。其它证据
仍使用 O_NOATIME，原普通身份、boot pin、双钟/预算、无消费/远端分支保持。
不授权新监督设施、完整批次执行、提权或改系统配置。

现场截图及边界见[现场复核](../a2-execution/Q2_LOCAL_PREFLIGHT_FIELD_REVIEW.md)。
独立文档复核指出的 STATX_MNT_ID 返回 mask 和 proc/PID namespace 假设已写入
本 A；文档链接有效，旧 host A 三份字节未变。本次只有文档与登记，无新代码、
测试源、探针或现场命令；不重复执行旧测试，也不把历史 287 PASS 作为新方案验证。

Owner 如决定实施，可明确回复：

> 按原 R，批准 A 887b640b 的固定内核事实读取方案（LH-Q2-KERNEL-FACT-READ-v1），关闭该范围 Gate，继续实施。

上句是待决定文本，**不是已经发生的 Owner B**。必须先保留准确 B，再独立提交
只含关闭登记的 C，随后才实施 D。旧 A/批准链及未受影响 CLOSED 工作保留。
