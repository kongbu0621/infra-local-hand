# GS1：guest 管理前提、覆盖声明及六代历史实现审查

准确批准 A `7ea9aed6a4f8be6d6fee0ee549e1e02378f32672`，独立 C
`001bd4f7baedf115ce67feba87a21d8e259c8d1d`，R 保持。准确 Owner B 见
[决定](../governance/Q2_CORE_GUEST_STARTUP_CONTINUATION_OWNER_DECISION.md)。
实现承接独立 C；A 三文档及其历史 OPEN 标签不改。

## 实际变更

移除普通单元和模板的通用间接启动类别阻断，以及仅服务于该分类的模板 Exec 编码
判断。完整属性、模板文本及 UTF-8 读取保留，全部 Exec 成员、直接业务根引用、业务
静止和启动边、domain/cgroup、当前 writer、持久数据与原命令身份检查保留。没有
cron 白名单、替代观察器、额外探针、权限、服务停止或配置修改。

原 CLI 增加明确 guest 前提确认，缺少时在输入读取及窗口之前拒绝；不能由 host
前提推导。固定四字段 `guest_startup_assurance` 接入 source binding、descriptor v2、
pre/post/失败/关机报告 v2、manifest/receipt v8 和 transition v7；host 与独立 guest
严格检查字段、类型和值。每个实际 manager 明确 `NOT_PERFORMED`，manager 集合严格
等于 system 加上 descriptor 确实声明时的 user_1100；不对旧报告默认补值。

新 session 固定 08d，短预检 v7 保留原 4096 B 合同。六代真实 pins、最大计量和
20 位时钟样本为 **708 B**。六代 30 件原件、24 个缺席名及新九名同时接入维护与
核心消费者。08c 按旧 EX v7、旧 v1 guest 报告及原五代嵌套历史校验，保留消费和
UNKNOWN。[获准旧 08c 五件索引](Q2_CORE_EXEC_ORIGINALS_INDEX_20261008.md)已按原保护
读取与私有原始索引交叉核对，未回现场查询。

核心 reconciliation/history v11、capacity v10 与独立 dispatcher 同步。七代维护
9072 MiB / 2590 inodes，加核心为 9136 MiB / 2606（9579790336 B）；原每代
120 CPU-s、所有单次限额及期限保持。原 runtime/wheel/projection/loader、安装、SSH
文法及 H01→Q4→H11 语义不变。所有旧来源 pins 保留，只有当前 dispatcher 发布允许值
更新为准确源码摘要 `a8306815b71fef841d94d3ed8117a76644c9b262c631673d4c17242dbb2543cc`。
host 源 67956 B、guest 源 61741 B，均低于各自 98304 B。

## 本地验证及保留失败

首轮受影响组为 **2767 passed / 48 skipped / 267 failed / 50 errors**。多数失败来自
新覆盖字段尚未接入核心原件精确字段集合，以及旧测试输入尚未更新协议；已修正接线。
另外保留本地 HOME 权限和私有 D-Bus socket 环境限制，未以跳过代替实现修复。

在普通本地用户环境重新运行同一受影响组，得到 **3084 passed / 48 skipped /
1 failed**。唯一剩余失败是新 CLI 前提测试模拟了无限资源上限却未模拟恢复调用；
产品已经按预期拒绝缺失 guest 前提，修正测试模拟后，GS 定向组 **92 passed**。
这 92 项包含新增的 system/user 两种准确 manager 集合正例。首轮、第二轮及定向
日志和 XML 均保留，不将此前两次运行表述为全绿。

定向风险覆盖：类别不再误拒但直接引用仍拒绝，覆盖声明缺失/否认/类型/额外字段与
旧 schema 拒绝，host/独立 guest 投影，pre/post manager 集合，六代顺序、原授权、
消费及重算摘要后的旧嵌套篡改，准确 A/B/C 字节和祖先。既有完整合成维护及核心
接线、保护读取、内容/容量/时限和原大小边界仍在受影响组。未运行真实 VM 探针。

## 发布与冻结前置

本记录随实现提交，尚不宣称新 D 自身首次 CI、独立安装、原私料静态核对及冻结已经
完成。两个新私有 caller 已准备，均未调用；必须完成这些验证后冻结同一个 D，才可
进入唯一 GS2。GS2 全部成功原件经验证后才允许 GS3；失败即保留并停止。当前未消费
08d，没有 SSH、维护动作或真实核心包。旧 caller、旧消费和原件保持。

## 首个发布候选的跨平台失败修复

首个 D `1086aa15f2e74ee6012c6ee0d40876742ff90990` 的首次 CI
[37731069584](https://github.com/kongbu0621/infra-local-hand/actions/runs/37731069584)
中，Windows 源码组 **1782 passed / 1352 skipped / 26 errors**：纯原件投影校验
及共用合成 fixture 错误导入 Linux guest runtime，触发缺少 fcntl。未绕过 Windows
测试或重跑该次 CI；未冻结或执行该 D。

修复使纯投影校验在原模块内执行相同的固定四字段 canonical 严格比较，合成 fixture
独立声明相同对象，消除 Linux runtime 导入依赖。新测试禁止导入 fcntl/pwd/resource
及 guest runtime，验证完整 artifact 仍通过。局部组 **166 passed / 1 failed**，
唯一失败是该新测试误把 fixture 的 policy 字典作为序列化输入；修正测试输入后
该项 **1 passed**。全部首次日志保留，现场窗口仍未消耗。后续修复 D 仍须自身首次
CI、独立安装、准确来源/大小核对和冻结，不能沿用旧 D 的验证身份。
