# SY1 实现与隔离验证

范围 `LH-Q2-CORE-SYSTEMCTL-CONTINUATION-v1` / SY1–SY3，准确 A
`62666eeec9f2f28833876df3d68ce6e8b8e0af54`，独立 C
`7b342ced547639f93797e849b34ed3da4915c8d3`，其 tree 为
`ec1ed26d198c9226816ff00de6896eb3d7e102de`。准确决定见
[Owner B](../governance/Q2_CORE_SYSTEMCTL_CONTINUATION_OWNER_DECISION.md)。
本实现承接 C，三文档原字节不变；旧06a/07a消费不改变。

## 实现和审查

- 新维护固定为 `lhqjgrow-20261007b`，核心仍为原未发出的 `lhqcore-20261007a`。
  旧两代各五原件与四缺席名均保护读取、去重和重新校验；07a按旧SC协议解析，并严格
  绑定其内部06a resume。既有同FD重读先seek到起点的修复保持。
- 新manifest/receipt v4、preflight v3、transition v3、reconciliation/history v7和
  host capacity v6接齐；两侧独立消费者拒绝旧协议、错代次、缺失、错序及布尔冒充数字。
  增加准确新A/B/C及继承关系准入；保留原systemctl `--`及同次有界失败信息。
- 三代完整维护条件3888 MiB/1110 inodes，加原核心为3952 MiB/1126；旧费用/UNKNOWN
  不释放。原单次预算、权限、目标检查和期限保持；没有新增扫描、helper或通用组件。
- [旧07a最小索引](Q2_CORE_SERIAL_ORIGINALS_INDEX_20261007.md)已按本次Owner许可登记。
  原私有索引、保留副本及已有调用方输出关系一致；两代保留副本通过实际新解析器。
  原文和其它机器元数据未公开，也未补采。

审查后的独立dispatcher SHA-256为
`5a824dd169e73d3b35eb7307a6ae16920075c63c72338c8af09ecf5ea8608dc2`。
放行只固定此准确源码，仍要求该候选CI/冻结、完整SY2原件、新boot及所有准入。
原runtime/wheel/projection/loader与核心任务身份、取消/恢复语义保持。

## 验证事实和边界

受影响core/journal源码及原journal链组共2346项：2288 passed、35 skipped、23项因普通
宿主umask0002生成组可写测试文件而失败。在隔离测试子进程使用022，仅重验这23项，
23 passed。生产路径保护未修改。前期沙箱映射权限/只读目录失败及旧测试fixture协议
同步前失败日志均保留，没有描述成首次全绿。新增两代历史/嵌套resume和消费者拒绝测试
包含在本组内；独立目标组也为224 passed。

新完整预检使用实际构造，2798 B，原4096 B上限保持；两维护源63730/55793 B，均在
原98304 B内。完整transition、approved-input和包界限继续由原构造/消费者测试验证。

当前仅实现与本地隔离验证完成；准确候选发布后的首次CI、独立安装及静态八输入检查、
两段caller冻结仍须完成，不能把旧c1fa156 CI当作新候选CI。SY2尚未开始，SY3/H01/Q4/H11
尚未执行；CI或合成维护原件不构成现场成功。任一现场失败停止，不重试、补采或清理。


发布后逐条审查补齐了预检顶层准确R/A/C，除原D和完整resume外再显式绑定本次授权。
相关授权/双侧消费/协调器/历史准入组再次通过（300 passed），旧修正前提交不作为现场
冻结候选。最终准确D须包含此修正，并通过其自己的首次CI；现场尚未执行。

## 模板与别名的源码修复

上文“现场尚未执行”是 SY1 当时状态；最新 [SY2 原始返回登记](Q2_CORE_SYSTEMCTL_CONTINUATION_FIELD_20261007.md)
已明确：07b 单次窗口失败且消费，systemctl show 退出1、双EOF完整、stderr拒绝未实例化
模板单元。三个旧维护代次与原件保持，扩容和 H01/Q4/H11 仍未执行。

具体错误在 startup_manager 将 list-unit-files 的模板名和 list-units 的运行单元合并，
再全部交给 show。模板不存在可查询的运行实例，systemd 正确拒绝；原参数分隔修复没有
解决这一类差异。官方 v255 的 [list-unit-files 文档](https://github.com/systemd/systemd/blob/v255/man/systemctl.xml)
和 [manager_load_unit_prepare](https://github.com/systemd/systemd/blob/v255/src/core/manager.c)
确认这一行为，不是凭安全提示猜测原因。

此次只修正这条既有核心准备路径：

- 未实例化模板改用 `cat -- <name>`，读取原 fragment 和 drop-ins，检查完整内容中的受保护路径，
  对启用模板保留间接启动拒绝。禁用、静态和 masked 模板也不能直接跳过内容；不创建试探实例，
  不执行 daemon-reload、启用或启动操作。读取仍使用原受限命令及原1 MiB流上限。
- 模板内容检查不是配置合并器；Exec 指令和续行按保守文本处理，已覆盖的旧 Exec 值仍检查。
  因此它可能拒绝包含被覆盖间接命令的配置，不能宣传为 systemd 解析的完全替代。
- 普通单元和实际实例继续原 show。对同类的别名差异，在同次查询增加 Names，按正式 Id 和
  已证实别名映射请求；缺失、无关返回、冲突和重复属性变化仍拒绝。已声明业务/域单元仍须
  正式 Id 精确相等，不允许别名替换身份，也不增加别名补查。
- 保留原非零返回码、双EOF、非空stderr拒绝、同次有界诊断、目标保护、预算、协议及次数。
  没有恢复宿主扫描、增加通用诊断平台或修改已批准三文档和冻结现场源码。

模板读取语义核对了官方 [unit_find_paths](https://github.com/systemd/systemd/blob/v255/src/systemctl/systemctl-util.c)
和 [verb_cat](https://github.com/systemd/systemd/blob/v255/src/systemctl/systemctl-edit.c)；Id/Names 来源核对了
[D-Bus 单元属性](https://github.com/systemd/systemd/blob/v255/src/core/dbus-unit.c)。
模板分流、fragment/drop-in、掩码、间接启动、别名完整覆盖和声明身份均有定向回归验证。

本地最终 journal 全组加 minimal/serial/systemctl 核心接续组：**613 passed / 5 skipped**，
用时4.82s。两个既有跳过来自 PID/proc 映射和缺少 qcow2/ext4 工具；三个新增原生 cat
测试因云沙箱禁止创建私有 Unix socket 跳过，不能计为通过。原生测试只用临时 unit 目录
和无 systemd manager 的私有 D-Bus，不访问真实管理器，并留待 CI 验证。
模板合成组68通过，systemctl/别名组32通过，已包含在上述613项内。首次别名测试曾因
测试断言放错函数出现 NameError，已修正并重验；没有因此修改运行实现或放宽检查。
`git diff --check`通过；host/guest维护源63730/59175 B，均低于原98304 B上限。

本次为源码修复与离线验证，不生成新 caller 或重新消费 SY2。准确候选 CI 须以该候选
自己的运行结果为准；旧 CI 不替代新验证。只有本地持有既有私料和真实终端，才能在有效的
后续单次边界内接现场维护；完整维护成功后继续同一个未发出的 H01→Q4→H11。
