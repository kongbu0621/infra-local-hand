# 固定角色、按 boot 准备、原维护与核心接续

**PROPOSED / Gate OPEN / NOT APPROVED**。Scope `LH-Q2-CORE-RUNTIME-CONTINUATION-v1`。
依[需求](REQUIREMENTS.md)，继续使用现有维护和核心组件，无新守护进程或通用执行接口。

## 准确来源和角色

保留全部历史 locator 原值、source relation 及其摘要。增加显式 `runtime_parent_binding`，
区分 historical locator 与本次使用的角色，不以整体替换旧 ordinary 字段掩盖来源变化。
离线仅使用以下已经保留的准确输入，拒绝 basename 搜索、另一副本或重新现场采集：

| 来源 | 固定依据 | 用途 |
| --- | --- | --- |
| 原 plan | `q2_core_delivery_freeze.TARGET_MEMBERS.plan`，9814 B，SHA-256 `efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c` | 四个 system 父 slice、用户账户、原 user slice 限额 |
| retry preparation | 同处 `retry`，61119 B，SHA-256 `586f0fd79ceb869a8e1ed238d925b6cdbf2cceaddf233687df81ea320bded4fb` | retained user slice 的逻辑路径及用户管理器关系 |
| 20261001e system plan | `q2_core_obligation_inputs.DELTA_PINS.plan`，30813 B，SHA-256 `85633b837718282ba6590b7a6679d51aa60addfb0f5be39ea929af83de4a45c1` | system ordinary 目标、32 tasks 及 controller 直接子域关系 |
| 原配置生成源码 | 候选 `4b6e4a7c403362358192086b88679e1326dcb2e1` 的 `q2_prepare.py`、`q2_prepare_contract.py` | 固定 slice 模板、用户管理器原 drop-in、CPU 表示 |

先校验既有归档/成员 pins，再核对原 plan 与 retry 的五父域名称、限额、层级和UID/GID，
以及 system plan 中不变四父域、retained 角色与新的 ordinary 子域。不得将历史 inode、
InvocationID 或 boot 当作当前身份。source pins、语义投影摘要和准确 R/A/C/D 在 host、
approved-input 和独立 dispatcher 中贯通；guest 独立检查投影的固定结构、pins、关系和
本次实际事实，不宣称在 guest 重新读取 host 私有归档。私有投影最多8192 B。

角色是四个原 system 父 slice + system ordinary slice + retained user slice：
ordinary 系统域为256 MiB/32 tasks，retained 用户域为256 MiB/64 tasks，controller
512 MiB/64 tasks，query 256 MiB/64 tasks，其余两父域512 MiB/64 tasks；全部 CPU=100%、
swap=0。原用户管理器256 MiB/64 tasks、CPU=100%、Delegate=cpu memory pids不变。
这些角色必须落在原声明域集合内，不能扩展19/7/7来迁就新的名字。

## 一次维护中的运行时准备

在原 pre/post SSH 内，各自先完成当阶段已有 boot、盘、父目录身份准入，再准备运行时。
准备是受记录的变更阶段，不能仍把整个 pre 声称为只读。每个阶段只能调用一次，动作
先记录 intent 再执行，未完成即保留；同 boot/phase/nonce 拒绝重复。post 必须是经本次
合格关机/增长/启动产生的新 boot，不能在失败后重新调用 pre 或 post。

1. 先执行已有业务 unit/cgroup/当前进程和持久数据保护检查中不依赖用户 bus 的部分，
   并检查固定准备目标、配置和账号。仅允许 inactive/dead 或完整匹配的 active 状态；
   failed、activating、残留 job、错误 User/Delegate/层级/限额或非空目标域一律停止。
   这些准入不是失败后的补采，不扩大到全机 unit/template 枚举。
2. 原四个 `/etc` slice 文件和专属 user-manager drop-in 必须逐字节匹配已核验原模板；
   缺失或冲突就停止，不补写 `/etc`。固定目标的 fragment/drop-in/遮蔽路径按原配置
   规则检查，只检查这些目标。不得调用整个 `q2_prepare` 或旧 retry caller，它们还会
   安装程序、创建数据根或执行其它旧动作。
3. 系统 ordinary slice 若已有唯一正确配置则复用；若在固定候选配置路径中均不存在，
   仅在 `/run/systemd/system` 创建该一个 unit，内容为原 slice 模板套用已固定 system
   plan 的 ordinary 限额。保留原 controller 子域层级。已有不同内容、链接、额外
   drop-in 或遮蔽就停止，不覆盖/删除/改名。新文件 root:root/0644、O_EXCL、no-follow，
   父目录通过保护检查；只在创建后执行一次 system daemon-reload。
4. 使用原 systemctl 工具绑定，至多一次 start 请求启动缺席/未运行的已准入目标：
   五个 system slice、UID 1100 的 runtime-dir 和 user manager。已 active 的目标不
   重启。unit 名来自上面的准确投影，不接受自由 argv；不使用 enable、linger、restart、
   stop、reset-failed 或附带业务 service。runtime-dir 由系统服务管理，不手工伪造。
5. 对当前用户运行时目录、socket、UID/GID、模式和稳定身份做原保护检查。在固定
   `/run/user/<uid>/systemd/user` 位置，复用正确 user slice 文件；不存在才按原 user
   slice 模板创建。目录只允许补齐这一路径的必要层级，文件ordinary:ordinary/0644，
   目录ordinary:ordinary/0755，祖先/runtime原模式约束不变；任何冲突都停止。
   创建后至多一次 user daemon-reload，至多一次 user start。用户操作固定UID/GID并
   清空附加组，使用准确 XDG_RUNTIME_DIR/DBUS_SESSION_BUS_ADDRESS 和原工具FD绑定。
6. 验证 manager/bus、两类 slice 的当前属性、cgroup 控制器/限额/空闲状态与目标配置。
   然后完成原完整 quiescence/process/writer/持久证据检查。原 poweroff token 前的
   final quiescence 保留；post 准备后同样通过原保护才允许 resize2fs。准备成功不能
   绕过业务进程拒绝，也不解释任意其他进程为“管理进程例外”。

每个阶段控制命令最多12次、60秒，所有新增检查/子进程计入原累计总额，单命令使用原
bounded transport。若只读准入发现管理前提不成立，动作尚未开始也停止该已消费窗口。
启动用户管理器可能触发既有默认用户目标；沿用 Owner 已接受的 declared-startup 前提，
不把该前提改写为已观测全机排除，实际出现受保护业务活动仍拒绝。

本程序每阶段最多创建两个配置文件及其必要目录，配置总量≤8192 B、对象≤16。
对这些新对象，按每阶段每个实际相关 guest pool 8192 B/32 inodes 保守预留；两阶段
累计16384 B/64 inodes，无退款，独立写入记录及完成前/后核对。既有 systemd 服务运行
开销继续计入原 VM、manager、维护 CPU/内存/进程预算；RT1 须核实全部成本均已覆盖，
不得将自动服务开销错误记作零或扩大原硬限额。新配置只在 `/run`，不修改持久启动策略。

## 核心独立消费与结果

`_capacity_managers` 从准确 runtime binding 取 system ordinary 名字，使用 system
manager 查询五个 system slice、user manager和carrier；retained user slice 单独通过
准确用户 bus 查询。解析记录以 `(manager, unit)` 区分，拒绝来源/角色混淆或漏项。
用户 helper保留可执行FD绑定、精确凭据、环境、期限、wait4/EOF/输出限额及bus前后稳定性。
增加的这一固定查询计入原核心管理预算，不开启重试或另一个 carrier。

运行时返回记录每个boot/phase的动作、实际tool返回/EOF、配置摘要/创建或复用、当前
manager/cgroup关系及限额。记录≤16384 B，不能只传 PASS 布尔值。host完整验证原件；
transition 携带严格有界的关系摘要与前后报告pins。独立核心消费者核对post boot、
runtime binding和当前重新取得的准确事实。当前inode/InvocationID需来自当前观察，
不能等于历史值才算通过，也不能复用维护前的当前身份。

修复普通角色与验证端同时采用新显式映射；路径表示使用已完成的逻辑→文件系统转换，
最终依然全路径相等。H01/H11使用system ordinary，Q4沿用retained user ordinary。
现有准备计划、geometry构造、collector和独立admission consumer一起验证，避免只改一端。

## 代次、协议及发行

追加旧09a第十个失败profile，五件原件按原v11 manifest/receipt、v3 guest解析，保留
原错误、零动作和UNKNOWN。新09b manifest/receipt v12、preflight v11、guest input/
report v4、transition v11，reconciliation/history v15、host-capacity v14；历史版本
仅按各自profile处理。新增runtime字段必须在生成端、host验证、历史consumer及独立
dispatcher同步严格校验，旧报告不能冒充新准备证明。完整resume保留，marker继续用
已经验证过的完整历史摘要，65536 B上限不变。

本准确A/B/C及继承C的D、完整来源/CI/独立安装和双方caller冻结之后才能RT2；RT2
完整原件验证后才能生成可发行核心包。新范围OPEN时发行允许表关闭，不借用VA授权。
旧所有 caller 和消费标记不变。没有真实维护成功证据就不得投影一个可用于发行的“成功”。
