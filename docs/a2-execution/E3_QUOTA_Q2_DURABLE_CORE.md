# Q2 第二批：固定准入、永久计费和 bootstrap 消费

这是既有 `LH-E3-QUOTA-HARNESS-v1` CLOSED 隔离实现范围内的接口细化，
不改变批准 A、旧 Q1 记录或生产资格。本批不安装服务，也不宣称真实 socket、
跨 user namespace peer、systemd 或 quota 验收完成。

## 固定接口

`local-hand-quota-grant/v1` 是管理侧预先保护的有限声明，不是客户端输入。
它绑定完整 wire 请求（观察 grant 摘要由规范字节计算）、原 bootstrap allocation、
原 phase budget、三或四个根、endpoint、query/management parent 身份、前序 request IDs，
以及 admission/query/collector 各自 CPU、RSS、pids、输出、运行时间和存储额度。
等待、接收和停止都在原 phase 截止时间内。数据解码不证明这些 OS 限制已生效。

容量声明固定所有新旧 FS UUID/project 域，按唯一域计费；另列保留原件/封存峰值、
管理存储、inode 和管理进程上限。每份 grant 的管理额度随启动意图永久消费，
成功、失败、取消和重启都不退款。声明必须来自事前管理准入，不能用当前空闲空间补造。

## 持久化与服务核心

最多 32 份 grant。预配置在独立、受保护、有限容量的目录内创建固定 lock、
policy 和每请求 cell；外部固定目录和每个文件的 dev/inode。运行时只打开这些原对象，
不创建缺失文件、不迁移 Q1、不建立空账本。每个 cell 为至多四条有界追加记录：
INTENT、INVOCATION、RESULT、CLOSED。每条记录以摘要链接前缀，并保存自身摘要；
缺文件、残缺行、额外记录、身份变化或错误摘要关闭准入。
管理员不得回滚已 fsync 的原对象；此模型不声称抵抗恶意管理员或谎报持久性的存储。

所有 cell 在非阻塞跨进程锁下核验；先追加并 fsync INTENT，再允许唯一派发回调。
未收到返回、崩溃、结果缺失或过期都保留原意图。重复请求只读取原记录。
同 ID 异绑定、同 phase 第二份请求、换 generation 或 foreign operation 重用资源均拒绝。
前序 RESULT 不能独自批准下一阶段；还须持久保存受信 broker 提供的完整退出围栏，
覆盖原 query、bootstrap/helper/reader 和采集器。围栏缺失即继续占用。
每个阶段的退出声明绑定完整 unit/InvocationID/cgroup/parent；query 和 bootstrap
还必须匹配原记录的 InvocationID。helper/reader/collector 的真实 InvocationID 来源仍须
由受信运行适配器独立核验，不能由 wire 客户端提供。

服务核心只接受受信 socket/manager 适配器产生的 peer 及监督事实，验证准确 bootstrap
unit、InvocationID、cgroup、PID 启动身份与 parent。普通 peer 的 JSON 不能构造这些输入。
本批提供固定接口及一致性校验；独立 OS 事实取得、listener/worker 装配仍是后续接线。
磁盘打开/read/write/fsync 及派发回调只能在单个已有独立监督的管理 worker 内调用，
不能放进 listener 或 broker 控制线程。一个未结束的 worker 阻止替代工作。

## bootstrap 接线与兼容

新的内部 bootstrap 信封为显式 `version: 2`，准确字段为 version/execution/allocation/observation。
旧无版本信封保持原语义；不为旧 v2/v3 监督记录补字段，也不自动选择新路径。
新路径核对原预算、allocation、完整执行 ID 和观察声明摘要；持有根 FD，
查询前后核对 dev/inode/uid/gid/mode、FS 类型、project/继承，再消费有界客户端回执。
查询 unit 必须位于声明的准确 parent；任何失败都阻止首个 marker/plan 写入，且不回退普通 quota 查询。
原三单元 CPU 分额不变，管理成本使用独立且全局记账的 grant。

## 本批验证范围

真实临时文件/fsync/flock/进程退出用于证明持久防重；OS quota、manager、peer 事实使用
明确标注的逻辑 fixture。覆盖意图前后中断、并发、丢失 ACK、重启、损坏/删除、未知阻断、
永久预算耗尽、同 UID 错角色、跨阶段继承、回执/本地根不符和旧 bootstrap 回归。
实际 IPC 在当前执行器不可用的既有结果保留，不再请求提权或绕过限制。

## 当前接线边界

`quota_bootstrap.bind_payload` 是供受信 broker 适配器调用的纯信封绑定接口，
`bootstrap.prepare` 已实现该信封的消费。现有生产 broker/runner 尚不选用这个新信封。
本批服务核心的 `dispatch`、`peer/expected_peer` 和关闭围栏是受信内部接口；
尚无认证 listener、受保护配置装载、原多根 native 查询与 manager 的完整适配器，
也未将 Q2 观察引用与 broker 持久事件原子关联。代码不会把这些缺口当作既有授权。
下一批先接这些入口和隔离属性、固定完整候选，再交付一次组合实机验证。
