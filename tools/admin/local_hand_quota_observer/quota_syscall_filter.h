/* Parameter filter for the native query phase, not a complete sandbox.
 * It is installed only after the trusted FD inspection prelude has obtained
 * the project ID. The launcher must confine that prelude and the ELF loader.
 * The filter does not remove CAP_SYS_ADMIN or prove root/FS admission.
 */
#ifndef LOCAL_HAND_QUOTA_SYSCALL_FILTER_H
#define LOCAL_HAND_QUOTA_SYSCALL_FILTER_H

#include <errno.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/dqblk_xfs.h>
#include <linux/fs.h>
#include <linux/quota.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

/* Linux UAPI header constants only. No syscall-number fallback. */
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__ && \
    defined(__SIZEOF_LONG__) && __SIZEOF_LONG__ == 8 && \
    defined(__SIZEOF_POINTER__) && __SIZEOF_POINTER__ == 8
# if defined(__x86_64__) && !defined(__ILP32__)
#  define LH_QUOTA_AUDIT_ARCH AUDIT_ARCH_X86_64
# elif defined(__aarch64__) && !defined(__ILP32__)
#  define LH_QUOTA_AUDIT_ARCH AUDIT_ARCH_AARCH64
# endif
#endif

#if defined(LH_QUOTA_AUDIT_ARCH) && defined(SYS_seccomp) && \
    defined(SYS_quotactl_fd) && defined(SYS_fstat) && defined(SYS_ioctl) && \
    defined(SYS_close) && defined(SYS_write) && defined(SYS_getuid) && \
    defined(SYS_geteuid) && defined(SYS_exit) && defined(SYS_exit_group)
#define LH_QUOTA_FILTER_AVAILABLE 1
enum { LH_QUOTA_FILTER_MAX = 96 };

/* Both halves are checked even where the kernel normally truncates to int.
 * All callers supply zero-extended uint32 syscall arguments. Unknown ABIs,
 * including x32 syscall numbers on an x86_64 arch value, never match.
 */
#define LH_Q_DENY BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM)
#define LH_Q_ALLOW BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)
#define LH_Q_ARG_LO(n) ((unsigned int)offsetof(struct seccomp_data, args[(n)]))
#define LH_Q_ARG_HI(n) (LH_Q_ARG_LO(n) + 4U)
#define LH_Q_ZERO_HIGH(n) \
    BPF_STMT(BPF_LD | BPF_W | BPF_ABS, LH_Q_ARG_HI(n)), \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, 0, 1, 0), LH_Q_DENY
#define LH_Q_ARG_EQ(n, value) \
    LH_Q_ZERO_HIGH(n), \
    BPF_STMT(BPF_LD | BPF_W | BPF_ABS, LH_Q_ARG_LO(n)), \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (value), 1, 0), LH_Q_DENY
#define LH_Q_NOARG(number) \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (number), 0, 1), LH_Q_ALLOW

/* Exposed as a pure builder so tests can check every branch without invoking
 * a real allowed quota syscall. Nothing in the native CLI selects a policy.
 */
static unsigned short quota_filter_build(struct sock_filter *output, uint32_t project_id)
{
    const struct sock_filter rules[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, LH_QUOTA_AUDIT_ARCH, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        LH_Q_NOARG(SYS_getuid), LH_Q_NOARG(SYS_geteuid),
        LH_Q_NOARG(SYS_exit), LH_Q_NOARG(SYS_exit_group),

        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_fstat, 0, 7),
        LH_Q_ARG_EQ(0, 3), LH_Q_ALLOW,
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_close, 0, 7),
        LH_Q_ARG_EQ(0, 3), LH_Q_ALLOW,
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_ioctl, 0, 13),
        LH_Q_ARG_EQ(0, 3), LH_Q_ARG_EQ(1, FS_IOC_FSGETXATTR), LH_Q_ALLOW,

        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_quotactl_fd, 0, 27),
        LH_Q_ARG_EQ(0, 3), LH_Q_ZERO_HIGH(1),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, LH_Q_ARG_LO(1)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K,
                 QCMD((unsigned int)Q_XGETQSTATV, PRJQUOTA), 0, 7),
        LH_Q_ARG_EQ(2, 0), LH_Q_ALLOW,
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K,
                 QCMD((unsigned int)Q_GETQUOTA, PRJQUOTA), 0, 7),
        LH_Q_ARG_EQ(2, project_id), LH_Q_ALLOW,
        LH_Q_DENY,

        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_write, 0, 13),
        LH_Q_ARG_EQ(0, STDOUT_FILENO), LH_Q_ZERO_HIGH(2),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, LH_Q_ARG_LO(2)),
        BPF_JUMP(BPF_JMP | BPF_JGT | BPF_K, 4096, 0, 1), LH_Q_DENY, LH_Q_ALLOW,
        LH_Q_DENY,
    };
    _Static_assert(sizeof(rules) / sizeof(rules[0]) <= LH_QUOTA_FILTER_MAX,
                   "quota filter capacity exceeded");
    memcpy(output, rules, sizeof(rules));
    return (unsigned short)(sizeof(rules) / sizeof(rules[0]));
}

static int quota_filter_install(uint32_t project_id)
{
    struct sock_filter rules[LH_QUOTA_FILTER_MAX];
    struct sock_fprog program = {.len = quota_filter_build(rules, project_id), .filter = rules};
    return (int)syscall(SYS_seccomp, (unsigned long)SECCOMP_SET_MODE_FILTER,
                        0UL, &program);
}
#undef LH_Q_DENY
#undef LH_Q_ALLOW
#undef LH_Q_ARG_LO
#undef LH_Q_ARG_HI
#undef LH_Q_ZERO_HIGH
#undef LH_Q_ARG_EQ
#undef LH_Q_NOARG
#else
#define LH_QUOTA_FILTER_AVAILABLE 0
#endif
#endif
