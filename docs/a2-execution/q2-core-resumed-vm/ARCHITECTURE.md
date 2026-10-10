# 旧安装与当前运行身份的接线

**PROPOSED / Gate OPEN / NOT APPROVED**；`LH-Q2-CORE-RESUMED-VM-v1`。
实现[需求](REQUIREMENTS.md)，复用既有维护、核心执行与证据路径，不新建产品服务。

## 三段来源各自保真

旧 activation/v1 保持原始字节、旧 host/guest boot 和安装结果，继续由旧验证器验证。
已完成的启动返回独立证明本次原配置启动、当前 host/VM 身份、镜像文件身份及旧记录保护，
只改变 PID/serial 输出名；它不证明 guest boot、包完整性或 guest 就绪。
RC2 新返回证明当前 guest 身份与准确已安装包、内核/模块和 quota 挂载的当前状态。

维护采用新的 `local-hand-q2-vm-activation/v2` 投影。共有定位/身份字段保持原义，另绑定
历史 activation 摘要、启动返回摘要、RC2 固定来源/nonce/返回摘要，明确当前检查无安装。
historical_boot_id 仍对应原 Q1 证据；current_boot_id 只能取本次成功 guest 返回。
历史包安装成功与当前包校验成功分别表示，不把旧包摘要声称为当前整盘内容摘要。
execution_permission 仍为 false；来源验证不能自己授予执行权限。

v2 只有在三段原件、准确批准、冻结输入及前后身份全部匹配时可生成；保留 v1 的历史解析，
但新批次不接受 v1 代替当前证明。guest 首尾 boot 须相同且不同于历史 guest boot；
host boot、固定 PID/start/argv/exe/namespace、端点、已信任 SSH host key 和镜像文件身份
必须与本次批准启动相符。拒绝缺件、自报成功、只改 boot、包版本漂移、错误模块/挂载，
以及字段未知或前后漂移。不得从 host LISTEN 推导 guest 通过。

RC2 只运行固定的 boot/内核读取、准确包查询与校验、模块元数据/解析及原挂载查询，
沿用先前安装证明的准确包名、版本与目标。模块解析只展示依赖，不安装或实际加载模块。
完整 EOF、退出码、原始 stdout/stderr、计数、前后固定身份和实际顶层完成共同决定成功。

## 输入与成本不靠增加上限解决

新组合来源替换现有 activation 归档占用的一个父 FD，保持该归档 524288 B 上限。
使用固定 USTAR 成员和显式命名空间，含旧 activation 原件、本次启动所需原件、RC2 原件、
10b 六返回及原 freeze/失败/终态。相同源码字节可由明确摘要引用唯一成员；原文件索引
和映射仍可无损重建。不接受链接、重复/额外成员、路径穿越、非零尾数据或自报摘要。
已有全部私有原件保持原位置/字节；组合归档不是删除、修改或重放原件的理由。

10b 明确为已调用未消费预检、SSH/marker/execute 均零，无维护原件；不补造 receipt，
不加入旧 55 件集合，不计作第十三代已消费维护。09c/10a 原归档、55 件 custody 和
分阶段 FD 所有权不变。原件及组合归档的实际 FD/name/bytes 持有和漂移核验持续到退出。

现有布局上界为交接前 122、交接峰值 128、交接后 90、custodian 64、核心准备 126。
单归档替换不增加持有数量，但仍须验证真实新增解析和最终保存的完整生命周期。
RC2 核验进程先结束且完整保存返回，才进入维护的原持有集合；不能隐瞒并发子进程费用。

现有启动索引有 22 项、原字节合计 109942 B；10b 九项合计 53803 B。
这些仅为离线保留材料尺寸，不是未来完整归档或 manifest 已通过的证明。RC1 必须用
准确来源和有界最大 RC2 返回验证布局；真实 RC2 返回填入后再次核验，超界停止。

## producer、消费者和条件发行一致

`q2_core_prior_attempt.py` 验证旧安装、当前启动及新 guest 返回的关系；
`q2_journal_growth.py` 采用新当前身份并持续复查，guest pre/post 保持严格 boot 绑定。
维护 manifest/receipt、preflight、transition、approved-input、capacity/obligations、
独立 dispatcher 与 entry/freeze 同步版本、准确 R/A/C/D、session10c 和十五份义务。
新版本不得由旧版本解析器静默接受；历史失败继续用其原始规则读取。

完整 resume 仍只编码一次，以摘要引用，包含历史 10b 的真实失败事实；不重复内嵌整份
旧 manifest/freeze。v2 原始验证与独立消费者的投影验证分开，不能以同一个函数互证。
维护后只有完整原件、coordinator completion、custodian 正常退出和最终资源用量通过，
才能构建原 07a 核心包。H01/Q4/H11 的接口、任务语义和数据保护不改。

原限额：host/guest 源码各 98304 B、custodian 16384 B，marker/receipt/描述/transition
各 65536 B，压缩/展开 bundle 49152/393216 B，argv 65536 B，preflight 4096 B，
approved-input 1048576 B，核心包 33550320 B；v2 投影仍限 4096 B。任何未知/超界不得发行。
