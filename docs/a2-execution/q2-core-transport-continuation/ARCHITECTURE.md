# 保留失败来源与分阶段输入装配

**PROPOSED / Gate OPEN / NOT APPROVED**，`LH-Q2-CORE-TRANSPORT-CONTINUATION-v1`。
依[需求](REQUIREMENTS.md)，复用现有组件；不新增 helper 或改变 custodian 协议。

## 四原件失败的来源模型

旧十一代五文件 profile 和 old09c 九成员归档原样保留。old10a 不经过强制读取 receipt 的
`_build_previous_generation`，不伪造 receipt 或成功报告。另设固定失败类型：
`previous_transport_failure` 表达准确 old10a session/D/authority、CONSUMED_FAILED、一次
SSH、四份维护原件、receipt 缺失、remote_exit UNKNOWN、无 coordinator completion、
核心未构建/NOT_RUN、无成本退款。不得把本地异常解释为 guest 未运行。

新私有 USTAR 归档包含十五个原始成员：四份维护原件、八份已保留本地返回、原 immutable
freeze、原失败记录、原 terminal gate。全部保持原字节；不执行其中引用的旧脚本。
归档≤196608 B，每成员≤65536 B，无压缩、链接、路径穿越、重复/额外成员、非零尾数据；
验证成员大小、摘要与固定集合，再验证完整语义关系。实际保留字节形状为 153600 B，
这是只读装配结果，不代表新运行时解析器已实现。

新候选的私有输入声明独立固定归档、十五成员索引、旧 freeze 和五 caller 摘要；由保留
原件交叉核验产生，并受新不可变 freeze 绑定。不能让归档用内部自报哈希为自身作证。
新 `transport_failure_source` 携带有界来源投影，进入完整 source binding、manifest
摘要、transition 和 approved-input。完整原始归档由生产端与私有独立验收器分别读取。
portable consumer 和独立 dispatcher 同义验证固定失败事实、集合、私有固定输入绑定
与全链摘要，拒绝缺失来源、假 receipt、错 D、错误计数和自报成功。

原件关系检查至少包括：旧 R/A/C/D、固定原 freeze 摘要、五 caller 摘要；terminal gate
仅按真实失败替换 freeze 的 state/uc2/uc3；失败记录与四原件及八本地返回的逐件索引；
preflight manifest 与实际 marker 完全一致；nonce、clocks、摘要和四条事件顺序一致；
execute 原始异常、caller 原始输出和 summary 中 diagnostic 完整一致。保留最后有效
样本的原意，不把它当失败样本。receipt 缺失依据已有缺失记录，不增加现场存在性查询。

## 一个新增 FD 的顺序

维护先按现有顺序固定输入、原目录/VM/工具和 old09c，建立原 Maintenance/nonce；此时
不打开 old10a 新归档。执行原 55 件 custodian 的 READY、身份/用量核验及父 FD 交接，
然后通过现有 protected Inputs.read 打开新归档，完成解析和 source-binding 更新，
再进入 preflight。交接失败不会打开新输入，也不会开始控制命令或创建 marker。

新归档 FD 持续由父持有到原 teardown。所有 bindings 检查复查已持有 FD/name/bytes；
没有先读后关闭再重开的绕行路径。custodian 仍只继承同一 55 份 open-file descriptions，
固定 count、协议、权限、IPC、CPU/RSS、存活身份与未知拒绝完全不变。

| 阶段 | 新方案静态上界 | 原限额 |
| --- | ---: | ---: |
| 交接前持有数 | 122 | 128 |
| 原交接与临时读保守峰值 | 128 | 128 |
| 交接后增加新归档及原 20 FD 余量 | 90 | 128 |
| custodian | 64 | 128 |
| 核心准备（原 125 加新归档） | 126 | 128 |

新输入 protected open 的临时目录 FD 在交接后低占用阶段；不会与 128 交接峰值重叠。
这些是源码推导，须在 TC1 按实际输入数验证完整启动、交接、pre/post 管道、输出保存、
失败退出和正常 teardown。现有 121/122 测试通过不能冒充新路径证明。

## 版本、独立消费者与条件核心

维护使用新 TC A/C/D 和 session10b。完整 resume 保留十一代五件维护和 old09c，再增加
独立的 old10a 失败事实；不得以不带 receipt 为由丢弃第十二代已消费维护。
manifest/receipt→v15、preflight→v14、transition→v14、reconciliation 与
historical-capacity-obligations→v18、host-capacity-condition→v17。guest input/report
仍 v4，仅准确更新 session/来源；guest 动作和保护不变。旧版本事实使用原解析规则。
短 preflight 继续只引用完整 resume 摘要，manifest 继续使用无损单份历史引用。

维护 producer、prior/approved-input、独立 dispatcher、contract、entry/freeze 和私有
调用器同步更新版本、来源、十四份成本和发行绑定。验收使用完整成功原件集合、原8项
JOURNAL_FILES以及真实顶层 completion、custodian 正常退出和最终聚合用量；不以一份
receipt、子进程返回0或 CI 通过替代维护成功。通过后才生成原07a包并接 H01→Q4→H11。

所有新增诊断沿既有异常→原始返回→summary→caller 路径保留，不补读进程或另建诊断。
源码体积若需要调整，仅在现有来源模块间等价整理，并同步准确源码集合/摘要。
host/guest≤98304 B，custodian≤16384 B，marker/receipt/描述/transition≤65536 B，
压缩/展开 bundle≤49152/393216 B，argv≤65536 B，短 preflight≤4096 B，
approved-input≤1048576 B，核心包≤33550320 B；任何静态超界都先停，不扩大这些上限。
