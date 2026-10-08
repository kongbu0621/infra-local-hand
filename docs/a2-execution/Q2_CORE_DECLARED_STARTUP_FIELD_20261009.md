# DS1 冻结与唯一 DS2 返回

准确 A：`2b13dd653ca19eaaf46a18e6ffc3f447b62eee59`。
[Owner B](../governance/Q2_CORE_DECLARED_STARTUP_CONTINUATION_OWNER_DECISION.md) 对应独立 C
`a2a6d62de08b2d1d8fbf9da97e8ccf938e3777c1`；准确实现 D
`db6e7165322da3072ca1fd88a36401e18ebd4a86` 直接承接 C，tree
`d5e9f6a3a5d9bcbb05a5531e6696143bbba3b8b3`。三文档字节不变。
[实现记录](Q2_CORE_DECLARED_STARTUP_IMPLEMENTATION_REVIEW_20261009.md) 和
[获批旧08e最小索引](Q2_CORE_Q1_BINDING_ORIGINALS_INDEX_20261009.md) 已随 D 发布。

## DS1 完成

准确 D 的首次 [CI 37813524321](https://github.com/kongbu0621/infra-local-hand/actions/runs/37813524321)
三个作业均成功，未重跑。Linux 7161通过、89跳过；Windows 1809通过、1355跳过。
两平台准确 checkout、源码检查及独立 wheel 验收均成功。跳过不计为通过。
本地从准确 D 独立检出、构建和新 venv 安装，94项检查、292条命令通过；现场安装未变。

真实保留来源和八旧维护历史均经原保护 reader 验证。准确 D 的静态 marker 在20位
时钟下为64582 B，原上限65536 B；descriptor26393 B、压缩/展开 bundle38929/132828 B。
最大计量及20位时钟的短预检708 B；合成成功 transition13705 B、approved-input390276 B，
均经 host/独立消费者验证。核心包保守上界19609598 B，小于33550320 B；这一步没有
生成或发行真实核心包，也不证明当前 VM 状态或维护成功。

两 caller 在现场动作前冻结于同一 D，来源采用仍受原 QI 权威绑定。私有不可变冻结记录
SHA-256 `a7672f12129948023c05a0ee1bafd12f3eb010a29255d97ee58694fcb2b24632`。
冻结时 DS2 NOT_STARTED、DS3 NOT_RUN；下述实际返回已替代可执行 release gate，
不可变冻结和原始证据均保留。

## 唯一08f已消费并停止

本次普通本地预检为 LOCAL_PREFLIGHT_PASSED，随后同一窗口执行一次维护调用。
创建原消费 marker，发出一次固定 pre SSH 后停止：

- Host：STOP_AND_RETAIN，exit3，外层原因 GROWTH_REPORT_MISSING。
- 原 guest v3 stderr：PRE_QUIESCENCE / GROWTH_BUSINESS_PROCESS，INCOMPLETE。
- 原 guest actions_started 为空；events没有 POWER_OFF_TOKEN。未发送关机令牌，
  journal备份/扩容、重启及文件系统扩容均未启动。
- remote_exit仍为UNKNOWN。DS3和H01/Q4/H11为NOT_RUN，没有发行真实核心包。

该原因来自保留的当前进程检查：非自身进程的cmdline含保护根，或exe/cwd落在保护根。
返回没有保存具体PID、匹配根或这两种检查中的准确分支，不能断言实际写入者或根因。
诊断context沿用上一次域查询的manager/unit，不是命中进程身份，不能据此归因该单元。
本次失败不允许将已批准的未知启动枚举缩减再解释为取消当前进程保护。

用保护读取核对并私有保留本次已产生的五件原件，marker/manifest/receipt关系、
transport字节数和摘要、原始events与stderr一致。新08f五件索引及原文仍私有；
未额外SSH、查询进程、补采、停止服务、清理、恢复或重试。

DS2唯一窗口为CONSUMED_FAILED，release gate为DS2_CONSUMED_FAILED_STOP_AND_RETAIN。
九代维护窗口及其累计义务继续保留，旧失败和UNKNOWN不改变。当前journal维护及
执行→取消→恢复查询核心链仍未完成。不得重放两冻结caller；任何进一步现场动作
或覆盖变化仍须依原R和准确范围处理，本记录不授予新窗口或新动作。
