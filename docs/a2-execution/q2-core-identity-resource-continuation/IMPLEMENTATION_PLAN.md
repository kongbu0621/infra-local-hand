# IR1–IR3 一次完整接续

**PROPOSED / Gate OPEN / NOT APPROVED**；`LH-Q2-CORE-IDENTITY-RESOURCE-CONTINUATION-v1`。
遵循[需求](REQUIREMENTS.md)与[架构](ARCHITECTURE.md)。当前三文档仅是待审A。

1. A只增加这三文档；Owner一次决定准确R/A、四叶身份策略采用、档位2、IR1–IR3及
   私有请求列明的原Q1目的地/载荷。先独立bookkeeping C登记CLOSED，再实现D，保留
   ancestry且不squash。一般继续指令不能补写为该准确新A的Owner决定。
2. 当前普通容量补丁 `167aa9760a3ce7053499ba2a744a9a4716449d92` 经PR #12及其准确
   首次CI完成正常合入；不因本A重跑已完成的来源调查或修改旧冻结。A/C/D均按正常
   PR流程保留；平台拒绝不得改入口绕行。
3. IR1在`q2_core_prior_attempt`实现固定19成员读取、旧v18记录绑定与无损历史还原；
   更新`q2_journal_growth`、delivery contract、approved-input、capacity、transition
   及独立dispatcher的新authority/schema/费用。不新增通用helper、扫描或运行服务。
4. 使用原计划四叶身份修复及档位2，并在两个消费者验证全部前后证明；新增固定
   11a会话，旧10d及所有旧事件保持。更新旧源码绑定对应的当前协议，不改历史记录。
5. 准备两个私有新caller，实际结果路径接齐schema、完整diagnostic、实际coordinator/
   custodian完成与EOF。只有完整IR2成功原件和独立消费者通过才发行原07a；早期
   failure、缺receipt/EOF、无法记录、超限均终态停止，不捕获后偷偷继续或retry。
6. 用已保留19成员验证私有原件哈希、旧preflight/marker、terminal/freeze及实际完成
   绑定。合成回归覆盖损坏、伪成功、缺/重复/额外成员、引用循环及成本遗漏/退款，
   不放宽真实路径/权限/身份边界。已完成保护读取不重发，不能拿现场作测试。
7. 在隔离本地真实文件、256-FD子进程和pre/post管道下验证全流程；固定现有来源派生
   全部payload及尺寸/费用上界，H01执行、Q4取消、H11恢复与结果路径做必要回归。
   主机维护22951MiB/6802inode，核心含capture为23079MiB/6834inode；17份完整义务，
   新source/archive准备各2MiB/64inode。历史固定读总CPU120秒包含其源码准备，不双计。
8. 先独立复核完整dispatcher并仅锁定其准确release digest，连同其它实现形成D；
   再正常发布准确D，其自己的首次CI三项、两平台独立安装及本地独立安装全部通过。
   保留中间失败，不能用CI rerun替换失败历史。完成最终protected来源/归档准备、
   caller依赖和private payload冻结。验证后再改源码必须成为另一个准确D并单独验证。
   冻结前不发行IR2；不得仅改白名单或把合成维护当作成功来提前发行核心。
9. IR2仅一次11a preflight，PASS则同窗execute，按原链完成至多两次维护SSH、正常
   关机、备份验证、journal增长、原配置一次重启和post完整验证。boot前后的固定
   runtime preparation各最多12命令/120秒，计入总预算；没有额外guest读取或安装。
10. IR2完整原件及实际顶层/子进程均成功后，直接IR3执行原07a H01→Q4→H11；批内
    不再逐项审批。逐案保存实际结果，任何阶段失败停止保留，禁止旧重放、新retry、
    补采、业务停服、清理、回滚、另一恢复/启动/窗口或外围工作。

本A只准备了可核对的固定归档尺寸、实际旧返回关系和费用；新归档文件、接续实现、
新caller及现场发行均未创建。IR1 NOT_STARTED、IR2 NOT_ISSUED、IR3/H01/Q4/H11 NOT_RUN。
