# 固定来源与单次本机读取边界

PROPOSED / Gate OPEN / NOT APPROVED；`LH-Q2-CORE-HOST-REBOOT-READ-v1`。
实现[需求](REQUIREMENTS.md)，只为原核心的新启动周期补齐有界本机证据。

## 固定来源

私有输入绑定RP1 immutable freeze、RP2原始preflight/本地返回索引/terminal、现有两份
798720 B及409600 B归档，以及原固定启动来源。HB1逐字节核验来源关系，重建activation
并与freeze相等；新proposal只从这些来源派生对象列表、旧实例和端口，不扫描寻找配置。
当前镜像身份只比较保留的device/inode及保护属性，不声称旧prelaunch内容摘要仍代表
当前盘内容。原UID/写位、无跟随、稳定身份和文件类型检查保持；不为通过读取改权限。

固定对象是activation列明的system/quota/journal/evidence/seed和被保留的original
system，共六个；原pidfile和serial仅检查固定条目，pidfile限64 B，serial不读内容。
进程范围最多两个：旧activation PID，以及固定pidfile中的有效PID（相同则去重）。
先读有界stat和exe身份；仅exe匹配固定QEMU时再读cmdline与命名空间，遇到其它程序
只保留不匹配事实。不会跟随监听输出扩大进程范围，也不
枚举/proc、目录树、其它端口或其它VM。所有实际路径只在私有proposal列出。

## 一次执行与证据

reader只接受准确R/A/B/C/D、Owner决定、来源摘要、固定目的地和输出槽。新调用记录
以O_EXCL创建，失败也终结；旧事件和caller绝不复用。输入持有、重查和最终索引保留
实际读取关系，不能声称此前已持续持有外部原件。父捕获保存双流、EOF、退出及异常。

host boot和自身命名空间在同次读取前后核对；不得通过命名空间映射伪造与旧boot相等。
当前boot与旧activation/RP2 window的关系仅记录；旧boot变化不是新VM已验证的证明。
读取PID时保留starttime/argv/exe/namespace，前后稳定性失败则停止，缺失与复用分开。
镜像使用无跟随metadata句柄及路径复核，不读取块内容。固定工具由受保护路径和打开
句柄核对；唯一ss查询严格限定原host-forward TCP监听端口，只做本机kernel查询。

不创建网络连接、不读取私钥内容、不执行guest源码。原SSH目的地仅用于从原argv派生
一个本机监听过滤条件。命令双流有界且需真实EOF与退出；超时不重试、不改过滤器。
输出含阶段、已持有身份、实测用量/限制、异常及有界流预览；未采样项保持UNKNOWN。

## 独立消费者及接续边界

独立离线消费者验证完整来源pin、请求/nonce、实际调用记录、双流和完成索引，并区分
读取完成、VM缺失、PID复用、监听占用、对象不符或未知。它不写activation/v3，不
更新dispatcher发行白名单，不生成维护/核心package。任何后续身份采用必须包含当前
guest/安装证明与准确启动来源，不能把本机结果改称guest已通过。

保留原18份维护、55份旧custodian原件、全部旧读取/准备和两份固定归档；本批不改
历史版本和费用消费者。新准备/捕获分别计费，最多一个控制子进程，实际FD/CPU/RSS/
AS及完整序列化上界在HB1隔离验证，超限则在本方案边界内修复或停止，不临时加限。
