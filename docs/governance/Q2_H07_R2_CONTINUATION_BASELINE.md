# H07 第二轮限定修复与续验：准确方案基线

2026-09-30 +08。状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。

- Scope：`LH-Q2-H07-R2-CONTINUATION-v1`，仅 V1–V4。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- 直接规则：engineering-sop 固定 R 的 `docs/workflow/program-repository-documentation-gate.md`；SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。强制采用、Owner-only Authority、无例外及变更规则沿用 AGENTS。
- 准确新 A：`eac5e65449e3a4b7083bc91b9123a253e0cb8320`。
- A tree：`080012d7697d43e96818d30f18d2a8c6ac288f8d`。
- A parent：`824f4be40fc02a68fe64df4934966471e146b222`，独立的既有U2测试修复。
- 结果输入：`9a5fb7488dcd6988b6c7d0c5c45cdf87d998dad6`。
- 原 A/C：`71c7e842c724650a0e949a63bb898699b41107be` / `8deeed492edeb7e5fa79cbe95c123a27e69f9f92`。
- 首轮续验 A/C：`a08a5055c35009a896ad6c6059d709758cc78436` / `7d33c698ff6c1bf34733ee2429d0404ace2abd55`。
- 新 Owner B、独立 CLOSED C、新范围实现 D：**均尚无**。

本记录仅固定已存在 A，补准确摘要/事实定位；不是 C，不授权新代码或第三轮派发。旧六份权威文档原字节和两轮原索引不变。

| authoritative document | bytes | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-h07-r2-continuation/REQUIREMENTS.md) | 8476 | `fd45c5f342c249f05958c6f7ef8f80064679623f1c303d0cc127d33716d16159` |
| [架构](../a2-execution/q2-h07-r2-continuation/ARCHITECTURE.md) | 17237 | `da7b6095d5fd1193715349d0c4b85a7777a46f17d6555557cd1593c6787837e6` |
| [实施方案](../a2-execution/q2-h07-r2-continuation/IMPLEMENTATION_PLAN.md) | 8945 | `c161e4aaa0ecbde1016bc43ea943197ffd087ae14d2463c8536dc07efc17b9d9` |

## 精确历史接受对象

仅 run `36662298613` / attempt1 / round2，执行D `9d8328cf742fa130c265de23b1b9085b9e8a0581`，artifact `11074538056`。

- ZIP SHA-256：`21c2c19d081adb1a89d8b9f2ad62297d86761f88947842705554db70e3c66373`。
- 原 report SHA-256：`99d6def38ae46a417a1cfc25b0e6588028813bc0d3b27cee60b083929ad99a54`。
- [脱敏复核索引](../a2-execution/evidence/q2-h07-cgroup-fence-spike/round-2-verification.json) SHA-256：`a1591d1f75e4a5b7bd5cf584abe3ba1b4829669387abf8a17b7689b79b0f1a66`。
- 原报告canonical boot UUID的ASCII字节（不含换行）SHA-256：`c8e2c21edb065608daa4fe6580e8ce548ac276dc933174f270f244699fe22a18`。仅用于与新轮boot作不复用比较，不证明新VM或原VM销毁。

原 report UNKNOWN_RETAINED、原 reason、C1预期未满足和C2–C6 NOT_RUN保留；整份收件器含错误的REJECTED不改成clean REJECTED。第二轮登记对象cleanup=true不补首轮cleanup=false。首轮历史接受保持其原范围。

拟接受该精确第二轮历史异常，在新准确修复、离线/普通CI和准入成立后，不再单独阻断**唯一剩余round3**。全部新增异常仍停止；总额度3，已用2，不重置、不rerun、不增第四轮。

## 准确技术变化与剩余风险

- E全轮固定；PROBE/C1–C6各有四个独立固定名对象，累计创建≤29，最多5个可见/可使用登记目录。内核异步释放不冒充即时回收。
- native v2 / report v3 / continuation v2，补早退/拒绝诊断和首因保留；旧schema原语义和原件不迁移，C3/C6规定缺项保留。
- 本次历史接受采用独立精确分支及脱敏摘要，不为旧clean REJECTED路线伪造报告或公开原机器产物。
- 准确Ubuntu源码包缺修复已经查明；原运行二进制及实际发信来源仍未动态绑定。不安装内核、增加权限或更换fixture来绕开。
- 原六病例、原时间/CPU/内存/输出/文件预算、标准hosted Ubuntu24.04 x64、GitHub页面手动执行保持；当前PRO6000不进入实验。

技术与治理两路静态审查已完成，修正了内核延迟释放计数及C3/C6资格措辞；无未解决方案阻断。既有范围318项定向测试和未修改helper39项自测通过；新生命周期/诊断尚未实现，不能声称已测试。详见[准备复核](../a2-execution/Q2_H07_R2_PREPARATION_REVIEW.md)。

## 待 Owner 决定语句（尚未发生）

> 按原 R，批准 A eac5e654 的 H07 第二轮限定修复与续验方案，关闭 V1–V4 范围 Gate；接受指定第二轮历史 UNKNOWN 仅不阻断最后一轮，保留两轮原失败、原额度与后续停止条件，继续实施。

若Owner作出准确决定，再原样记录B/身份/时间或事件及稳定副本，单独提交C；新D从C下降。确认后范围内不再逐项询问，但第三轮仍须全部准入成立。原Q2 startup仍NOT_ISSUED；不把本spike当成实际H07接线、FS或完整计费验收。
