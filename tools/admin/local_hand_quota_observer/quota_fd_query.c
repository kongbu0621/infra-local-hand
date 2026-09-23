/* Q1 internal ABI primitive. Not an installed service or an admission decision.
 * A future supervisor supplies its already-admitted directory as inherited fd 3.
 * No paths, commands, project IDs, or quotas are accepted from argv/environment.
 * This executable MUST NOT have setuid bits or file capabilities.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/dqblk_xfs.h>
#include <linux/fs.h>
#include <linux/magic.h>
#include <linux/quota.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/vfs.h>
#include <unistd.h>
#include "quota_syscall_filter.h"

enum { ROOT_FD = 3, MAX_CALLS = 16, OUTPUT_BYTES = 4096 };
_Static_assert(sizeof(struct fsxattr) == 28, "unsupported fsxattr ABI");
_Static_assert(offsetof(struct fsxattr, fsx_projid) == 12, "unsupported project ABI");
_Static_assert(sizeof(((struct if_dqblk *)0)->dqb_bhardlimit) == 8, "unsupported quota ABI");
_Static_assert(QIF_DQBLKSIZE == 1024, "unsupported generic quota block unit");

struct call { const char *name; long rc; int error; };
struct report {
    const char *status, *code;
    int exit_code;
    struct call calls[MAX_CALLS];
    size_t count;
    unsigned quota_calls;
    bool root_seen, fs_seen, project_seen, state_seen, quota_seen, hard_bytes_valid;
    bool root_after_seen, project_after_seen, state_after_seen;
    bool no_new_privs, filter_installed;
    struct stat root;
    struct statfs fs;
    struct fsxattr project;
    struct fs_quota_statv state;
    struct if_dqblk quota;
    struct stat root_after;
    struct fsxattr project_after;
    struct fs_quota_statv state_after;
    uint64_t hard_bytes;
};

static void record(struct report *r, const char *name, long rc, int error)
{
    if (r->count >= MAX_CALLS) _exit(70);
    r->calls[r->count++] = (struct call){name, rc, error};
}

/* Capture errno immediately, before formatting or another library/syscall call. */
#define OBSERVE(r, label, expression) do { \
    errno = 0; \
    long call_rc = (long)(expression); \
    int call_errno = errno; \
    record((r), (label), call_rc, call_errno); \
} while (0)

static bool succeeded(const struct report *r)
{
    return r->count && r->calls[r->count - 1].rc == 0;
}

static void fail(struct report *r, const char *status, const char *code, int result)
{
    r->status = status; r->code = code; r->exit_code = result;
}

static void query(struct report *r, unsigned int command, unsigned int id,
                  void *output, const char *label)
{
#ifdef SYS_quotactl_fd
    r->quota_calls++;
    OBSERVE(r, label, syscall(SYS_quotactl_fd, (unsigned long)ROOT_FD,
                             (unsigned long)command, (unsigned long)id, output));
#else
    (void)command; (void)id; (void)output; (void)label;
    fail(r, "UNSUPPORTED", "QUOTACTL_FD_ABI_UNAVAILABLE", 3);
#endif
}

static bool enforced(const struct fs_quota_statv *state)
{
    unsigned int required = FS_QUOTA_PDQ_ACCT | FS_QUOTA_PDQ_ENFD;
    return state->qs_version == FS_QSTATV_VERSION1 &&
           (state->qs_flags & required) == required;
}

static int stat_root(struct stat *value)
{
#if LH_QUOTA_FILTER_AVAILABLE
    /* Avoid libc fstat implementations that use path-capable newfstatat. */
    return (int)syscall(SYS_fstat, (unsigned long)ROOT_FD, value);
#else
    (void)value; errno = ENOSYS; return -1;
#endif
}

static void inspect(struct report *r)
{
#if !LH_QUOTA_FILTER_AVAILABLE
    fail(r, "UNSUPPORTED", "RESTRICTION_ABI_UNAVAILABLE", 3); return;
#endif
    OBSERVE(r, "fstat.before", stat_root(&r->root));
    if (!succeeded(r)) { fail(r, "REJECTED", "ROOT_STAT_FAILED", 2); return; }
    r->root_seen = true;
    if (!S_ISDIR(r->root.st_mode)) {
        fail(r, "REJECTED", "ROOT_NOT_DIRECTORY", 2); return;
    }
    OBSERVE(r, "fcntl.getfl", fcntl(ROOT_FD, F_GETFL));
    const struct call *flags = &r->calls[r->count - 1];
    if (flags->rc < 0) { fail(r, "REJECTED", "ROOT_FLAGS_FAILED", 2); return; }
    if ((flags->rc & O_ACCMODE) != O_RDONLY || (flags->rc & O_PATH)) {
        fail(r, "REJECTED", "ROOT_FD_MODE_UNSUPPORTED", 2); return;
    }
    OBSERVE(r, "fstatfs", fstatfs(ROOT_FD, &r->fs));
    if (!succeeded(r)) { fail(r, "UNSUPPORTED", "FILESYSTEM_STAT_FAILED", 3); return; }
    r->fs_seen = true;
    if (r->fs.f_type != EXT4_SUPER_MAGIC && r->fs.f_type != XFS_SUPER_MAGIC) {
        fail(r, "UNSUPPORTED", "FILESYSTEM_UNSUPPORTED", 3); return;
    }
    OBSERVE(r, "ioctl.fsgetxattr.before", ioctl(ROOT_FD, FS_IOC_FSGETXATTR, &r->project));
    if (!succeeded(r)) { fail(r, "UNSUPPORTED", "PROJECT_QUERY_FAILED", 3); return; }
    r->project_seen = true;
    if (!r->project.fsx_projid || !(r->project.fsx_xflags & FS_XFLAG_PROJINHERIT)) {
        fail(r, "REJECTED", "INHERITED_PROJECT_REQUIRED", 2); return;
    }
#if LH_QUOTA_FILTER_AVAILABLE
    OBSERVE(r, "prctl.no_new_privs", prctl(PR_SET_NO_NEW_PRIVS, 1UL, 0UL, 0UL, 0UL));
    if (!succeeded(r)) { fail(r, "UNSUPPORTED", "NO_NEW_PRIVS_FAILED", 3); return; }
    r->no_new_privs = true;
    OBSERVE(r, "seccomp.install", quota_filter_install(r->project.fsx_projid));
    if (!succeeded(r)) { fail(r, "UNSUPPORTED", "SYSCALL_FILTER_FAILED", 3); return; }
    r->filter_installed = true;
#endif
    r->state.qs_version = FS_QSTATV_VERSION1;
    query(r, QCMD((unsigned int)Q_XGETQSTATV, PRJQUOTA), 0, &r->state, "quotactl_fd.state.before");
    if (!succeeded(r)) { fail(r, "UNSUPPORTED", "ENFORCEMENT_QUERY_FAILED", 3); return; }
    r->state_seen = true;
    if (!enforced(&r->state)) {
        fail(r, "UNSUPPORTED", "PROJECT_ENFORCEMENT_UNPROVEN", 3); return;
    }
    query(r, QCMD((unsigned int)Q_GETQUOTA, PRJQUOTA), r->project.fsx_projid, &r->quota,
          "quotactl_fd.getquota");
    if (!succeeded(r)) { fail(r, "UNSUPPORTED", "QUOTA_QUERY_FAILED", 3); return; }
    r->quota_seen = true;
    if (!(r->quota.dqb_valid & QIF_BLIMITS)) {
        fail(r, "UNSUPPORTED", "HARD_LIMIT_FIELD_UNVERIFIED", 3); return;
    }
    if (!r->quota.dqb_bhardlimit) {
        fail(r, "REJECTED", "FINITE_HARD_LIMIT_REQUIRED", 2); return;
    }
    /* Generic Q_GETQUOTA uses 1 KiB blocks, not XFS's 512-byte Q_XGETQUOTA units. */
    if (r->quota.dqb_bhardlimit > UINT64_MAX / 1024) {
        fail(r, "REJECTED", "HARD_LIMIT_BYTE_OVERFLOW", 2); return;
    }
    r->hard_bytes = r->quota.dqb_bhardlimit * 1024;
    r->hard_bytes_valid = true;
    OBSERVE(r, "ioctl.fsgetxattr.after", ioctl(ROOT_FD, FS_IOC_FSGETXATTR, &r->project_after));
    if (!succeeded(r)) { fail(r, "IO_UNCERTAIN", "PROJECT_RECHECK_FAILED", 4); return; }
    r->project_after_seen = true;
    if (r->project_after.fsx_projid != r->project.fsx_projid ||
        r->project_after.fsx_xflags != r->project.fsx_xflags) {
        fail(r, "IO_UNCERTAIN", "PROJECT_CHANGED", 4); return;
    }
    OBSERVE(r, "fstat.after", stat_root(&r->root_after));
    if (!succeeded(r)) { fail(r, "IO_UNCERTAIN", "ROOT_RECHECK_FAILED", 4); return; }
    r->root_after_seen = true;
    if (r->root_after.st_dev != r->root.st_dev || r->root_after.st_ino != r->root.st_ino ||
        r->root_after.st_uid != r->root.st_uid || r->root_after.st_gid != r->root.st_gid ||
        r->root_after.st_mode != r->root.st_mode) {
        fail(r, "IO_UNCERTAIN", "ROOT_CHANGED", 4); return;
    }
    r->state_after.qs_version = FS_QSTATV_VERSION1;
    query(r, QCMD((unsigned int)Q_XGETQSTATV, PRJQUOTA), 0, &r->state_after, "quotactl_fd.state.after");
    if (!succeeded(r)) { fail(r, "IO_UNCERTAIN", "ENFORCEMENT_RECHECK_FAILED", 4); return; }
    r->state_after_seen = true;
    if (!enforced(&r->state_after) || r->state_after.qs_flags != r->state.qs_flags) {
        fail(r, "IO_UNCERTAIN", "ENFORCEMENT_CHANGED", 4); return;
    }
    fail(r, "OBSERVED", "QUOTA_FACTS_OBSERVED", 0);
}

static int emit(const struct report *r)
{
    char buf[OUTPUT_BYTES]; size_t used = 0;
#define APPEND(...) do { \
    int n = snprintf(buf + used, sizeof(buf) - used, __VA_ARGS__); \
    if (n < 0 || (size_t)n >= sizeof(buf) - used) return 70; \
    used += (size_t)n; \
} while (0)
    APPEND("{\"schema\":\"local-hand-quota-abi/v2\",\"status\":\"%s\",\"code\":\"%s\","
           "\"real_e3_accepted\":false,\"production_supported\":false,\"admission_proven\":false,"
           "\"quota_syscall_attempts\":%u,\"uid\":%ju,\"euid\":%ju,\"root_fd\":3,"
           "\"abi\":{\"fsxattr_bytes\":%zu,\"dqblk_bytes\":%zu,\"qstatv_bytes\":%zu},",
           r->status, r->code, r->quota_calls, (uintmax_t)getuid(), (uintmax_t)geteuid(),
           sizeof(struct fsxattr), sizeof(struct if_dqblk), sizeof(struct fs_quota_statv));
    APPEND("\"restriction\":{\"profile\":\"quota-fd-readonly/v1\",\"no_new_privs\":%s,"
           "\"filter_installed\":%s,\"project_id\":",
           r->no_new_privs ? "true" : "false", r->filter_installed ? "true" : "false");
    if (r->filter_installed) APPEND("%u", r->project.fsx_projid); else APPEND("null");
    APPEND("},");
    APPEND("\"root\":");
    if (r->root_seen) APPEND("{\"device\":%ju,\"inode\":%ju,\"uid\":%ju,\"gid\":%ju,\"mode\":%ju}",
                           (uintmax_t)r->root.st_dev, (uintmax_t)r->root.st_ino,
                           (uintmax_t)r->root.st_uid, (uintmax_t)r->root.st_gid,
                           (uintmax_t)r->root.st_mode);
    else APPEND("null");
    APPEND(",\"filesystem_magic\":");
    if (r->fs_seen) APPEND("%jd", (intmax_t)r->fs.f_type); else APPEND("null");
    APPEND(",\"project\":");
    if (r->project_seen) APPEND("{\"id\":%u,\"xflags\":%u}",r->project.fsx_projid,r->project.fsx_xflags);
    else APPEND("null");
    APPEND(",\"enforcement\":");
    if (r->state_seen) APPEND("{\"version\":%d,\"flags\":%u}",r->state.qs_version,r->state.qs_flags);
    else APPEND("null");
    APPEND(",\"quota\":");
    if (r->quota_seen) {
        APPEND("{\"valid_mask\":%u,\"hard_blocks_1024\":%" PRIu64 ",\"hard_bytes\":",
               r->quota.dqb_valid, (uint64_t)r->quota.dqb_bhardlimit);
        if (r->hard_bytes_valid) APPEND("%" PRIu64, r->hard_bytes); else APPEND("null");
        APPEND("}");
    }
    else APPEND("null");
    APPEND(",\"root_after\":");
    if (r->root_after_seen)
        APPEND("{\"device\":%ju,\"inode\":%ju,\"uid\":%ju,\"gid\":%ju,\"mode\":%ju}",
               (uintmax_t)r->root_after.st_dev, (uintmax_t)r->root_after.st_ino,
               (uintmax_t)r->root_after.st_uid, (uintmax_t)r->root_after.st_gid,
               (uintmax_t)r->root_after.st_mode);
    else APPEND("null");
    APPEND(",\"project_after\":");
    if (r->project_after_seen) APPEND("{\"id\":%u,\"xflags\":%u}",
                                    r->project_after.fsx_projid,r->project_after.fsx_xflags);
    else APPEND("null");
    APPEND(",\"enforcement_after\":");
    if (r->state_after_seen) APPEND("{\"version\":%d,\"flags\":%u}",
                                  r->state_after.qs_version,r->state_after.qs_flags);
    else APPEND("null");
    APPEND(",\"calls\":[");
    for (size_t i = 0; i < r->count; ++i)
        APPEND("%s{\"name\":\"%s\",\"rc\":%ld,\"errno\":%d}", i ? "," : "",
               r->calls[i].name, r->calls[i].rc, r->calls[i].error);
    APPEND("]}\n");
#undef APPEND
    /* No partial output is a valid receipt; caller must capture exit and full JSON. */
    return write(STDOUT_FILENO, buf, used) == (ssize_t)used ? r->exit_code : 74;
}

int main(int argc, char **argv)
{
    (void)argv;
    struct report r = {.status = "REJECTED", .code = "NO_ARGUMENTS_ALLOWED", .exit_code = 2};
    if (argc == 1) {
        inspect(&r);
        /* Close exactly once: retrying close after EINTR can close a reused fd. */
        if (r.root_seen) {
            OBSERVE(&r, "close.root", close(ROOT_FD));
            if (!succeeded(&r)) {
                /* Preserve an earlier substantive failure, including its errno. */
                if (r.exit_code == 0) fail(&r, "IO_UNCERTAIN", "ROOT_CLOSE_FAILED", 4);
            }
        }
    }
    _exit(emit(&r)); /* No libc teardown syscalls after the restrictive filter. */
}
