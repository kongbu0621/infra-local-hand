# Q2 系统管理器启动修复：待确认基线

- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- 规则来源及 SHA-256：继承根 `AGENTS.md` 的直接固定来源，当前已读且完整性匹配。
- Documentation A：`ae50aea2639c32021794ecb70730f4b9e781c8d6`。
- Scope：`LH-Q2-SYSTEM-MANAGER-REPAIR-v1`，M1–M4。
- Gate：**OPEN**。Owner 尚未针对这个准确 A 作出关闭决定。
- 当前 source implementation：仍为 `7780364c23497e989cd320f157cb4f512a798028`。

| A 中的文件 | SHA-256 |
|---|---|
| `docs/a2-execution/q2-system-manager-repair/REQUIREMENTS.md` | `b5d88001f0827a1bf84ce043aafb89825f22e2cbd16bbc8324faf5ffea472c37` |
| `docs/a2-execution/q2-system-manager-repair/ARCHITECTURE.md` | `c749c61c8869276db9f284fdbcd2498fcdde6f618471f3edf7cc61d42627009f` |
| `docs/a2-execution/q2-system-manager-repair/IMPLEMENTATION_PLAN.md` | `ac1949d4f89a36f8b584f3aeec0ecb9860ed9d59d412e5621ef613bda404a20b` |

上表应以 A 的实际字节核验；此登记不修改三份文档、不属于 CLOSED C。
授权待决点是普通三阶段从 user manager 切换到受限系统 manager 入口，
包含新增受信启动责任、准确 manager/handle/父级版本、有限新对象及一个正常链批次。
全局 AppArmor、业务权限、原隔离校验和旧现场均保持。

独立审阅核对了旧普通生产者的同 UID 风险、管理端前驱授权、完整父树关闭、
嵌套父域与固定预算、新 payload 来源及旧版本兼容。文档链接与空白检查通过。
这些是方案审阅结果，不是源码测试或真实系统验证；未新增程序、配置、测试源码，
未消费现场调用，未生成声称已修复的执行 ZIP。

若 Owner 批准，准确决定须保留并登记为独立 CLOSED C，然后实施 M1–M4。
整批包含修复、验证、提交、单次交付及原结果审查，不再逐项索取相同范围批准。
既有其它 CLOSED 范围、历史失败、UNKNOWN 和 lease 不受此 OPEN 登记改写。
