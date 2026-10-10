# IR1 实现与离线核对

本记录落实已关闭的 `LH-Q2-CORE-IDENTITY-RESOURCE-CONTINUATION-v1`。
准确 A `e16b9038eb825f06306a6fe94bc2be30cc418238` 的三文档未修改；
独立 C `f74725156ed0fa5bfc1c9760ca9efd1afd110870` 在实现之前。
Owner 一次批准 IR1–IR3 及固定目的地的私有载荷，范围内无需再逐项审批。

## 原始返回、身份与容量

新增固定 19 成员、798720 B 的私有归档消费者；内层旧归档保持原字节和旧解析器。
同时绑定旧10d五个实际原件、冻结与终态、caller开始/完成/原始输出、preflight和execute
返回。检查原件索引、manifest摘要、无损历史引用、失败诊断、实际coordinator/custodian
退出、caller输出摘要及旧VM来源。旧guest诊断按当时host实际保留的四字段子集比较，
不把当时未传播的额外诊断伪装成host已保存的数据。没有新造旧原件或补采现场。

旧10d仍是已消费失败：caller/coordinator退出3、custodian退出0；guest报告为
PRE_RUNTIME_PREPARATION / GROWTH_PATH_PROTECTION，远端完成仍UNKNOWN。
保留全部16份历史维护义务，新的11a为第17份完整义务；旧09c/10b仍为调用过但未消费的
preflight，不能据此重放。19个父输入绑定与55个custodian持续持有的旧原件保持。

本次采用已实现的四个历史quota叶目录来源身份策略和两倍当前执行上限；不增加全局
UID例外。前后path/device/inode和UID/GID/mode证明、原Q1及19/7/7、进程/写入者/数据
检查仍由维护生产者和独立核心消费者共同检查。当前协议采用manifest/receipt v20、
preflight v19、transition v20、host-capacity v21及核心reconciliation/capacity v22。

17份维护义务共22936 MiB/6322 inodes，CPU2160秒；16份旧义务仍各1296 MiB/370 inodes/
120秒，新11a为2200 MiB/402 inodes/240秒，新增904 MiB/32 inodes只计一次。
计入所有旧读取/准备、新source/archive各2 MiB/64 inodes及核心capture后，完整主机
条件为23079 MiB/6834 inodes；维护自身为22951 MiB/6802 inodes。已完成保护读取与其
源码准备合计CPU120秒，不重复计费、不退款。普通漏计修复PR #12准确首次CI
`38070750255` attempt 1三项成功，正常merge为`0b50988991895b46f75f8f1a570fc51148b4144c`。

## 完整发行源码复核

将完整dispatcher与上次已冻结版本 `a3f9dbeca268de80124f524ccee4f1437bd61784` 比较，
核对全部变化：当前/历史上限分离、保护读取费用、旧10d来源与新authority、四叶前后
证明、资源汇总和独立核心输入验证。原H01→Q4→H11任务参数、逐案判定与失败停止路径
保持；H11仍只能恢复原同任务。重新检查入口的源码/可发行状态双重门槛，修改字节及
旧候选均拒绝。仅锁定复核后的完整dispatcher SHA-256：
`645de8571fb812c7b713af2eff53ab0255814ed7ce1edf57f139bcbc69000152`。
这项源码锁定不能替代准确D首次CI、独立安装、实际维护成功或核心PASS。

## 私有调用与验证范围

新调用候选保持一次preflight、仅PASS同窗execute；原始stdout/stderr、完整diagnostic
和本地解析/断言/I/O堆栈通过实际结果路径保留。维护完成接受器额外核对顶层caller的
实际退出、双EOF和原始输出摘要；再验证coordinator/custodian及两个独立消费者。
核心只在全部通过后构造原07a包；其返回按实际COMPLETE决定退出码，异常停止并保留。
24项私有合成调用回归通过，覆盖失败传播、畸形输出、原始字节保存、拒绝重放、完成
缺失/失败/EOF不完整，以及核心启动门槛。没有用现场作测试。

真实保留源已通过两个消费者；只读固定来源推导的pre/post压缩载荷约36/40 KiB，
descriptor约29/49 KiB，marker约54 KiB，完整receipt上界约46 KiB，均低于当前边界。
维护FD交接峰值128，独立核心准备上界126，均在256内；guest上界98。
这些是离线数据形状和静态上界，不声称已观察到当前VM或已有成功维护报告。

私有新归档已按批准创建。首次沙盒准备在父目录owner映射处失败，未写归档；正常宿主
权限的准备成功，实际分配806912 B/3 inodes。保留失败记录，未降低权限谓词。
Q2沙盒测试同类真实权限/套接字限制单列保留，正常宿主隔离回归用于验证实际权限边界。

当前实现仍需准确D首次CI、正常PR发布、本地及两平台独立安装和最终调用冻结。
IR2尚未发行，IR3/H01/Q4/H11尚未运行；这些检查不能提前改写为现场PASS。
