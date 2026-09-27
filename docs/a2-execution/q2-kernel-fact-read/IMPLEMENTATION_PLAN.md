# Q2 固定内核事实读取：实施方案补充

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope/R 与[需求](REQUIREMENTS.md)一致；[架构](ARCHITECTURE.md)是实现边界。
- 原实现 D `0a456a909821fd1fc6a4fdec43b9e16bc88679f2` 与复核 E
  `19069a8ab62c19355ff8eed6ee65da2c459f3404` 保留；截图不构成新批准。

## 顺序与可交付结果

| 阶段 | 工作 | 对应要求 |
| --- | --- | --- |
| K0 | 提交本三文档和现场复核为准确 A；保留 Owner 对原 R、准确 A/scope 的决定 B；独立 C 只登记 CLOSED | K01–K07 |
| K1 | C 后新增专用 proc 读者，替换 local preflight 的两处内核读取，并记录准确 syscall/errno；不改普通证据 IO | K01–K05 |
| K2 | 验证 ABI、拒绝边界、普通用户实际 proc 读取和既有证据保护；失败不得记 PASS | K02–K06 |
| K3 | 固定 D/tree，重建绑定新旧批准链的精确 RAM 包，保留旧包；校验源码 Git blob/摘要、长度和错误结果 | K06–K07 |
| K4 | 向原 host 交付同一普通身份下的本地预检，取得完整 JSON，准确保留结果后判断下一缺口 | K01–K07 |

本范围全部只是本地预检。完成 K4 不表示 H07、联合账单、消费资格或 Q2 验收通过。
消费/远端/full execution 入口继续保持现有阻断，不把专用读者自动用于这些入口。

## 实现位置与合同

- 新专用模块位于 `tests/e3_host/`；初始只服务现有 `q2_host_window_preflight.py`。
- 对应定向测试位于 `tests/`；不在 OPEN 状态提前创建代码、测试或可执行原型。
- 原报告 schema 保持，增加有界 kernel-read 详情与准确失败信息；只返回
  `OBSERVED_PARTIAL` / `LOCAL_PREFLIGHT_BLOCKED`，不得产生 READY/ADMITTED。
- 包校验链新增本 scope 的准确 A/B/C/D；原三条批准链、私有原件 pin 与原预期
  boot 不改变。交付前验证接收端最早原点仍传到整个观察链，不能重置时限。
- 准确代码、测试、脱敏验证与来源索引入公共仓库；真实路径/boot/原始输出和
 截图保留私有。原历史留存不删除、不改称成功。

## 有意义的验收

验证非 procfs、不同挂载 ID、缺失 statx mask、未知 ABI/符号、symlink/hardlink、
对象/路径/挂载替换、异常权限、超长/截断 boot、错误 boot、超大 mountinfo、
双钟到期、读失败与 fd/终端清理。检查普通证据分支仍带 O_NOATIME，不能用
这个例外读取任意路径；无 marker 创建、外部进程、远端调用或持久结果。

至少一个真实普通身份环境验证该专用接口并记录实际 euid/能力边界；隔离环境
无法执行时明确 SKIP/BLOCKED，不能用 root 测试或 mock 代替这一证据。原 host
只走批准后的受限包；不要求 Owner 为取得正例改权限、换账号或重复失败路径。
完整现场结果可能因保护、固定 boot、原件或后续账单条件阻断，须如实保留。

## 回退与停止

旧包仍在，但不建议用相同权限条件反复运行。新包出错即停止，无自动改标志、
备用路径或执行续跑。需要扩大固定内核对象、支持不同信任/权限边界或放宽预算，
依原 R 更新受影响文档并取得必要决定；不影响已关闭且边界清楚的其它范围。
