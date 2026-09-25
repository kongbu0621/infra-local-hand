# Q2 持久服务核心与 bootstrap 消费：第二批验证

日期：2026-09-25。**107 项定向测试通过。固定准入、防重、管理预算和 bootstrap 新版回执消费已实现；
Q2 的 listener、受监督运行适配及 broker 持久接线未完成，Q3/Q4 未完成，生产
`E3_SUPERVISION_UNVERIFIED` 保留。** 本轮没有连接 guest、运行真实 quota/systemd 实验或启动业务作业。

准确源码提交：`4c550483a92eb5d13c9bd3d7ef42319fabebcace`；源码 tree：
`736ad69811bd293c97acbe7feb995c66922e1399`。该源码提交完成且工作树干净后运行本报告的最终测试。
后续仅记录证据和更新进度；远端提交身份与同树核对记录见
[发布映射](E3_QUOTA_Q2_DURABLE_PUBLICATION.md)。

本批继承 `LH-E3-QUOTA-HARNESS-v1` 的隔离开发批准：R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、A
`415327ebdcc251bb055da9931a7a88990f750b7a`、独立 C
`5a4ea852091db06549a876e42bbd5f95d5869d3b`。不修改三份权威文档，不获得生产部署或 GX10 切换资格。

## 已实现范围

| 组件 | 新增行为 |
| --- | --- |
| `quota_grant.py` | 严格固定请求、原 root/budget 分配、endpoint、query/management 父树及有限容量声明；管理存储、CPU、内存、进程和输出预算永久记账，不因完成或 UNKNOWN 退还 |
| `q2_journal.py` | 最多 32 个预置固定 cell；目录和文件 inode 固定；先 fsync 意图再允许派发；有界哈希链、原 InvocationID/回执和完整阶段关闭记录；丢失、替换、撕裂或写入不确定时拒绝继续 |
| `q2_service.py` | 精确固定准入和 peer 绑定；同请求不重投；派发前后都受原截止时间约束；有未关闭工作时阻断后续阶段；原 preflight/business/evidence 分配关系与退出围栏完整匹配 |
| `quota_bootstrap.py` / `bootstrap.py` | 显式内部信封 v2；在首次 marker/plan 写入前消费回执并复核持有根 FD 的身份、project 和继承；UNKNOWN、过期或根变化均拒绝；旧信封维持原语义，不隐式升级 |

详细实现与受信假设见[持久核心设计](E3_QUOTA_Q2_DURABLE_CORE.md)。管理容量与阶段资源字段是
受保护声明的验证和扣账，当前尚不是实际 systemd/cgroup 资源限制执行证明。服务核心只能放进有限的
受监督管理 worker；同步持久化或派发回调不能放进 listener 或控制线程。

## 准确验证

Python 3.12.14，Linux 6.18.44。最终运行区间：
`2026-09-25T08:29:07.380523+00:00` 至 `2026-09-25T08:29:08.906908+00:00`。
**107 tests / 0 failures / 0 errors / 0 skipped / exit 0**。

```sh
PYTHONPATH=tools:tests python -B -W error -m unittest -v \
  test_local_hand_jobs_quota_grant \
  test_e3_quota_q2_service \
  test_local_hand_jobs_quota_bootstrap \
  test_local_hand_jobs_quota_contract \
  test_local_hand_jobs_bootstrap_preparation \
  test_local_hand_jobs_budget \
  test_local_hand_jobs_bootstrap \
  test_local_hand_jobs_bootstrap_roots
```

实际采集以同一解释器加载以上同组 unittest suite，并保存 TextTestRunner 原始输出；上面是等价 CLI。
原始结果见 [targeted.log](validation/q2-durable-core-20260925/targeted.log)，命令及分类见
[targeted-command.json](validation/q2-durable-core-20260925/targeted-command.json)。日志 SHA256：
`df9f470cde80fafddfd0ee843740bad50a6b5e220f69d47aefd7a4296913d21d`。

| 验证层 | 实际覆盖与边界 |
| --- | --- |
| 固定合同和管理预算 | 逻辑声明；覆盖原分配绑定、容量不足、永久扣账、跨阶段资源漂移和 evidence 第四根 |
| 持久账本/服务核心 | 真实临时文件、fsync、flock、跨进程锁及子进程在意图后退出；覆盖丢回包后去重、重启、UNKNOWN、文件替换/缺失、哈希链损坏、截止时间在 fsync 中耗尽和未关闭阶段拒绝；peer、manager、时钟和 quota 结果为模拟 |
| bootstrap 消费 | 真实临时目录、inode/device/mode、marker/plan 写入及前后根身份检查；UID、namespace、ioctl、IPC 为明确模型；检查首次写入前拒绝及原 CPU 分额不变 |
| 既有功能回归 | 原 wire 合同、旧 bootstrap 准备、budget 和 bootstrap_roots 定向回归；不是产品全量测试 |
| 真实 AF_UNIX、SO_PEERCRED 与 FD 传递 | 本批 NOT_RUN；第一批执行器 EPERM 和权限拒绝仍保留，不能以模型替代 |
| 真实 quota/systemd、Windows、独立 wheel 安装 | 本批 NOT_RUN |

### 保留的中间失败

以下为当时工具观察的摘要，不伪装成保存了原始完整日志：

1. 初次使用 pytest 时环境没有 pytest，退出 1，未收集测试；改用已有 stdlib unittest，未安装依赖。
2. 初次 bootstrap 定向组 17 项中，旧 8 项通过，新 9 项在测试 fixture 的 `os.chown` 中报
   `OSError: [Errno 22] Invalid argument`。修正为明确 UID 模型后通过；生产 UID 检查没有放宽。
3. 源码提交后尝试以伪造 `sys.platform='win32'` 模拟收集，Linux stdlib 先导入缺失的 `_winapi`，
   在目标测试收集前退出 1。该模拟无效，未继续规避，也不计入 107 项或 Windows 验证。

## 下一批确定范围

1. 受保护固定配置加载和实际 peer 身份取证；有界 listener 将工作交给独立受监督管理 worker。
2. 接上完整 3–4 根的固定 native 查询与 manager 适配，兑现已声明的管理资源限制和各阶段退出证明。
3. broker 原执行/事件与观察 grant、回执引用持久绑定，明确选择新版 bootstrap 信封；完成
   bootstrap 专属 socket 可见性及 helper/reader 无连接资格的隔离配置。
4. 形成固定源码候选及一次组合实机验证交接，验证真实 IPC、管理监督、根事实和完整退出。

`bind_payload` 当前只是纯绑定 API，`bootstrap.prepare` 已能消费新版，但生产 broker/runner 尚未选择它。
受信适配器提供的 peer、InvocationID 和退出事实不能由普通请求自证。原 Q1 单槽查询不能直接冒充 Q2
多根运行器。旧 slot-001 UNKNOWN、slot-002 INCOMPLETE 和所有保留记录均不重放或升级结论。
