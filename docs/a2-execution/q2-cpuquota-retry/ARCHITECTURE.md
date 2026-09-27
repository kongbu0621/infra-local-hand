# Q2 单次新运行：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN**；scope：`LH-Q2-CPUQUOTA-RETRY-v1`。
- [需求](REQUIREMENTS.md)定义一次替代实验的范围，旧恢复合同与材料保留。

## 职责和信任边界

| 组件 | 职责 | 不可推导的事实 |
| --- | --- | --- |
| 原管理通道的批次所有者 | 在任何探测前固定外层 300 秒，持有原 client 与双流；保存新的 create-only 意图 | SSH 退出不等于各子服务已停止 |
| 只读鉴证器 | 绑定准确旧失败、当前静止性、未消费账本及七根身份 | 当前目录空不能抹去旧发行或替代历史捕获 |
| 容量与安装器 | 对旧存量和保留承诺累计计费，安装需求固定候选至独立路径 | 新 epoch/ID 不产生旧容量退款 |
| 新装配器 | 新 policy/ledger/authority 和唯一运行身份，关联原准备及失败 | 新映射不等于 quota 根重新创建 |
| 既有 owner/supervisor/chain | 同 MainPID 绑定实际身份，执行一次固定三阶段，分别记录退出、EOF、停止和 seal | 子级自报成功不能替代外部原进程证据 |

新编排为显式 test-only 工具，不进入普通 wheel 或 Plugin。运行候选固定在需求所列
commit/tree/wheel；C 后编排工具 D 单独固定文件摘要，职责限于鉴证、独立安装、
装配和交付，不通过 monkeypatch 或动态覆盖改变冻结运行候选。

## 准入和旧失败边界

私有计划固定 guest/boot/初始 namespace、文件系统、工具与原准备/恢复/owner 的
准确身份及摘要、旧安装 candidate、完整保留清单、新运行 candidate、唯一 attempt ID、
新路径/身份、原七根映射及预算。严格拒绝未知字段、任意命令、路径别名和重叠。

首次修改前同时验证：

1. 原 owner 来源与实际 argv 摘要一致，准确无效 CPUQuota 文本对应退出 1、原解析错误、
   空 stdout 和完整双流 EOF/hash；原 reservation/envelope/delivery 均保留。
2. 原服务前后观察是 not-found、无 InvocationID/MainPID/ControlPID/Job；绑定入口、
   fixture-check、supervisor/controller 输出和 grant 消费材料未产生。单一缺失文件不够。
3. 当前同 guest/boot 下没有旧命名 unit/job 或相关工作；此项只证明现在静止，不能补写历史 deadline。
4. 原普通 SQLite 使用只读、无创建/恢复副作用的方式打开；文件/metadata/ledger_id/generation
   符合原初始化回执，operations/events/leases 均空，没有 WAL/SHM/journal。遇损坏或未知表/状态拒绝。
5. 七根逐项 dev/inode、owner/mode、文件系统/project、继承、实际硬限额和成员与准备回执相符，
   没有 payload/消费；不得仅凭 empty 或无 operation 就认定可以复用。
6. 原账户、组、manager 和专用 slice 配置摘要及限制保持；原 Q1/准备/恢复/安装/账本/证据字节保持，
   新旧费用可同时容纳。采样期间变化则停止。

不可把未发行证明套到旧 owner：它已经发行。通过上述条件只意味着可在**新的明确授权**下，
把未消费的物理根映射给一个新的操作。新记录保存 `supersedes_failed_attempt` 的逻辑关联，
旧状态不变，不改判或续期。任一条件不明为 BLOCKED/UNKNOWN，无通用恢复分支。

## 对象、状态和并发

独立 create-only 对象包括新 source/runtime/native 安装、authority/policy、broker state/SQLite、
journal、session/control/endpoint、声明、输出和批次 reservation。新 attempt/operation、ledger、
deployment/installation、epoch/session/query/management request、unit 名不得与旧对象相同。
新受保护映射记录同时绑定原准备回执、未消费鉴证、七根实际身份和这唯一新 operation。

状态为 `DECLARED → ATTESTED → RESERVED → INSTALLED → ASSEMBLED → ISSUED → RECORDED`。
每项副作用前记录 intent；一次 reservation 以排他创建决定赢家。失败保持对应完成边界和全部材料，
不回滚、不删后重建、不换 ID、不自动第二次执行。读取保留证据可重复，变更入口不可重复。
并发或旧账户其他工作会破坏静止性，必须在交付前重新验证并拒绝；不能以合作性锁替代真实状态检查。

若准确已有 manager 或专用父 slice 只是正常 inactive，可在本新范围内各做一次有界 start，
不用 restart、不改配置。记录 start intent/结果及新 dev/inode，不假装仍为原 cgroup 身份。
manager 配置不符、failed 状态、未知工作或需创建范围外对象时停止。

## 容量、期限与结果

唯一文件系统/project 的硬限额计费一次；旧日志/安装/源及未释放持久承诺和新费用全部列出。
实际存量与未释放承诺分别核对，不能重复叠加同一费用，也不能以小的实际占用抹去仍须保留的承诺。
新 epoch 不清空历史计费。新 CPU/时间是追加授权，空间总上界不变；旧材料无清理路径。

外层时间在一次只读探测前固定，guest 入口在首次读取前固定其 140 秒阶段期限。
跨宿主与 guest 时钟用一次往返保守绑定，不直接比较两台机器的单调时钟。
启动 owner 前须同时容纳实际剩余的 owner、stop、EOF/fsync/seal 余量；静态 140+120<300
不能代替绝对 deadline 准入。任何预算不足立即停止，不分步重新计时。

记录 transport EOF/退出、guest 服务结果、原 owner/child 身份、独立停止、树空、各级 seal 和
旧字节保持。编码修复的格式版本必须与 argv/hash 对应，旧四位记录仍使用旧版重建。
RECORDED 只说明材料已保留；新 Q2 验收须另满足原 Q2 合同，旧 INCOMPLETE 永不自动转 PASS。

尚未证明的是现场完整三阶段及真实停止链；离线解析和安装不能替代它们。空间和 manager 生命周期
是有界准入检查，不以假设解除；不满足时保留 BLOCKED，不能临时安装依赖或改宿主。
