# EX1：五代历史与单次维护绑定实现审查

准确批准A `5b14123206ced8117374d3fd2ef84b9f38784db3`，独立C
`987c77f6eb16e7ca41d8b1d4ccd7f89faf418d32`，R保持。准确Owner B见
[决定](../governance/Q2_CORE_EXEC_CONTINUATION_OWNER_DECISION.md)。实现承接C；
A三文档原字节及历史OPEN标签不改，EX2/EX3须等待全部冻结条件。

## 实际变更与范围

第五代08b按原manifest/receipt v6、原R/A/C/D及四代嵌套resume严格解析，早期各代
保持原schema和嵌套关系。五代25件原件、20缺席名贯穿原保护读取、消费前同FD重读
和核心读取；元数据、held FD、单链接、上限和跨集合inode去重保持。
获批[旧08b五件索引](Q2_CORE_NAMES_ORIGINALS_INDEX_20261008.md)已经与原私有索引和
保护读取的保留副本核对；仅公开basename/bytes/SHA-256，原文和机器信息保持私有。

新08c manifest/receipt v7保存完整五代历史；短预检v6保留既有canonical含LF摘要表示，
由实际已验证manifest.resume构造，解析器核对固定完整历史，execute重建并比对完整
manifest、历史摘要、D、nonce、原钟和累计用量。拒绝旧v1–v5、重哈希篡改、缺失原件，
不以摘要代替任何原历史语义检查。五代真实pins、最大计量/20位钟样本仍 **708 B**。

准确R/A/B/C、A/C树、三文档在A/C/D、B在C/D及独立C祖先由维护入口和完整freezer核对。
核心host与独立guest同步transition v6、reconciliation/history v10、capacity v9；
六代维护7776 MiB/2220 inodes，含核心7840 MiB/2236（8220835840 B），各120 CPU-s。
旧全部消费、完整费用和UNKNOWN保留；所有原单次预算、限额和期限不变。

host源66421 B、guest源61275 B均低于98304 B。相对输入修复e2d27ca，guest唯一变化为
固定session 08b→08c；Exec成员保序、Names显示解码和全部原命令检查保持。
所有历史64位来源pins保留，仅当前dispatcher发布允许值更新为准确新源码摘要
`192ac9ebfd024e970498b2e4a5e7b72a2d62625403510f21812e03f5ff266747`。
原runtime/wheel/projection/loader、现场安装、SSH文法及H01→Q4→H11语义保持。

## 本地验证

维护和核心受影响文件首次 **2914 passed / 48 skipped / 1 failed**。唯一失败来自旧测试
仍断言四代历史；按本次五代要求更新断言，精确复核 **1 passed**。没有为此修改产品
实现或放宽限制；首轮日志及环境跳过保留，不把首次全组描述为全绿。

新EX测试覆盖第五代原四代resume的缺失/替换/顺序/授权/类型/额外字段反例，准确A/B/C
字节、树、祖先和C不能作D、旧v5交接及旧四代摘要拒绝。既有逐件保护读取、20缺席名、
内部关系和两侧投影反例扩展至第五代；原完整动作合成路径、真实JournalDevice隔离测试
及Exec/Names/模板/systemctl检查继续纳入受影响组。未查询真实manager或VM。

## 发布和冻结前置

本记录随实现提交，尚不宣称准确新D首次CI、独立安装、原八输入/四旧核心/五代维护
原件和完整静态来源核验已经完成。两个新私有caller已准备但未执行，旧caller和
冻结副本保持原样。必须先完成新D发布、准确CI、安装、来源/原件及全部大小上限，
再冻结同一D；此前EX2/EX3均NOT_RUN，无现场预检、SSH或真实核心包。
