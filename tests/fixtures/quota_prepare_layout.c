/* Read-only native UAPI layout witness. No quota calls, mounts or privileges. */
#include <linux/dqblk_xfs.h>
#include <linux/quota.h>
#include <stddef.h>
#include <stdio.h>

#define OFFSET(type, field) printf("%zu,", offsetof(struct type, field))
#define BLOCK_FIELDS(type) \
    OFFSET(type, dqb_bhardlimit); OFFSET(type, dqb_bsoftlimit); \
    OFFSET(type, dqb_curspace); OFFSET(type, dqb_ihardlimit); \
    OFFSET(type, dqb_isoftlimit); OFFSET(type, dqb_curinodes); \
    OFFSET(type, dqb_btime); OFFSET(type, dqb_itime)

int main(void)
{
    const unsigned int one = 1;
    printf("{\"little_endian\":%s,\"scalars\":[%zu,%zu,%zu,%zu,%zu],",
           *(const unsigned char *)&one == 1 ? "true" : "false",
           sizeof(void *), sizeof(long), sizeof(int), sizeof(__u64), _Alignof(__u64));
    printf("\"dqblk\":{\"size\":%zu,\"alignment\":%zu,\"offsets\":[",
           sizeof(struct if_dqblk), _Alignof(struct if_dqblk));
    BLOCK_FIELDS(if_dqblk);
    printf("%zu]},", offsetof(struct if_dqblk, dqb_valid));
    printf("\"nextdqblk\":{\"size\":%zu,\"alignment\":%zu,\"offsets\":[",
           sizeof(struct if_nextdqblk), _Alignof(struct if_nextdqblk));
    BLOCK_FIELDS(if_nextdqblk); OFFSET(if_nextdqblk, dqb_valid);
    printf("%zu]},", offsetof(struct if_nextdqblk, dqb_id));
    printf("\"file\":{\"size\":%zu,\"alignment\":%zu,\"offsets\":[",
           sizeof(struct fs_qfilestatv), _Alignof(struct fs_qfilestatv));
    OFFSET(fs_qfilestatv, qfs_ino); OFFSET(fs_qfilestatv, qfs_nblks);
    OFFSET(fs_qfilestatv, qfs_nextents);
    printf("%zu]},", offsetof(struct fs_qfilestatv, qfs_pad));
    printf("\"state\":{\"size\":%zu,\"alignment\":%zu,\"offsets\":[",
           sizeof(struct fs_quota_statv), _Alignof(struct fs_quota_statv));
    OFFSET(fs_quota_statv, qs_version); OFFSET(fs_quota_statv, qs_pad1);
    OFFSET(fs_quota_statv, qs_flags); OFFSET(fs_quota_statv, qs_incoredqs);
    OFFSET(fs_quota_statv, qs_uquota); OFFSET(fs_quota_statv, qs_gquota);
    OFFSET(fs_quota_statv, qs_pquota); OFFSET(fs_quota_statv, qs_btimelimit);
    OFFSET(fs_quota_statv, qs_itimelimit); OFFSET(fs_quota_statv, qs_rtbtimelimit);
    OFFSET(fs_quota_statv, qs_bwarnlimit); OFFSET(fs_quota_statv, qs_iwarnlimit);
    OFFSET(fs_quota_statv, qs_rtbwarnlimit); OFFSET(fs_quota_statv, qs_pad3);
    OFFSET(fs_quota_statv, qs_pad4);
    printf("%zu]},", offsetof(struct fs_quota_statv, qs_pad2));
    printf("\"constants\":[%u,%u,%u,%u,%u,%u,%u,%u,%u]}\n",
           (unsigned)Q_GETQUOTA, (unsigned)Q_GETNEXTQUOTA, (unsigned)Q_SETQUOTA,
           (unsigned)Q_XGETQSTATV, (unsigned)PRJQUOTA, (unsigned)QIF_DQBLKSIZE,
           (unsigned)FS_QSTATV_VERSION1,
           (unsigned)(FS_QUOTA_PDQ_ACCT | FS_QUOTA_PDQ_ENFD), (unsigned)QIF_ALL);
    return 0;
}
