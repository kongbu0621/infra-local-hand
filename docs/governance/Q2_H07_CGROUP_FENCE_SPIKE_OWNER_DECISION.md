# H07 cgroup 监督原语实验：Owner 决定

- Decision Authority / Owner：当前项目 Owner（本工作会话用户）。
- 决定时间：2026-09-29 19:01:33 +08:00（本条消息的会话时间上下文）。
- 本地归档事件：`LH-Q2-H07-CGROUP-FENCE-SPIKE-CLOSURE-20260929-01`；不是平台消息 ID。
- 稳定来源：本文件保留准确 Owner 回复及紧邻确认请求，供 Owner 核实。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Documentation A：`71c7e842c724650a0e949a63bb898699b41107be`。
- Scope：`LH-Q2-H07-CGROUP-FENCE-SPIKE-v1`，准确 A 的 F1–F4。
- 三文档及摘要：[准确基线登记](Q2_H07_CGROUP_FENCE_SPIKE_BASELINE.md)。

## 准确 Owner 回复 B

> 按原 R，批准 A 71c7e842 的 H07 cgroup 监督原语实验，关闭 F1–F4 范围 Gate；允许通过 GitHub 页面手动触发最多三轮限定 CI 验证，继续实施。

## 紧邻确认请求中的准确决定语句

> 按原 R，批准 A 71c7e842 的 H07 cgroup 监督原语实验，关闭 F1–F4 范围 Gate；允许通过 GitHub 页面手动触发最多三轮限定 CI 验证，继续实施。

确认请求已说明独立 GitHub 临时 Linux 环境、六个固定病例、最多三轮有明确源码
修复理由的 CI 验证，以及新执行机制须按原 R 精确关闭。Owner 准确回复关闭
这一独立实验范围，明确允许 executor 通过 GitHub 页面手动触发。

## 独立关闭与实施范围

F1–F4：固定 C helper、严格协议及生命周期、有界隔离验证、六病例真实实验、
独立 manual-only workflow 和可追溯结果。仅 ubuntu-24.04 x64 GitHub 托管临时
runner，最多三轮（首轮及最多两轮有明确源码修复理由的验证），每轮六例各一次，
job≤15min，总 job 执行额度≤45min。无自动重试；成功 dispatch 计入额度。
范围内修复与剩余额度内复验无需逐次确认；停止条件和范围变化规则按准确 A。

本记录与 AGENTS 的 CLOSED 声明构成独立 bookkeeping C；不包含 helper、
测试、workflow 或其他实现。A 三文档原字节及历史 OPEN 标签保持不变；
实现 D 必须以此 C 为祖先。准确 C SHA 由 Git 历史定位，不预写自身 SHA。

R 可读原件/完整性、Owner mandate/authority、无例外及变更规则均保持。
原 PRO6000/guest、原 Q2 唯一批次、生产后端及冻结 runtime 不在实验动作范围内；
实验即使通过，也不能证明原链 H07、FS、完整账单或生产资格。
