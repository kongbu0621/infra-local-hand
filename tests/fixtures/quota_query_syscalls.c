/* Link-time syscall simulation ONLY. Never built into the real admin binary. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/dqblk_xfs.h>
#include <linux/fs.h>
#include <linux/magic.h>
#include <linux/quota.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/vfs.h>
#include <unistd.h>

static unsigned stats, projects, states;
static int is(const char *name)
{
    const char *value = getenv("LH_Q1_TEST_CASE");
    return value && strcmp(value, name) == 0;
}
static int error(int number) { errno = number; return -1; }
static void fixed_fd(int fd) { if (fd != 3) _exit(99); }

int __wrap_fstat(int fd, struct stat *value)
{
    fixed_fd(fd); stats++;
    if (is("stat_error") || (stats == 2 && is("recheck_error"))) return error(EACCES);
    memset(value, 0, sizeof(*value));
    value->st_dev = 41; value->st_ino = 52; value->st_uid = 1501; value->st_gid = 1501;
    value->st_mode = (is("regular_file") ? S_IFREG : S_IFDIR) | 0700;
    if (stats == 2 && is("root_changed")) value->st_ino++;
    if (stats == 2 && is("uid_changed")) value->st_uid++;
    return 0;
}

int __wrap_fcntl(int fd, int command, ...)
{
    fixed_fd(fd); if (command != F_GETFL) _exit(99);
    if (is("flags_error")) return error(EBADF);
    if (is("writable_fd")) return O_RDWR;
    if (is("opath_fd")) return O_PATH;
    return O_RDONLY | O_DIRECTORY;
}

int __wrap_fstatfs(int fd, struct statfs *value)
{
    fixed_fd(fd);
    if (is("fs_error")) return error(EIO);
    memset(value, 0, sizeof(*value));
    value->f_type = is("xfs") ? XFS_SUPER_MAGIC : EXT4_SUPER_MAGIC;
    if (is("unsupported_fs")) value->f_type = TMPFS_MAGIC;
    return 0;
}

int __wrap_ioctl(int fd, unsigned long command, ...)
{
    fixed_fd(fd); if (command != FS_IOC_FSGETXATTR) _exit(99);
    projects++;
    if (is("project_error") || (projects == 2 && is("project_recheck_error"))) return error(ENOTTY);
    va_list args; va_start(args, command);
    struct fsxattr *value = va_arg(args, struct fsxattr *);
    va_end(args); memset(value, 0, sizeof(*value));
    value->fsx_projid = is("zero_project") ? 0 : 73;
    value->fsx_xflags = is("no_inherit") ? 0 : FS_XFLAG_PROJINHERIT;
    if (projects == 2 && is("project_changed")) value->fsx_projid++;
    if (projects == 2 && is("inherit_changed")) value->fsx_xflags = 0;
    return 0;
}

long __wrap_syscall(long number, ...)
{
#ifndef SYS_quotactl_fd
    (void)number; _exit(99);
#else
    if (number != SYS_quotactl_fd) _exit(99);
    va_list args; va_start(args, number);
    unsigned int fd = va_arg(args, unsigned int);
    unsigned int command = va_arg(args, unsigned int);
    unsigned int id = va_arg(args, unsigned int);
    void *out = va_arg(args, void *);
    va_end(args); fixed_fd((int)fd);
    if (command == QCMD((unsigned int)Q_XGETQSTATV, PRJQUOTA)) {
        if (id != 0) _exit(99);
        states++;
        struct fs_quota_statv *value = out;
        if (value->qs_version != FS_QSTATV_VERSION1) _exit(99);
        if (is("state_error") || (states == 2 && is("state_recheck_error"))) return error(ENOSYS);
        memset(value, 0, sizeof(*value)); value->qs_version = FS_QSTATV_VERSION1;
        value->qs_flags = FS_QUOTA_PDQ_ACCT | FS_QUOTA_PDQ_ENFD;
        if (is("no_enforcement") || (states == 2 && is("enforcement_changed")))
            value->qs_flags = FS_QUOTA_PDQ_ACCT;
        if (is("wrong_state_version")) value->qs_version = 2;
        return 0;
    }
    if (command != QCMD((unsigned int)Q_GETQUOTA, PRJQUOTA) || id != 73) _exit(99);
    if (is("quota_eperm") || is("quota_eperm_close_error")) return error(EPERM);
    if (is("quota_ero_fs")) return error(EROFS);
    if (is("quota_enosys")) return error(ENOSYS);
    struct if_dqblk *value = out; memset(value, 0, sizeof(*value));
    value->dqb_valid = is("invalid_limits") ? QIF_SPACE : QIF_ALL;
    value->dqb_bhardlimit = is("unlimited") ? 0 : 123;
    if (is("overflow")) value->dqb_bhardlimit = UINT64_MAX / 1024 + 1;
    if (is("boundary")) value->dqb_bhardlimit = UINT64_MAX / 1024;
    if (is("stale_errno")) errno = EINTR;  /* Success must preserve rc independently. */
    return 0;
#endif
}

int __wrap_close(int fd)
{
    fixed_fd(fd);
    return (is("close_error") || is("quota_eperm_close_error")) ? error(EINTR) : 0;
}
