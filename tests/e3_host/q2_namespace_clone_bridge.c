#define _GNU_SOURCE 1

/*
 * Test-only native boundary for LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1.
 *
 * This is deliberately not installed by setup.py.  It provides the only
 * clone3 entry used by the isolated fixture and the final, non-returning
 * receipt tail.  There is no libc fork path, numeric-pid migration, or syscall-number
 * fallback.  Callers must independently admit the exact compiler, CPython
 * ABI, loader, cgroup fds, identities, rlimits and transport before use.
 */

#include <Python.h>

#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <linux/capability.h>
#include <linux/magic.h>
#include <linux/sched.h>
#include <sched.h>
#include <signal.h>
#include <poll.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <sys/signalfd.h>
#include <sys/time.h>
#include <sys/wait.h>
#include <linux/wait.h>
#include <sys/fsuid.h>
#include <sys/personality.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/vfs.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#ifndef SYS_clone3
#error "clone3 syscall number is required; no runtime-number fallback is permitted"
#endif
#ifndef SYS_close_range
#error "close_range syscall number is required; no close-loop fallback is permitted"
#endif
#ifndef CLONE_INTO_CGROUP
#error "CLONE_INTO_CGROUP headers are required"
#endif
#ifndef CLONE_PIDFD
#error "CLONE_PIDFD headers are required"
#endif
#ifndef SYS_pidfd_send_signal
#error "pidfd_send_signal syscall number is required; no numeric-pid fallback is permitted"
#endif
#if !defined(__x86_64__) || __SIZEOF_POINTER__ != 8
#error "the reviewed bridge ABI is Linux x86_64 LP64 only"
#endif

#define Q2_BRIDGE_ABI_VERSION 1
#define Q2_CLONE_ARGS_SIZE 88U
#define Q2_MAX_ARGV 16U
#define Q2_MAX_ENVP 2U
#define Q2_MAX_GROUPS 32U
#define Q2_RECEIPT_SIZE 224U
#define Q2_RECEIPT_MAGIC_OFFSET 0U
#define Q2_RECEIPT_VERSION_OFFSET 8U
#define Q2_RECEIPT_PROCESS_OFFSET 16U
#define Q2_RECEIPT_BOOTTIME_OFFSET 24U
#define Q2_RECEIPT_MONOTONIC_OFFSET 32U
#define Q2_RECEIPT_REALTIME_OFFSET 40U
#define Q2_RECEIPT_COUNTER_OFFSET 48U
#define Q2_RECEIPT_PREVIOUS_DIGEST_OFFSET 56U
#define Q2_RECEIPT_H_DIGEST_OFFSET 88U
#define Q2_RECEIPT_CLEANUP_FINAL_DIGEST_OFFSET 120U
#define Q2_RECEIPT_ACK_CAPTURE_HEAD_OFFSET 152U
#define Q2_RECEIPT_RESERVED_OFFSET 184U
#define Q2_RECEIPT_HASH_OFFSET 192U
#define Q2_RECEIPT_DIGEST_SIZE 32U
#define Q2_TAIL_UNARMED 0
#define Q2_TAIL_SETUP 1
#define Q2_TAIL_ARMED 2
#define Q2_TAIL_FAILED 3
#define Q2_RELEASE_BYTE 1U
#define Q2_MAX_GATE_WAIT_NS 840000000000ULL
#define Q2_KERNEL_O_LARGEFILE 0100000

_Static_assert(sizeof(struct clone_args) == Q2_CLONE_ARGS_SIZE,
               "Linux x86_64 LP64 clone_args must be exactly 88 bytes");
_Static_assert(sizeof(uint64_t) == 8U, "64-bit receipt words required");
_Static_assert(Q2_RECEIPT_SIZE <= 512U, "receipt must fit the approved single-write bound");
_Static_assert(Q2_RECEIPT_HASH_OFFSET + Q2_RECEIPT_DIGEST_SIZE == Q2_RECEIPT_SIZE,
               "receipt hash must terminate the fixed layout");
_Static_assert(sizeof(sigset_t) == 16U * sizeof(unsigned long),
               "reviewed x86_64 sigset_t must contain exactly 16 native words");
_Static_assert(_Alignof(sigset_t) == _Alignof(unsigned long),
               "reviewed x86_64 sigset_t alignment must match native words");

typedef union {
    sigset_t signals;
    unsigned long words[16];
} q2_sigset_view;

typedef union {
    unsigned char bytes[1024];
    uint64_t words[128];
} q2_fdinfo_snapshot;

typedef struct {
    int cgroup_fd;
    int gate_fd;
    uint64_t gate_deadline_boottime_ns;
    int role_supervisor;
    pid_t expected_parent;
    uid_t uid;
    gid_t gid;
    gid_t groups[Q2_MAX_GROUPS];
    size_t group_count;
    int affinity_cpu;
    struct rlimit limits[RLIM_NLIMITS];
    char *executable;
    char *argv[Q2_MAX_ARGV + 1U];
    char *envp[Q2_MAX_ENVP + 1U];
} child_spec;

typedef struct {
    volatile sig_atomic_t state;
    int fd0;
    int fd1;
    int fd2;
    int deadline_signal;
    int signalfd_fd;
    struct stat fd_identity[3];
    struct stat signalfd_identity;
    q2_fdinfo_snapshot signalfd_fdinfo;
    size_t signalfd_fdinfo_size;
    uint64_t last_process_ns;
    uint64_t process_accounted_ns;
    uint64_t carrier_accounted_ns;
    uint64_t guardian_accounted_ns;
    uint64_t guardian_usage_ns;
    uint64_t sample_round_ns;
    uint64_t tail_cpu_max_ns;
    uint64_t tail_wall_max_ns;
    uint64_t boot_deadline_ns;
    uint64_t mono_deadline_ns;
    uint64_t realtime_deadline_ns;
    uint64_t realtime_minus_boot_ns;
    uint64_t realtime_minus_mono_ns;
    uint64_t clock_step_tolerance_ns;
    uint64_t fatal_timer_min_remaining_ns;
    timer_t fatal_timer_id;
    int stop_latched;
    unsigned char receipt[Q2_RECEIPT_SIZE];
} cleanup_tail_plan;

static cleanup_tail_plan tail_plan;
static q2_fdinfo_snapshot tail_fdinfo_scratch;
static const struct sigaction q2_default_signal_action = {.sa_handler = SIG_DFL};
static PyObject *BridgeError;

static uint64_t
timespec_ns(const struct timespec *value)
{
    if (value->tv_sec < 0 || value->tv_nsec < 0 || value->tv_nsec >= 1000000000L) {
        return UINT64_MAX;
    }
    if ((uint64_t)value->tv_sec > UINT64_MAX / 1000000000ULL) {
        return UINT64_MAX;
    }
    return (uint64_t)value->tv_sec * 1000000000ULL + (uint64_t)value->tv_nsec;
}

static int
add_u64(uint64_t left, uint64_t right, uint64_t *out)
{
    if (UINT64_MAX - left < right) {
        return -1;
    }
    *out = left + right;
    return 0;
}

static uint64_t
u64_distance(uint64_t left, uint64_t right)
{
    return left >= right ? left - right : right - left;
}

static int
same_fd_identity(const struct stat *left, const struct stat *right)
{
    return left->st_dev == right->st_dev && left->st_ino == right->st_ino &&
           left->st_mode == right->st_mode && left->st_rdev == right->st_rdev;
}

static int
validate_gate_fd(int fd)
{
    struct stat identity;
    int status_flags = fcntl(fd, F_GETFL);
    int descriptor_flags = fcntl(fd, F_GETFD);
    if (status_flags < 0 || descriptor_flags < 0 || fstat(fd, &identity) != 0) return -1;
    if (!S_ISFIFO(identity.st_mode) || status_flags != (O_RDONLY | O_NONBLOCK) ||
        descriptor_flags != FD_CLOEXEC) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

static int
remaining_boottime(uint64_t deadline_ns, struct timespec *timeout)
{
    struct timespec now;
    uint64_t now_ns;
    uint64_t remaining;
    if (clock_gettime(CLOCK_BOOTTIME, &now) != 0) return -1;
    now_ns = timespec_ns(&now);
    if (now_ns == UINT64_MAX || now_ns >= deadline_ns) {
        errno = ETIMEDOUT;
        return -1;
    }
    remaining = deadline_ns - now_ns;
    timeout->tv_sec = (time_t)(remaining / 1000000000ULL);
    timeout->tv_nsec = (long)(remaining % 1000000000ULL);
    return 0;
}

static int
wait_exact_release(const child_spec *spec)
{
    struct pollfd watched = {.fd = spec->gate_fd, .events = POLLIN | POLLHUP};
    struct timespec timeout;
    unsigned char release;
    unsigned char extra;
    ssize_t count;
    int ready;
    int have_release = 0;
    for (;;) {
        if (getppid() != spec->expected_parent ||
            remaining_boottime(spec->gate_deadline_boottime_ns, &timeout) != 0) return -1;
        ready = ppoll(&watched, 1U, &timeout, NULL);
        if (ready < 0 && errno == EINTR) continue;
        if (ready <= 0 || (watched.revents & (POLLERR | POLLNVAL)) != 0) return -1;
        if (!have_release) {
            count = read(spec->gate_fd, &release, 1U);
            if (count < 0 && errno == EAGAIN) continue;
            if (count != 1 || release != Q2_RELEASE_BYTE) return -1;
            have_release = 1;
        }
        count = read(spec->gate_fd, &extra, 1U);
        if (count == 0) return 0;
        if (count > 0 || (count < 0 && errno != EAGAIN)) return -1;
        watched.revents = 0;
    }
}

static uint32_t
be32_load(const unsigned char *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static void
be32_store(unsigned char *p, uint32_t value)
{
    p[0] = (unsigned char)(value >> 24);
    p[1] = (unsigned char)(value >> 16);
    p[2] = (unsigned char)(value >> 8);
    p[3] = (unsigned char)value;
}

static void
le64_store(unsigned char *p, uint64_t value)
{
    p[0] = (unsigned char)value;
    p[1] = (unsigned char)(value >> 8);
    p[2] = (unsigned char)(value >> 16);
    p[3] = (unsigned char)(value >> 24);
    p[4] = (unsigned char)(value >> 32);
    p[5] = (unsigned char)(value >> 40);
    p[6] = (unsigned char)(value >> 48);
    p[7] = (unsigned char)(value >> 56);
}

static uint64_t
le64_load(const unsigned char *p)
{
    return (uint64_t)p[0] | ((uint64_t)p[1] << 8) | ((uint64_t)p[2] << 16) |
           ((uint64_t)p[3] << 24) | ((uint64_t)p[4] << 32) |
           ((uint64_t)p[5] << 40) | ((uint64_t)p[6] << 48) |
           ((uint64_t)p[7] << 56);
}

#define ROR32(x, n) (((x) >> (n)) | ((x) << (32U - (n))))
#define BSIG0(x) (ROR32((x), 2U) ^ ROR32((x), 13U) ^ ROR32((x), 22U))
#define BSIG1(x) (ROR32((x), 6U) ^ ROR32((x), 11U) ^ ROR32((x), 25U))
#define SSIG0(x) (ROR32((x), 7U) ^ ROR32((x), 18U) ^ ((x) >> 3U))
#define SSIG1(x) (ROR32((x), 17U) ^ ROR32((x), 19U) ^ ((x) >> 10U))
#define CH(x, y, z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EXPAND_WORD(i) w[(i)] = SSIG1(w[(i)-2]) + w[(i)-7] + SSIG0(w[(i)-15]) + w[(i)-16]
#define SHA_ROUND(i, k) { \
    uint32_t t1 = v[7] + BSIG1(v[4]) + CH(v[4], v[5], v[6]) + (k) + w[(i)]; \
    uint32_t t2 = BSIG0(v[0]) + MAJ(v[0], v[1], v[2]); \
    v[7] = v[6]; v[6] = v[5]; v[5] = v[4]; v[4] = v[3] + t1; \
    v[3] = v[2]; v[2] = v[1]; v[1] = v[0]; v[0] = t1 + t2; \
}

/* SHA-256 of exactly 192 bytes.  Deliberately fully unrolled: the post-gate
 * receipt path has no allocation and no data-dependent or fixed-count loop. */
static void
sha256_fixed192(const unsigned char input[Q2_RECEIPT_HASH_OFFSET],
                unsigned char output[Q2_RECEIPT_DIGEST_SIZE])
{
    uint32_t h[8] = {0x6a09e667U,0xbb67ae85U,0x3c6ef372U,0xa54ff53aU,
                     0x510e527fU,0x9b05688cU,0x1f83d9abU,0x5be0cd19U};
    uint32_t v[8];
    uint32_t w[64];
#define LOAD_STATE() { v[0]=h[0];v[1]=h[1];v[2]=h[2];v[3]=h[3];v[4]=h[4];v[5]=h[5];v[6]=h[6];v[7]=h[7]; }
#define ADD_STATE() { h[0]+=v[0];h[1]+=v[1];h[2]+=v[2];h[3]+=v[3];h[4]+=v[4];h[5]+=v[5];h[6]+=v[6];h[7]+=v[7]; }
#define EXPAND_ALL() { \
    EXPAND_WORD(16);EXPAND_WORD(17);EXPAND_WORD(18);EXPAND_WORD(19); \
    EXPAND_WORD(20);EXPAND_WORD(21);EXPAND_WORD(22);EXPAND_WORD(23); \
    EXPAND_WORD(24);EXPAND_WORD(25);EXPAND_WORD(26);EXPAND_WORD(27); \
    EXPAND_WORD(28);EXPAND_WORD(29);EXPAND_WORD(30);EXPAND_WORD(31); \
    EXPAND_WORD(32);EXPAND_WORD(33);EXPAND_WORD(34);EXPAND_WORD(35); \
    EXPAND_WORD(36);EXPAND_WORD(37);EXPAND_WORD(38);EXPAND_WORD(39); \
    EXPAND_WORD(40);EXPAND_WORD(41);EXPAND_WORD(42);EXPAND_WORD(43); \
    EXPAND_WORD(44);EXPAND_WORD(45);EXPAND_WORD(46);EXPAND_WORD(47); \
    EXPAND_WORD(48);EXPAND_WORD(49);EXPAND_WORD(50);EXPAND_WORD(51); \
    EXPAND_WORD(52);EXPAND_WORD(53);EXPAND_WORD(54);EXPAND_WORD(55); \
    EXPAND_WORD(56);EXPAND_WORD(57);EXPAND_WORD(58);EXPAND_WORD(59); \
    EXPAND_WORD(60);EXPAND_WORD(61);EXPAND_WORD(62);EXPAND_WORD(63); \
}
#define ALL_ROUNDS() { \
    SHA_ROUND(0,0x428a2f98U);SHA_ROUND(1,0x71374491U);SHA_ROUND(2,0xb5c0fbcfU);SHA_ROUND(3,0xe9b5dba5U); \
    SHA_ROUND(4,0x3956c25bU);SHA_ROUND(5,0x59f111f1U);SHA_ROUND(6,0x923f82a4U);SHA_ROUND(7,0xab1c5ed5U); \
    SHA_ROUND(8,0xd807aa98U);SHA_ROUND(9,0x12835b01U);SHA_ROUND(10,0x243185beU);SHA_ROUND(11,0x550c7dc3U); \
    SHA_ROUND(12,0x72be5d74U);SHA_ROUND(13,0x80deb1feU);SHA_ROUND(14,0x9bdc06a7U);SHA_ROUND(15,0xc19bf174U); \
    SHA_ROUND(16,0xe49b69c1U);SHA_ROUND(17,0xefbe4786U);SHA_ROUND(18,0x0fc19dc6U);SHA_ROUND(19,0x240ca1ccU); \
    SHA_ROUND(20,0x2de92c6fU);SHA_ROUND(21,0x4a7484aaU);SHA_ROUND(22,0x5cb0a9dcU);SHA_ROUND(23,0x76f988daU); \
    SHA_ROUND(24,0x983e5152U);SHA_ROUND(25,0xa831c66dU);SHA_ROUND(26,0xb00327c8U);SHA_ROUND(27,0xbf597fc7U); \
    SHA_ROUND(28,0xc6e00bf3U);SHA_ROUND(29,0xd5a79147U);SHA_ROUND(30,0x06ca6351U);SHA_ROUND(31,0x14292967U); \
    SHA_ROUND(32,0x27b70a85U);SHA_ROUND(33,0x2e1b2138U);SHA_ROUND(34,0x4d2c6dfcU);SHA_ROUND(35,0x53380d13U); \
    SHA_ROUND(36,0x650a7354U);SHA_ROUND(37,0x766a0abbU);SHA_ROUND(38,0x81c2c92eU);SHA_ROUND(39,0x92722c85U); \
    SHA_ROUND(40,0xa2bfe8a1U);SHA_ROUND(41,0xa81a664bU);SHA_ROUND(42,0xc24b8b70U);SHA_ROUND(43,0xc76c51a3U); \
    SHA_ROUND(44,0xd192e819U);SHA_ROUND(45,0xd6990624U);SHA_ROUND(46,0xf40e3585U);SHA_ROUND(47,0x106aa070U); \
    SHA_ROUND(48,0x19a4c116U);SHA_ROUND(49,0x1e376c08U);SHA_ROUND(50,0x2748774cU);SHA_ROUND(51,0x34b0bcb5U); \
    SHA_ROUND(52,0x391c0cb3U);SHA_ROUND(53,0x4ed8aa4aU);SHA_ROUND(54,0x5b9cca4fU);SHA_ROUND(55,0x682e6ff3U); \
    SHA_ROUND(56,0x748f82eeU);SHA_ROUND(57,0x78a5636fU);SHA_ROUND(58,0x84c87814U);SHA_ROUND(59,0x8cc70208U); \
    SHA_ROUND(60,0x90befffaU);SHA_ROUND(61,0xa4506cebU);SHA_ROUND(62,0xbef9a3f7U);SHA_ROUND(63,0xc67178f2U); \
}

#define LOAD_INPUT_BLOCK(offset) { \
    w[0]=be32_load(input+(offset)+0);w[1]=be32_load(input+(offset)+4); \
    w[2]=be32_load(input+(offset)+8);w[3]=be32_load(input+(offset)+12); \
    w[4]=be32_load(input+(offset)+16);w[5]=be32_load(input+(offset)+20); \
    w[6]=be32_load(input+(offset)+24);w[7]=be32_load(input+(offset)+28); \
    w[8]=be32_load(input+(offset)+32);w[9]=be32_load(input+(offset)+36); \
    w[10]=be32_load(input+(offset)+40);w[11]=be32_load(input+(offset)+44); \
    w[12]=be32_load(input+(offset)+48);w[13]=be32_load(input+(offset)+52); \
    w[14]=be32_load(input+(offset)+56);w[15]=be32_load(input+(offset)+60); \
}
    LOAD_INPUT_BLOCK(0);
    EXPAND_ALL(); LOAD_STATE(); ALL_ROUNDS(); ADD_STATE();
    LOAD_INPUT_BLOCK(64);
    EXPAND_ALL(); LOAD_STATE(); ALL_ROUNDS(); ADD_STATE();
    LOAD_INPUT_BLOCK(128);
    EXPAND_ALL(); LOAD_STATE(); ALL_ROUNDS(); ADD_STATE();

    w[0]=0x80000000U;w[1]=0U;w[2]=0U;w[3]=0U;
    w[4]=0U;w[5]=0U;w[6]=0U;w[7]=0U;
    w[8]=0U;w[9]=0U;w[10]=0U;w[11]=0U;
    w[12]=0U;w[13]=0U;w[14]=0U;w[15]=1536U;
    EXPAND_ALL(); LOAD_STATE(); ALL_ROUNDS(); ADD_STATE();

    be32_store(output+0,h[0]);be32_store(output+4,h[1]);
    be32_store(output+8,h[2]);be32_store(output+12,h[3]);
    be32_store(output+16,h[4]);be32_store(output+20,h[5]);
    be32_store(output+24,h[6]);be32_store(output+28,h[7]);
#undef LOAD_INPUT_BLOCK
#undef ALL_ROUNDS
#undef EXPAND_ALL
#undef ADD_STATE
#undef LOAD_STATE
}

static void
free_child_spec(child_spec *spec)
{
    size_t i;
    if (spec == NULL) {
        return;
    }
    PyMem_Free(spec->executable);
    for (i = 0; i < Q2_MAX_ARGV && spec->argv[i] != NULL; ++i) {
        PyMem_Free(spec->argv[i]);
    }
    for (i = 0; i < Q2_MAX_ENVP && spec->envp[i] != NULL; ++i) {
        PyMem_Free(spec->envp[i]);
    }
    PyMem_Free(spec);
}

static char *
copy_nul_free_bytes(PyObject *value, size_t maximum, const char *name)
{
    char *raw;
    Py_ssize_t length;
    char *copy;
    if (!PyBytes_Check(value)) {
        PyErr_Format(BridgeError, "%s must be bytes", name);
        return NULL;
    }
    if (PyBytes_AsStringAndSize(value, &raw, &length) < 0) {
        return NULL;
    }
    if (length < 1 || (size_t)length > maximum || memchr(raw, '\0', (size_t)length) != NULL) {
        PyErr_Format(BridgeError, "%s has invalid length or NUL", name);
        return NULL;
    }
    copy = PyMem_Malloc((size_t)length + 1U);
    if (copy == NULL) {
        PyErr_NoMemory();
        return NULL;
    }
    memcpy(copy, raw, (size_t)length);
    copy[length] = '\0';
    return copy;
}

static int
parse_string_vector(PyObject *value, char **out, size_t maximum_items,
                    size_t maximum_item, const char *name)
{
    Py_ssize_t count;
    Py_ssize_t i;
    if (!PyTuple_Check(value)) {
        PyErr_Format(BridgeError, "%s must be a tuple", name);
        return -1;
    }
    count = PyTuple_GET_SIZE(value);
    if (count < 1 || (size_t)count > maximum_items) {
        PyErr_Format(BridgeError, "%s count outside fixed bound", name);
        return -1;
    }
    for (i = 0; i < count; ++i) {
        out[i] = copy_nul_free_bytes(PyTuple_GET_ITEM(value, i), maximum_item, name);
        if (out[i] == NULL) {
            return -1;
        }
    }
    out[count] = NULL;
    return 0;
}

static int
parse_groups(PyObject *value, child_spec *spec)
{
    Py_ssize_t count;
    Py_ssize_t i;
    if (!PyTuple_Check(value)) {
        PyErr_SetString(BridgeError, "groups must be a tuple");
        return -1;
    }
    count = PyTuple_GET_SIZE(value);
    if (count < 0 || (size_t)count > Q2_MAX_GROUPS) {
        PyErr_SetString(BridgeError, "groups exceeds fixed bound");
        return -1;
    }
    for (i = 0; i < count; ++i) {
        unsigned long item = PyLong_AsUnsignedLong(PyTuple_GET_ITEM(value, i));
        if (item == (unsigned long)-1 && PyErr_Occurred()) {
            return -1;
        }
        if (item >= UINT32_MAX) {
            PyErr_SetString(BridgeError, "group id outside uint32");
            return -1;
        }
        spec->groups[i] = (gid_t)item;
        if (i > 0 && spec->groups[i] < spec->groups[i - 1]) {
            PyErr_SetString(BridgeError, "groups must be nondecreasing");
            return -1;
        }
    }
    spec->group_count = (size_t)count;
    return 0;
}

static int
parse_rlimits(PyObject *value, child_spec *spec)
{
    Py_ssize_t i;
    if (!PyTuple_Check(value) || PyTuple_GET_SIZE(value) != RLIM_NLIMITS) {
        PyErr_Format(BridgeError, "rlimits must contain exactly %d pairs", RLIM_NLIMITS);
        return -1;
    }
    for (i = 0; i < RLIM_NLIMITS; ++i) {
        PyObject *pair = PyTuple_GET_ITEM(value, i);
        unsigned long long soft;
        unsigned long long hard;
        if (!PyTuple_Check(pair) || PyTuple_GET_SIZE(pair) != 2) {
            PyErr_SetString(BridgeError, "each rlimit must be a pair");
            return -1;
        }
        soft = PyLong_AsUnsignedLongLong(PyTuple_GET_ITEM(pair, 0));
        if (soft == (unsigned long long)-1 && PyErr_Occurred()) return -1;
        hard = PyLong_AsUnsignedLongLong(PyTuple_GET_ITEM(pair, 1));
        if (hard == (unsigned long long)-1 && PyErr_Occurred()) return -1;
        if (soft > hard) {
            PyErr_SetString(BridgeError, "rlimit soft exceeds hard");
            return -1;
        }
        spec->limits[i].rlim_cur = (rlim_t)soft;
        spec->limits[i].rlim_max = (rlim_t)hard;
    }
    return 0;
}

static int
validate_exact_env(char **envp)
{
    return envp[0] != NULL && envp[1] != NULL && envp[2] == NULL &&
           strcmp(envp[0], "LANG=C") == 0 && strcmp(envp[1], "LC_ALL=C") == 0;
}

static int
reset_child_signals(void)
{
    struct sigaction action;
    struct sigaction observed;
    sigset_t blocked;
    sigset_t empty;
    sigset_t pending;
    sigset_t observed_mask;
    int signal_number;
    memset(&action, 0, sizeof(action));
    action.sa_handler = SIG_DFL;
    if (sigemptyset(&action.sa_mask) != 0 || sigfillset(&blocked) != 0 ||
        sigemptyset(&empty) != 0 || sigprocmask(SIG_BLOCK, &blocked, NULL) != 0) {
        return -1;
    }
    for (signal_number = 1; signal_number < NSIG; ++signal_number) {
        if (signal_number != SIGKILL && signal_number != SIGSTOP) {
            if (sigaction(signal_number, &action, NULL) != 0) {
                if (errno == EINVAL) continue;
                return -1;
            }
            if (sigaction(signal_number, NULL, &observed) != 0) return -1;
            if (observed.sa_handler != SIG_DFL || !sigisemptyset(&observed.sa_mask)) {
                errno = EINVAL;
                return -1;
            }
        }
    }
    if (sigpending(&pending) != 0 || !sigisemptyset(&pending)) {
        errno = EINVAL;
        return -1;
    }
    if (sigprocmask(SIG_SETMASK, &empty, NULL) != 0 ||
        sigprocmask(SIG_SETMASK, NULL, &observed_mask) != 0 ||
        !sigisemptyset(&observed_mask)) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

static int
apply_rlimits(const child_spec *spec)
{
    struct rlimit before[RLIM_NLIMITS];
    struct rlimit observed;
    int resource;
    for (resource = 0; resource < RLIM_NLIMITS; ++resource) {
        if (getrlimit(resource, &before[resource]) != 0) return -1;
    }
    if (spec->role_supervisor) {
        for (resource = 0; resource < RLIM_NLIMITS; ++resource) {
            int raise_soft = resource == RLIMIT_CPU || resource == RLIMIT_AS ||
                             resource == RLIMIT_DATA || resource == RLIMIT_NOFILE;
            if (spec->limits[resource].rlim_max != before[resource].rlim_max ||
                (raise_soft && spec->limits[resource].rlim_cur != before[resource].rlim_max) ||
                (!raise_soft && (spec->limits[resource].rlim_cur != before[resource].rlim_cur ||
                                 spec->limits[resource].rlim_max != before[resource].rlim_max))) {
                errno = EINVAL;
                return -1;
            }
        }
    }
    for (resource = 0; resource < RLIM_NLIMITS; ++resource) {
        if (setrlimit(resource, &spec->limits[resource]) != 0) {
            return -1;
        }
        if (getrlimit(resource, &observed) != 0 ||
            observed.rlim_cur != spec->limits[resource].rlim_cur ||
            observed.rlim_max != spec->limits[resource].rlim_max) {
            errno = EINVAL;
            return -1;
        }
    }
    return 0;
}

static int
apply_affinity(int cpu)
{
    cpu_set_t set;
    if (cpu < 0 || cpu >= CPU_SETSIZE) {
        errno = EINVAL;
        return -1;
    }
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);
    return sched_setaffinity(0, sizeof(set), &set);
}

static int
clear_ambient_keepcaps_and_bounding(void)
{
    int capability;
    if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0L, 0L, 0L) != 0 ||
        prctl(PR_SET_KEEPCAPS, 0L, 0L, 0L, 0L) != 0 ||
        prctl(PR_GET_KEEPCAPS, 0L, 0L, 0L, 0L) != 0) return -1;
    for (capability = 0; capability <= CAP_LAST_CAP; ++capability) {
        if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_IS_SET, capability, 0L, 0L) != 0 ||
            prctl(PR_CAPBSET_DROP, capability, 0L, 0L, 0L) != 0 ||
            prctl(PR_CAPBSET_READ, capability, 0L, 0L, 0L) != 0) return -1;
    }
    errno = 0;
    if (prctl(PR_CAPBSET_READ, CAP_LAST_CAP + 1, 0L, 0L, 0L) != -1 || errno != EINVAL) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

static int
clear_capability_sets(void)
{
    struct __user_cap_header_struct header;
    struct __user_cap_data_struct data[2];
    memset(&header, 0, sizeof(header));
    memset(data, 0, sizeof(data));
    header.version = _LINUX_CAPABILITY_VERSION_3;
    header.pid = 0;
    if (syscall(SYS_capset, &header, data) != 0 || syscall(SYS_capget, &header, data) != 0) return -1;
    if (data[0].effective != 0 || data[0].permitted != 0 || data[0].inheritable != 0 ||
        data[1].effective != 0 || data[1].permitted != 0 || data[1].inheritable != 0) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

static int
set_and_check_fsids(uid_t uid, gid_t gid)
{
    (void)setfsuid(uid);
    if (setfsuid((uid_t)-1) != (int)uid) return -1;
    (void)setfsgid(gid);
    if (setfsgid((gid_t)-1) != (int)gid) return -1;
    return 0;
}

static int
groups_match_spec(const child_spec *spec)
{
    gid_t groups[Q2_MAX_GROUPS];
    int count;
    size_t index;
    count = getgroups((int)Q2_MAX_GROUPS, groups);
    if (count < 0 || (size_t)count != spec->group_count) return 0;
    for (index = 0; index < spec->group_count; ++index) {
        if (groups[index] != spec->groups[index]) return 0;
    }
    return 1;
}

static int
current_root_identity_matches_spec(const child_spec *spec)
{
    uid_t real_uid, effective_uid, saved_uid;
    gid_t real_gid, effective_gid, saved_gid;
    return spec->uid == 0 && spec->gid == 0 &&
           getresuid(&real_uid, &effective_uid, &saved_uid) == 0 &&
           getresgid(&real_gid, &effective_gid, &saved_gid) == 0 &&
           real_uid == 0 && effective_uid == 0 && saved_uid == 0 &&
           real_gid == 0 && effective_gid == 0 && saved_gid == 0 &&
           groups_match_spec(spec);
}

static int
case_identity_is_ordinary(const child_spec *spec)
{
    size_t index;
    if (spec->uid == 0 || spec->gid == 0) return 0;
    for (index = 0; index < spec->group_count; ++index) {
        if (spec->groups[index] == 0) return 0;
    }
    return 1;
}

static int
verify_child_identity(const child_spec *spec)
{
    uid_t real_uid, effective_uid, saved_uid;
    gid_t real_gid, effective_gid, saved_gid;
    int death_signal = 0;
    if (getresuid(&real_uid, &effective_uid, &saved_uid) != 0 ||
        getresgid(&real_gid, &effective_gid, &saved_gid) != 0 ||
        real_uid != spec->uid || effective_uid != spec->uid || saved_uid != spec->uid ||
        real_gid != spec->gid || effective_gid != spec->gid || saved_gid != spec->gid) return -1;
    if (!groups_match_spec(spec)) return -1;
    if (prctl(PR_GET_NO_NEW_PRIVS, 0L, 0L, 0L, 0L) != 1 ||
        prctl(PR_GET_PDEATHSIG, &death_signal, 0L, 0L, 0L) != 0 || death_signal != SIGKILL ||
        getppid() != spec->expected_parent || prctl(PR_GET_DUMPABLE, 0L, 0L, 0L, 0L) != 1) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

static int
verify_supervisor_identity(const child_spec *spec)
{
    int death_signal = 0;
    if (!current_root_identity_matches_spec(spec) ||
        setfsuid((uid_t)-1) != 0 || setfsgid((gid_t)-1) != 0 ||
        prctl(PR_GET_NO_NEW_PRIVS, 0L, 0L, 0L, 0L) != 0 ||
        prctl(PR_GET_PDEATHSIG, &death_signal, 0L, 0L, 0L) != 0 ||
        death_signal != SIGKILL || getppid() != spec->expected_parent ||
        prctl(PR_GET_DUMPABLE, 0L, 0L, 0L, 0L) != 1) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

static int
normalize_and_verify_process(const child_spec *spec)
{
    cpu_set_t observed_affinity;
    struct sched_param observed_scheduler;
    char cwd[2];
    int priority;
    if (reset_child_signals() != 0 || apply_rlimits(spec) != 0 ||
        apply_affinity(spec->affinity_cpu) != 0 ||
        sched_setscheduler(0, SCHED_OTHER, &(struct sched_param){0}) != 0 ||
        setpriority(PRIO_PROCESS, 0, 0) != 0 || personality(PER_LINUX) == -1 ||
        personality(0xffffffffUL) != PER_LINUX || chdir("/") != 0) return -1;
    (void)umask(077);
    if (umask(077) != 077 || getcwd(cwd, sizeof(cwd)) == NULL || strcmp(cwd, "/") != 0 ||
        sched_getscheduler(0) != SCHED_OTHER || sched_getparam(0, &observed_scheduler) != 0 ||
        observed_scheduler.sched_priority != 0) {
        errno = EINVAL;
        return -1;
    }
    errno = 0;
    priority = getpriority(PRIO_PROCESS, 0);
    if (errno != 0 || priority != 0 || sched_getaffinity(0, sizeof(observed_affinity), &observed_affinity) != 0 ||
        CPU_COUNT(&observed_affinity) != 1 || !CPU_ISSET(spec->affinity_cpu, &observed_affinity)) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

static int
close_for_role(const child_spec *spec)
{
    unsigned int first;
    unsigned int last;
    if (spec->role_supervisor) {
        if (spec->gate_fd != 8) {
            errno = EINVAL;
            return -1;
        }
        first = 9U;
        last = ~0U;
    } else {
        if (spec->gate_fd != 3) {
            errno = EINVAL;
            return -1;
        }
        first = 4U;
        last = ~0U;
    }
    if (syscall(SYS_close_range, first, last, 0U) != 0) {
        return -1;
    }
    return 0;
}

static int
validate_descriptor(int fd, int access_mode, mode_t object_type, int cloexec)
{
    struct stat identity;
    int status_flags = fcntl(fd, F_GETFL);
    int descriptor_flags = fcntl(fd, F_GETFD);
    if (status_flags < 0 || descriptor_flags < 0 || fstat(fd, &identity) != 0 ||
        (status_flags & O_ACCMODE) != access_mode ||
        (identity.st_mode & S_IFMT) != object_type ||
        (((descriptor_flags & FD_CLOEXEC) != 0) != cloexec)) {
        errno = EINVAL;
        return -1;
    }
    return 0;
}

static int
prepare_exec_fds(const child_spec *spec)
{
    int fd;
    if (fcntl(0, F_GETFL) != (O_RDONLY | O_NONBLOCK) ||
        fcntl(1, F_GETFL) != (O_WRONLY | O_NONBLOCK) ||
        fcntl(2, F_GETFL) != (O_WRONLY | O_NONBLOCK) ||
        validate_descriptor(0, O_RDONLY, S_IFIFO, 0) != 0 ||
        validate_descriptor(1, O_WRONLY, S_IFIFO, 0) != 0 ||
        validate_descriptor(2, O_WRONLY, S_IFIFO, 0) != 0) return -1;
    if (!spec->role_supervisor) return 0;
    for (fd = 3; fd <= 7; ++fd) {
        int flags = fcntl(fd, F_GETFD);
        if (flags < 0 || fcntl(fd, F_SETFD, flags & ~FD_CLOEXEC) != 0) return -1;
    }
    if (fcntl(3, F_GETFL) != (O_RDWR | O_NONBLOCK) ||
        fcntl(4, F_GETFL) != (O_RDONLY | O_DIRECTORY | Q2_KERNEL_O_LARGEFILE) ||
        fcntl(5, F_GETFL) != (O_RDONLY | O_DIRECTORY | Q2_KERNEL_O_LARGEFILE) ||
        fcntl(6, F_GETFL) != (O_RDONLY | O_DIRECTORY | Q2_KERNEL_O_LARGEFILE) ||
        fcntl(7, F_GETFL) != (O_RDONLY | O_DIRECTORY | Q2_KERNEL_O_LARGEFILE) ||
        validate_descriptor(3, O_RDWR, S_IFSOCK, 0) != 0 ||
        validate_descriptor(4, O_RDONLY, S_IFDIR, 0) != 0 ||
        validate_descriptor(5, O_RDONLY, S_IFDIR, 0) != 0 ||
        validate_descriptor(6, O_RDONLY, S_IFDIR, 0) != 0 ||
        validate_descriptor(7, O_RDONLY, S_IFDIR, 0) != 0) return -1;
    return 0;
}

static void
child_fail(int code)
{
    _exit(code);
}

static int
kill_reap_close_pidfd(int pidfd)
{
    siginfo_t information;
    struct pollfd watched;
    struct timespec bounded_wait = {.tv_sec = 1, .tv_nsec = 0};
    int saved_errno = errno;
    int reaped = 0;
    if (pidfd >= 0) {
        (void)syscall(SYS_pidfd_send_signal, pidfd, SIGKILL, NULL, 0U);
        watched.fd = pidfd;
        watched.events = POLLIN;
        watched.revents = 0;
        (void)ppoll(&watched, 1U, &bounded_wait, NULL);
        memset(&information, 0, sizeof(information));
        if (waitid((idtype_t)P_PIDFD, (id_t)pidfd, &information, WEXITED | WNOHANG) == 0 &&
            information.si_pid != 0) reaped = 1;
        (void)close(pidfd);
    }
    errno = saved_errno;
    return reaped;
}

static void
run_child(child_spec *spec)
{
    pid_t after;
    int death_signal = 0;
    /* This is intentionally the first child-side syscall after clone3. */
    if (prctl(PR_SET_PDEATHSIG, SIGKILL) != 0) child_fail(101);
    if (prctl(PR_GET_PDEATHSIG, &death_signal, 0L, 0L, 0L) != 0 || death_signal != SIGKILL)
        child_fail(102);
    after = getppid();
    if (after <= 1 || after != spec->expected_parent) child_fail(103);
    PyOS_AfterFork_Child();

    if (close_for_role(spec) != 0 || validate_gate_fd(spec->gate_fd) != 0) child_fail(104);
    if (wait_exact_release(spec) != 0) child_fail(105);
    if (close(spec->gate_fd) != 0) child_fail(106);

    if (!spec->role_supervisor) {
        if (clear_ambient_keepcaps_and_bounding() != 0 ||
            setgroups(spec->group_count, spec->groups) != 0 ||
            setresgid(spec->gid, spec->gid, spec->gid) != 0 ||
            setresuid(spec->uid, spec->uid, spec->uid) != 0 ||
            set_and_check_fsids(spec->uid, spec->gid) != 0 ||
            clear_capability_sets() != 0 ||
            prctl(PR_SET_NO_NEW_PRIVS, 1L, 0L, 0L, 0L) != 0 ||
            prctl(PR_SET_PDEATHSIG, SIGKILL) != 0 || getppid() != spec->expected_parent ||
            prctl(PR_SET_DUMPABLE, 1L) != 0 || verify_child_identity(spec) != 0) child_fail(108);
    } else {
        if (verify_supervisor_identity(spec) != 0) child_fail(108);
    }
    if (normalize_and_verify_process(spec) != 0) child_fail(107);
    if ((!spec->role_supervisor && verify_child_identity(spec) != 0) ||
        (spec->role_supervisor && verify_supervisor_identity(spec) != 0) ||
        prepare_exec_fds(spec) != 0 || !validate_exact_env(spec->envp)) child_fail(109);
    execve(spec->executable, spec->argv, spec->envp);
    child_fail(110);
}

static PyObject *
py_fixture_clone_into_cgroup(PyObject *self, PyObject *args, PyObject *kwargs)
{
    static char *keywords[] = {"cgroup_fd","gate_fd","gate_deadline_boottime_ns",
                               "role","executable","argv","env",
                               "expected_parent","uid","gid","groups","affinity_cpu","rlimits",NULL};
    int cgroup_fd;
    int gate_fd;
    unsigned long long gate_deadline_boottime_ns;
    const char *role;
    PyObject *executable;
    PyObject *argv;
    PyObject *env;
    int expected_parent;
    unsigned long uid;
    unsigned long gid;
    PyObject *groups;
    int affinity_cpu;
    PyObject *rlimits;
    child_spec *spec;
    struct clone_args clone_arguments;
    struct stat cgroup_identity;
    struct timespec gate_now;
    uint64_t gate_now_ns;
    PyObject *result;
    PyObject *child_object;
    PyObject *pidfd_object;
    int pidfd = -1;
    pid_t child;
    int clone_errno;
    (void)self;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs,
                                     "iiKsOOOikkOiO:fixture_clone_into_cgroup", keywords,
                                     &cgroup_fd, &gate_fd, &gate_deadline_boottime_ns,
                                     &role, &executable, &argv, &env,
                                     &expected_parent, &uid, &gid, &groups, &affinity_cpu, &rlimits)) {
        return NULL;
    }
    if (clock_gettime(CLOCK_BOOTTIME, &gate_now) != 0) return PyErr_SetFromErrno(BridgeError);
    gate_now_ns = timespec_ns(&gate_now);
    if (uid > UINT32_MAX || gid > UINT32_MAX || expected_parent != (int)getpid() ||
        cgroup_fd < 0 || cgroup_fd == gate_fd || fcntl(cgroup_fd, F_GETFD) != FD_CLOEXEC ||
        fcntl(cgroup_fd, F_GETFL) !=
            (O_RDONLY | O_DIRECTORY | Q2_KERNEL_O_LARGEFILE) ||
        fstat(cgroup_fd, &cgroup_identity) != 0 || !S_ISDIR(cgroup_identity.st_mode) ||
        (strcmp(role, "supervisor") != 0 && strcmp(role, "case") != 0) ||
        gate_fd != (strcmp(role, "supervisor") == 0 ? 8 : 3) || validate_gate_fd(gate_fd) != 0 ||
        gate_now_ns == UINT64_MAX || gate_deadline_boottime_ns <= gate_now_ns ||
        gate_deadline_boottime_ns - gate_now_ns > Q2_MAX_GATE_WAIT_NS) {
        PyErr_SetString(BridgeError, "clone identity, role, held cgroup fd, gate, or deadline invalid");
        return NULL;
    }
    spec = PyMem_Calloc(1U, sizeof(*spec));
    if (spec == NULL) return PyErr_NoMemory();
    spec->cgroup_fd = cgroup_fd;
    spec->gate_fd = gate_fd;
    spec->gate_deadline_boottime_ns = (uint64_t)gate_deadline_boottime_ns;
    spec->role_supervisor = strcmp(role, "supervisor") == 0;
    spec->expected_parent = (pid_t)expected_parent;
    spec->uid = (uid_t)uid;
    spec->gid = (gid_t)gid;
    spec->affinity_cpu = affinity_cpu;
    spec->executable = copy_nul_free_bytes(executable, 4096U, "executable");
    if (spec->executable == NULL || spec->executable[0] != '/' ||
        parse_string_vector(argv, spec->argv, Q2_MAX_ARGV, 4096U, "argv") != 0 ||
        parse_string_vector(env, spec->envp, Q2_MAX_ENVP, 64U, "env") != 0 ||
        !validate_exact_env(spec->envp) || parse_groups(groups, spec) != 0 ||
        parse_rlimits(rlimits, spec) != 0) {
        if (!PyErr_Occurred()) PyErr_SetString(BridgeError, "clone child specification invalid");
        free_child_spec(spec);
        return NULL;
    }
    if (strcmp(spec->argv[0], spec->executable) != 0) {
        PyErr_SetString(BridgeError, "argv[0] must equal the absolute executable");
        free_child_spec(spec);
        return NULL;
    }
    if ((spec->role_supervisor && !current_root_identity_matches_spec(spec)) ||
        (!spec->role_supervisor && !case_identity_is_ordinary(spec))) {
        PyErr_SetString(BridgeError, "clone role credentials or supplementary groups invalid");
        free_child_spec(spec);
        return NULL;
    }

    memset(&clone_arguments, 0, sizeof(clone_arguments));
    clone_arguments.flags = CLONE_INTO_CGROUP | CLONE_PIDFD;
    clone_arguments.pidfd = (uint64_t)(uintptr_t)&pidfd;
    clone_arguments.cgroup = (uint64_t)cgroup_fd;
    clone_arguments.exit_signal = SIGCHLD;
    result = PyTuple_New(2);
    if (result == NULL) {
        free_child_spec(spec);
        return NULL;
    }
    PyOS_BeforeFork();
    child = (pid_t)syscall(SYS_clone3, &clone_arguments, sizeof(clone_arguments));
    clone_errno = errno;
    if (child == 0) {
        run_child(spec);
        child_fail(112);
    }
    PyOS_AfterFork_Parent();
    if (child < 0) {
        free_child_spec(spec);
        Py_DECREF(result);
        errno = clone_errno;
        return PyErr_SetFromErrno(BridgeError);
    }
    free_child_spec(spec);
    if (pidfd < 0) {
        /* A successful CLONE_PIDFD without its fd violates the sealed ABI.
         * Exiting the exact parent lets PDEATHSIG contain the child without a
         * forbidden numeric-pid fallback. */
        _exit(113);
    }
    child_object = PyLong_FromLong((long)child);
    pidfd_object = child_object == NULL ? NULL : PyLong_FromLong((long)pidfd);
    if (child_object == NULL || pidfd_object == NULL) {
        Py_XDECREF(child_object);
        Py_XDECREF(pidfd_object);
        Py_DECREF(result);
        if (!kill_reap_close_pidfd(pidfd)) _exit(114);
        return NULL;
    }
    PyTuple_SET_ITEM(result, 0, child_object);
    PyTuple_SET_ITEM(result, 1, pidfd_object);
    return result;
}

static int
dict_u64(PyObject *mapping, const char *key, uint64_t *out)
{
    PyObject *value = PyDict_GetItemString(mapping, key);
    unsigned long long converted;
    if (value == NULL || !PyLong_CheckExact(value)) {
        PyErr_Format(BridgeError, "missing integer arm field %s", key);
        return -1;
    }
    converted = PyLong_AsUnsignedLongLong(value);
    if (converted == (unsigned long long)-1 && PyErr_Occurred()) return -1;
    *out = (uint64_t)converted;
    return 0;
}

static int
signal_handler_is(int signal_number, void (*handler)(int))
{
    struct sigaction observed;
    return sigaction(signal_number, NULL, &observed) == 0 && observed.sa_handler == handler;
}

static __attribute__((noinline)) int
tail_signal_configuration_valid(void)
{
    q2_sigset_view mask;
    q2_sigset_view expected;
    volatile unsigned long *mask_words = mask.words;
    volatile unsigned long *expected_words = expected.words;
    mask_words[0]=0U;mask_words[1]=0U;mask_words[2]=0U;mask_words[3]=0U;
    mask_words[4]=0U;mask_words[5]=0U;mask_words[6]=0U;mask_words[7]=0U;
    mask_words[8]=0U;mask_words[9]=0U;mask_words[10]=0U;mask_words[11]=0U;
    mask_words[12]=0U;mask_words[13]=0U;mask_words[14]=0U;mask_words[15]=0U;
    expected_words[0]=0U;expected_words[1]=0U;expected_words[2]=0U;expected_words[3]=0U;
    expected_words[4]=0U;expected_words[5]=0U;expected_words[6]=0U;expected_words[7]=0U;
    expected_words[8]=0U;expected_words[9]=0U;expected_words[10]=0U;expected_words[11]=0U;
    expected_words[12]=0U;expected_words[13]=0U;expected_words[14]=0U;expected_words[15]=0U;
    if (sigemptyset(&expected.signals) != 0 || sigaddset(&expected.signals, SIGCHLD) != 0 ||
        sigaddset(&expected.signals, SIGUSR1) != 0 ||
        sigaddset(&expected.signals, SIGHUP) != 0 ||
        sigaddset(&expected.signals, SIGTERM) != 0 ||
        sigaddset(&expected.signals, SIGINT) != 0 ||
        sigaddset(&expected.signals, SIGQUIT) != 0 ||
        sigaddset(&expected.signals, SIGXCPU) != 0 ||
        sigaddset(&expected.signals, tail_plan.deadline_signal) != 0 ||
        sigprocmask(SIG_SETMASK, NULL, &mask.signals) != 0 ||
        mask_words[0] != expected_words[0] || mask_words[1] != expected_words[1] ||
        mask_words[2] != expected_words[2] || mask_words[3] != expected_words[3] ||
        mask_words[4] != expected_words[4] || mask_words[5] != expected_words[5] ||
        mask_words[6] != expected_words[6] || mask_words[7] != expected_words[7] ||
        mask_words[8] != expected_words[8] || mask_words[9] != expected_words[9] ||
        mask_words[10] != expected_words[10] || mask_words[11] != expected_words[11] ||
        mask_words[12] != expected_words[12] || mask_words[13] != expected_words[13] ||
        mask_words[14] != expected_words[14] || mask_words[15] != expected_words[15]) return 0;
    return signal_handler_is(SIGCHLD, SIG_DFL) && signal_handler_is(SIGUSR1, SIG_DFL) &&
           signal_handler_is(SIGHUP, SIG_DFL) && signal_handler_is(SIGTERM, SIG_DFL) &&
           signal_handler_is(SIGINT, SIG_DFL) && signal_handler_is(SIGQUIT, SIG_DFL) &&
           signal_handler_is(SIGXCPU, SIG_DFL) &&
           signal_handler_is(tail_plan.deadline_signal, SIG_DFL) &&
           signal_handler_is(SIGALRM, SIG_DFL) && signal_handler_is(SIGPROF, SIG_DFL) &&
           signal_handler_is(SIGPIPE, SIG_IGN);
}

static int
hex_nibble(unsigned char value)
{
    if (value >= (unsigned char)'0' && value <= (unsigned char)'9') return value - (unsigned char)'0';
    if (value >= (unsigned char)'a' && value <= (unsigned char)'f')
        return value - (unsigned char)'a' + 10;
    if (value >= (unsigned char)'A' && value <= (unsigned char)'F')
        return value - (unsigned char)'A' + 10;
    return -1;
}

#ifdef Q2_BRIDGE_NATIVE_TEST_HOOKS
#define Q2_PARSER_SCOPE __attribute__((visibility("default")))
#else
#define Q2_PARSER_SCOPE static
#endif

Q2_PARSER_SCOPE int
q2_parse_signalfd_mask(const unsigned char *raw, size_t count, uint64_t expected)
{
    static const unsigned char marker[] = "sigmask:\t";
    size_t marker_offset = SIZE_MAX;
    size_t value_offset;
    size_t offset;
    size_t index;
    uint64_t observed = 0;
    int nibble;
    if (raw == NULL || count == 0U) return 0;
    for (offset = 0U; offset + sizeof(marker) - 1U <= count; ++offset) {
        if (memcmp(raw + offset, marker, sizeof(marker) - 1U) != 0) continue;
        if ((offset != 0U && raw[offset - 1U] != (unsigned char)'\n') ||
            marker_offset != SIZE_MAX) return 0;
        marker_offset = offset;
    }
    if (marker_offset == SIZE_MAX) return 0;
    value_offset = marker_offset + sizeof(marker) - 1U;
    if (count - value_offset < 17U) return 0;
    for (index = 0U; index < 16U; ++index) {
        nibble = hex_nibble(raw[value_offset + index]);
        if (nibble < 0) return 0;
        observed = (observed << 4) | (uint64_t)nibble;
    }
    if (raw[value_offset + 16U] != (unsigned char)'\n') return 0;
    return observed == expected;
}

#undef Q2_PARSER_SCOPE

static int
signalfd_mask_matches_held_procfs(void)
{
    char extra;
    struct stat proc_identity;
    struct statfs proc_filesystem;
    uint64_t expected = 0;
    ssize_t count;
    ssize_t trailing;
    int fd;
    int close_result;
    if (fcntl(4, F_GETFL) != (O_RDONLY | O_DIRECTORY | Q2_KERNEL_O_LARGEFILE) ||
        fcntl(4, F_GETFD) != 0 || fstat(4, &proc_identity) != 0 ||
        !S_ISDIR(proc_identity.st_mode) || fstatfs(4, &proc_filesystem) != 0 ||
        (unsigned long)proc_filesystem.f_type != (unsigned long)PROC_SUPER_MAGIC) return 0;
    fd = openat(4, "self/fdinfo/3", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return 0;
    count = pread(fd, tail_plan.signalfd_fdinfo.bytes,
                  sizeof(tail_plan.signalfd_fdinfo.bytes), 0);
    trailing = count > 0 ? pread(fd, &extra, 1U, count) : -1;
    close_result = close(fd);
    if (count <= 0 || trailing != 0 || close_result != 0) return 0;
    expected |= 1ULL << (SIGCHLD - 1);
    expected |= 1ULL << (SIGUSR1 - 1);
    expected |= 1ULL << (SIGHUP - 1);
    expected |= 1ULL << (SIGTERM - 1);
    expected |= 1ULL << (SIGINT - 1);
    expected |= 1ULL << (SIGQUIT - 1);
    expected |= 1ULL << (SIGXCPU - 1);
    expected |= 1ULL << (tail_plan.deadline_signal - 1);
    if (!q2_parse_signalfd_mask(tail_plan.signalfd_fdinfo.bytes,
                                (size_t)count, expected)) return 0;
    tail_plan.signalfd_fdinfo_size = (size_t)count;
    return 1;
}

static PyObject *
py_fixture_setup(PyObject *self, PyObject *args)
{
    int fd0, fd1, fd2, deadline_signal;
    int flags0, flags1, flags2;
    int descriptors0, descriptors1, descriptors2;
    struct stat stat0, stat1, stat2;
    struct sigaction ignore, observed;
    (void)self;
    if (tail_plan.state != Q2_TAIL_UNARMED) {
        PyErr_SetString(BridgeError, "cleanup tail setup is one-shot");
        return NULL;
    }
    tail_plan.state = Q2_TAIL_FAILED;
    if (!PyArg_ParseTuple(args, "iiii:fixture_setup", &fd0, &fd1, &fd2, &deadline_signal)) return NULL;
    if (fd0 != 0 || fd1 != 1 || fd2 != 2 ||
        deadline_signal < SIGRTMIN || deadline_signal > SIGRTMAX) {
        PyErr_SetString(BridgeError, "cleanup tail setup requires fd0/fd1/fd2");
        return NULL;
    }
    flags0 = fcntl(fd0, F_GETFL); flags1 = fcntl(fd1, F_GETFL); flags2 = fcntl(fd2, F_GETFL);
    descriptors0 = fcntl(fd0, F_GETFD); descriptors1 = fcntl(fd1, F_GETFD);
    descriptors2 = fcntl(fd2, F_GETFD);
    if (flags0 < 0 || flags1 < 0 || flags2 < 0 ||
        descriptors0 < 0 || descriptors1 < 0 || descriptors2 < 0 ||
        fstat(fd0,&stat0)!=0 || fstat(fd1,&stat1)!=0 || fstat(fd2,&stat2)!=0) {
        return PyErr_SetFromErrno(BridgeError);
    }
    if (flags0 != (O_RDONLY | O_NONBLOCK) || flags1 != (O_WRONLY | O_NONBLOCK) ||
        flags2 != (O_WRONLY | O_NONBLOCK) ||
        (descriptors0 & FD_CLOEXEC) != 0 || (descriptors1 & FD_CLOEXEC) != 0 ||
        (descriptors2 & FD_CLOEXEC) != 0 || !S_ISFIFO(stat0.st_mode) ||
        !S_ISFIFO(stat1.st_mode) || !S_ISFIFO(stat2.st_mode) ||
        fpathconf(fd1, _PC_PIPE_BUF) < (long)Q2_RECEIPT_SIZE ||
        same_fd_identity(&stat0, &stat1) || same_fd_identity(&stat0, &stat2) ||
        same_fd_identity(&stat1, &stat2)) {
        PyErr_SetString(BridgeError,"cleanup protocol fd type, access mode, or nonblocking flag invalid");
        return NULL;
    }
    memset(&ignore,0,sizeof(ignore)); ignore.sa_handler=SIG_IGN; sigemptyset(&ignore.sa_mask);
    if (sigaction(SIGPIPE,&ignore,NULL)!=0 || sigaction(SIGPIPE,NULL,&observed)!=0)
        return PyErr_SetFromErrno(BridgeError);
    if (observed.sa_handler!=SIG_IGN) {
        PyErr_SetString(BridgeError,"SIGPIPE ignore readback failed");
        return NULL;
    }
    tail_plan.fd0 = fd0; tail_plan.fd1 = fd1; tail_plan.fd2 = fd2;
    tail_plan.fd_identity[0] = stat0;
    tail_plan.fd_identity[1] = stat1;
    tail_plan.fd_identity[2] = stat2;
    tail_plan.deadline_signal = deadline_signal;
    tail_plan.state = Q2_TAIL_SETUP;
    Py_RETURN_NONE;
}

static PyObject *
py_fixture_arm(PyObject *self, PyObject *args)
{
    PyObject *receipt;
    PyObject *limits;
    char *raw;
    Py_ssize_t length;
    uint64_t schema_version;
    uint64_t signalfd_fd;
    uint64_t fatal_timer_id;
    uint64_t fatal_timer_clock;
    uint64_t stop_latched;
    uint64_t domain_total;
    int signalfd_status;
    int signalfd_descriptor;
    struct itimerspec fatal_timer;
    struct itimerval profiler_timer;
    struct stat signalfd_identity;
    static const unsigned char magic[8] = {'Q','2','N','S','R','0','0','1'};
    (void)self;
    if (tail_plan.state != Q2_TAIL_SETUP) {
        PyErr_SetString(BridgeError, "cleanup tail arm is one-shot and requires setup");
        return NULL;
    }
    tail_plan.state = Q2_TAIL_FAILED;
    if (!PyArg_ParseTuple(args, "OO:fixture_arm", &receipt, &limits)) return NULL;
    if (!PyBytes_CheckExact(receipt) || !PyDict_CheckExact(limits)) {
        PyErr_SetString(BridgeError, "cleanup tail arm inputs invalid");
        return NULL;
    }
    if (PyBytes_AsStringAndSize(receipt, &raw, &length) < 0) return NULL;
    if (length != Q2_RECEIPT_SIZE ||
        memcmp(raw + Q2_RECEIPT_MAGIC_OFFSET, magic, sizeof(magic)) != 0) {
        PyErr_SetString(BridgeError, "receipt must be the fixed 224-byte v1 layout");
        return NULL;
    }
    if (le64_load((unsigned char *)raw + Q2_RECEIPT_VERSION_OFFSET) != 1U ||
        memcmp(raw + Q2_RECEIPT_PROCESS_OFFSET, (unsigned char[32]){0}, 32U) != 0 ||
        le64_load((unsigned char *)raw + Q2_RECEIPT_COUNTER_OFFSET) == 0 ||
        memcmp(raw + Q2_RECEIPT_PREVIOUS_DIGEST_OFFSET,
               (unsigned char[Q2_RECEIPT_DIGEST_SIZE]){0}, Q2_RECEIPT_DIGEST_SIZE) == 0 ||
        memcmp(raw + Q2_RECEIPT_H_DIGEST_OFFSET,
               (unsigned char[Q2_RECEIPT_DIGEST_SIZE]){0}, Q2_RECEIPT_DIGEST_SIZE) == 0 ||
        memcmp(raw + Q2_RECEIPT_CLEANUP_FINAL_DIGEST_OFFSET,
               (unsigned char[Q2_RECEIPT_DIGEST_SIZE]){0}, Q2_RECEIPT_DIGEST_SIZE) == 0 ||
        memcmp(raw + Q2_RECEIPT_ACK_CAPTURE_HEAD_OFFSET,
               (unsigned char[Q2_RECEIPT_DIGEST_SIZE]){0}, Q2_RECEIPT_DIGEST_SIZE) == 0 ||
        memcmp(raw + Q2_RECEIPT_RESERVED_OFFSET, (unsigned char[8]){0}, 8U) != 0 ||
        memcmp(raw + Q2_RECEIPT_HASH_OFFSET,
               (unsigned char[Q2_RECEIPT_DIGEST_SIZE]){0}, Q2_RECEIPT_DIGEST_SIZE) != 0) {
        PyErr_SetString(BridgeError, "receipt fixed fields, zero samples, or digest template invalid");
        return NULL;
    }
    if (PyDict_Size(limits) != 20 ||
        dict_u64(limits,"last_process_ns",&tail_plan.last_process_ns) != 0 ||
        dict_u64(limits,"process_accounted_ns",&tail_plan.process_accounted_ns) != 0 ||
        dict_u64(limits,"carrier_accounted_ns",&tail_plan.carrier_accounted_ns) != 0 ||
        dict_u64(limits,"guardian_accounted_ns",&tail_plan.guardian_accounted_ns) != 0 ||
        dict_u64(limits,"guardian_usage_ns",&tail_plan.guardian_usage_ns) != 0 ||
        dict_u64(limits,"sample_round_ns",&tail_plan.sample_round_ns) != 0 ||
        dict_u64(limits,"tail_cpu_max_ns",&tail_plan.tail_cpu_max_ns) != 0 ||
        dict_u64(limits,"tail_wall_max_ns",&tail_plan.tail_wall_max_ns) != 0 ||
        dict_u64(limits,"boot_deadline_ns",&tail_plan.boot_deadline_ns) != 0 ||
        dict_u64(limits,"mono_deadline_ns",&tail_plan.mono_deadline_ns) != 0 ||
        dict_u64(limits,"realtime_deadline_ns",&tail_plan.realtime_deadline_ns) != 0 ||
        dict_u64(limits,"realtime_minus_boot_ns",&tail_plan.realtime_minus_boot_ns) != 0 ||
        dict_u64(limits,"realtime_minus_mono_ns",&tail_plan.realtime_minus_mono_ns) != 0 ||
        dict_u64(limits,"clock_step_tolerance_ns",&tail_plan.clock_step_tolerance_ns) != 0 ||
        dict_u64(limits,"fatal_timer_min_remaining_ns",&tail_plan.fatal_timer_min_remaining_ns) != 0 ||
        dict_u64(limits,"fatal_timer_id",&fatal_timer_id) != 0 ||
        dict_u64(limits,"fatal_timer_clock",&fatal_timer_clock) != 0 ||
        dict_u64(limits,"signalfd_fd",&signalfd_fd) != 0 ||
        dict_u64(limits,"stop_latched",&stop_latched) != 0 ||
        dict_u64(limits,"schema_version",&schema_version) != 0) {
        return NULL;
    }
    if (schema_version != 1U || signalfd_fd != 3U || stop_latched != 0U ||
        fatal_timer_clock != (uint64_t)CLOCK_PROCESS_CPUTIME_ID ||
        tail_plan.tail_cpu_max_ns == 0 || tail_plan.tail_cpu_max_ns >= 1000000000ULL ||
        tail_plan.tail_wall_max_ns == 0 || tail_plan.tail_wall_max_ns > 1000000000ULL ||
        tail_plan.sample_round_ns == 0 || tail_plan.sample_round_ns >= 1000000000ULL ||
        tail_plan.clock_step_tolerance_ns == 0 ||
        tail_plan.clock_step_tolerance_ns > 2000000000ULL ||
        tail_plan.fatal_timer_min_remaining_ns < tail_plan.tail_cpu_max_ns ||
        tail_plan.guardian_usage_ns > tail_plan.guardian_accounted_ns ||
        tail_plan.guardian_accounted_ns > 9000000000ULL ||
        tail_plan.last_process_ns != tail_plan.process_accounted_ns ||
        add_u64(tail_plan.guardian_accounted_ns, tail_plan.carrier_accounted_ns,
                &domain_total) != 0 || domain_total < tail_plan.process_accounted_ns) {
        PyErr_SetString(BridgeError, "cleanup tail fixed limits invalid");
        return NULL;
    }
    tail_plan.stop_latched = (int)stop_latched;
    tail_plan.signalfd_fd = (int)signalfd_fd;
    tail_plan.fatal_timer_id = (timer_t)(uintptr_t)fatal_timer_id;
    signalfd_status = fcntl(tail_plan.signalfd_fd, F_GETFL);
    signalfd_descriptor = fcntl(tail_plan.signalfd_fd, F_GETFD);
    if (signalfd_status < 0 || signalfd_descriptor < 0 ||
        fstat(tail_plan.signalfd_fd, &signalfd_identity) != 0 ||
        signalfd_status != (O_RDWR | O_NONBLOCK) || signalfd_descriptor != 0 ||
        !signalfd_mask_matches_held_procfs() ||
        timer_gettime(tail_plan.fatal_timer_id, &fatal_timer) != 0 ||
        fatal_timer.it_interval.tv_sec != 0 || fatal_timer.it_interval.tv_nsec != 0 ||
        timespec_ns(&fatal_timer.it_value) == UINT64_MAX ||
        timespec_ns(&fatal_timer.it_value) < tail_plan.fatal_timer_min_remaining_ns ||
        getitimer(ITIMER_PROF, &profiler_timer) != 0 ||
        profiler_timer.it_interval.tv_sec != 0 || profiler_timer.it_interval.tv_usec != 0 ||
        profiler_timer.it_value.tv_sec != 0 || profiler_timer.it_value.tv_usec != 0 ||
        !tail_signal_configuration_valid()) {
        PyErr_SetString(BridgeError, "cleanup tail guard, signal, or signalfd state invalid");
        return NULL;
    }
    tail_plan.signalfd_identity = signalfd_identity;
    memcpy(tail_plan.receipt, raw, Q2_RECEIPT_SIZE);
    tail_plan.state = Q2_TAIL_ARMED;
    Py_RETURN_NONE;
}

static int
pending_stop_signal(void)
{
    sigset_t pending;
    if (sigpending(&pending) != 0) return 1;
    return sigismember(&pending,SIGCHLD)!=0 || sigismember(&pending,SIGUSR1)!=0 ||
           sigismember(&pending,SIGHUP)!=0 || sigismember(&pending,SIGTERM)!=0 ||
           sigismember(&pending,SIGINT)!=0 || sigismember(&pending,SIGQUIT)!=0 ||
           sigismember(&pending,SIGXCPU)!=0 || sigismember(&pending,SIGALRM)!=0 ||
           sigismember(&pending,SIGPROF)!=0 ||
           sigismember(&pending,tail_plan.deadline_signal)!=0;
}

static int
tail_descriptors_valid(void)
{
    struct stat identity0, identity1, identity2, signalfd_identity;
    return fcntl(tail_plan.fd0, F_GETFL) == (O_RDONLY | O_NONBLOCK) &&
           fcntl(tail_plan.fd1, F_GETFL) == (O_WRONLY | O_NONBLOCK) &&
           fcntl(tail_plan.fd2, F_GETFL) == (O_WRONLY | O_NONBLOCK) &&
           validate_descriptor(tail_plan.fd0, O_RDONLY, S_IFIFO, 0) == 0 &&
           validate_descriptor(tail_plan.fd1, O_WRONLY, S_IFIFO, 0) == 0 &&
           validate_descriptor(tail_plan.fd2, O_WRONLY, S_IFIFO, 0) == 0 &&
           fstat(tail_plan.fd0, &identity0) == 0 && fstat(tail_plan.fd1, &identity1) == 0 &&
           fstat(tail_plan.fd2, &identity2) == 0 &&
           same_fd_identity(&identity0, &tail_plan.fd_identity[0]) &&
           same_fd_identity(&identity1, &tail_plan.fd_identity[1]) &&
           same_fd_identity(&identity2, &tail_plan.fd_identity[2]) &&
           fcntl(tail_plan.signalfd_fd, F_GETFL) == (O_RDWR | O_NONBLOCK) &&
           fcntl(tail_plan.signalfd_fd, F_GETFD) == 0 &&
           fstat(tail_plan.signalfd_fd, &signalfd_identity) == 0 &&
           same_fd_identity(&signalfd_identity, &tail_plan.signalfd_identity);
}

static __attribute__((noinline)) int
tail_signalfd_fdinfo_valid(void)
{
    char extra;
    struct stat proc_identity;
    struct statfs proc_filesystem;
    volatile const uint64_t *observed = tail_fdinfo_scratch.words;
    volatile const uint64_t *expected = tail_plan.signalfd_fdinfo.words;
    uint64_t difference = 0;
    ssize_t count;
    ssize_t trailing;
    int fd;
    int close_result;
    if (fcntl(4, F_GETFL) != (O_RDONLY | O_DIRECTORY | Q2_KERNEL_O_LARGEFILE) ||
        fcntl(4, F_GETFD) != 0 || fstat(4, &proc_identity) != 0 ||
        !S_ISDIR(proc_identity.st_mode) || fstatfs(4, &proc_filesystem) != 0 ||
        (unsigned long)proc_filesystem.f_type != (unsigned long)PROC_SUPER_MAGIC) return 0;
    fd = openat(4, "self/fdinfo/3", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return 0;
    count = pread(fd, tail_fdinfo_scratch.bytes, sizeof(tail_fdinfo_scratch.bytes), 0);
    trailing = count > 0 ? pread(fd, &extra, 1U, count) : -1;
    close_result = close(fd);
    if (count <= 0 || trailing != 0 || close_result != 0 ||
        (size_t)count != tail_plan.signalfd_fdinfo_size) return 0;
#define Q2_DIFF_WORD(index) difference |= observed[(index)] ^ expected[(index)]
#define Q2_DIFF_8(base) { \
    Q2_DIFF_WORD((base)+0U);Q2_DIFF_WORD((base)+1U); \
    Q2_DIFF_WORD((base)+2U);Q2_DIFF_WORD((base)+3U); \
    Q2_DIFF_WORD((base)+4U);Q2_DIFF_WORD((base)+5U); \
    Q2_DIFF_WORD((base)+6U);Q2_DIFF_WORD((base)+7U); \
}
#define Q2_DIFF_32(base) { \
    Q2_DIFF_8((base)+0U);Q2_DIFF_8((base)+8U); \
    Q2_DIFF_8((base)+16U);Q2_DIFF_8((base)+24U); \
}
    Q2_DIFF_32(0U);Q2_DIFF_32(32U);Q2_DIFF_32(64U);Q2_DIFF_32(96U);
#undef Q2_DIFF_32
#undef Q2_DIFF_8
#undef Q2_DIFF_WORD
    return difference == 0U;
}

static int
tail_guards_valid(void)
{
    struct itimerspec fatal_timer;
    struct itimerval profiler_timer;
    uint64_t fatal_remaining;
    if (timer_gettime(tail_plan.fatal_timer_id, &fatal_timer) != 0 ||
        fatal_timer.it_interval.tv_sec != 0 || fatal_timer.it_interval.tv_nsec != 0 ||
        getitimer(ITIMER_PROF, &profiler_timer) != 0 ||
        profiler_timer.it_interval.tv_sec != 0 || profiler_timer.it_interval.tv_usec != 0 ||
        profiler_timer.it_value.tv_sec != 0 || profiler_timer.it_value.tv_usec != 0) return 0;
    fatal_remaining = timespec_ns(&fatal_timer.it_value);
    return fatal_remaining != UINT64_MAX &&
           fatal_remaining >= tail_plan.fatal_timer_min_remaining_ns;
}

static int
tail_signalfd_empty(void)
{
    struct signalfd_siginfo information;
    ssize_t count;
    errno = 0;
    count = read(tail_plan.signalfd_fd, &information, sizeof(information));
    return count == -1 && errno == EAGAIN;
}

static __attribute__((noreturn,noinline)) void
tail_fail(int code)
{
    (void)close(tail_plan.fd1);
    (void)close(tail_plan.fd2);
    _exit(code);
}

static __attribute__((noinline)) int
restore_tail_signals(void)
{
    sigset_t unblocked;
    int failed = 0;
    if (sigemptyset(&unblocked) != 0 ||
        sigaddset(&unblocked,SIGUSR1)!=0 ||
        sigaddset(&unblocked,SIGHUP)!=0 ||
        sigaddset(&unblocked,SIGTERM)!=0 || sigaddset(&unblocked,SIGINT)!=0 ||
        sigaddset(&unblocked,SIGQUIT)!=0 || sigaddset(&unblocked,SIGXCPU)!=0 ||
        sigaddset(&unblocked,tail_plan.deadline_signal)!=0) return -1;
    if (sigaction(SIGUSR1,&q2_default_signal_action,NULL)!=0) failed = 1;
    if (sigaction(SIGHUP,&q2_default_signal_action,NULL)!=0) failed = 1;
    if (sigaction(SIGTERM,&q2_default_signal_action,NULL)!=0) failed = 1;
    if (sigaction(SIGINT,&q2_default_signal_action,NULL)!=0) failed = 1;
    if (sigaction(SIGQUIT,&q2_default_signal_action,NULL)!=0) failed = 1;
    if (sigaction(SIGXCPU,&q2_default_signal_action,NULL)!=0) failed = 1;
    if (sigaction(tail_plan.deadline_signal,&q2_default_signal_action,NULL)!=0) failed = 1;
    if (sigprocmask(SIG_UNBLOCK,&unblocked,NULL)!=0) failed = 1;
    return failed ? -1 : 0;
}

static PyObject *
py_fixture_cleanup_tail(PyObject *self, PyObject *noargs)
{
    struct timespec process_time, boot_time, mono_time, realtime;
    uint64_t process_ns, boot_ns, mono_ns, realtime_ns;
    uint64_t process_with_tail, carrier_delta, carrier_with_tail, domain_total;
    uint64_t boot_with_tail, mono_with_tail, realtime_with_tail;
    uint64_t realtime_minus_boot, realtime_minus_mono;
    unsigned char probe;
    ssize_t written;
    int sigpipe_result;
    int close_stdout_result;
    int close_stderr_result;
    (void)self; (void)noargs;

    /* The first observable operation is the final process-clock sample. */
    if (clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&process_time)!=0) _exit(201);
    if (clock_gettime(CLOCK_BOOTTIME,&boot_time)!=0 || clock_gettime(CLOCK_MONOTONIC,&mono_time)!=0 ||
        clock_gettime(CLOCK_REALTIME,&realtime)!=0) {
        if (tail_plan.state == Q2_TAIL_ARMED) tail_fail(202);
        _exit(202);
    }
    if (tail_plan.state!=Q2_TAIL_ARMED) _exit(203);
    process_ns=timespec_ns(&process_time);boot_ns=timespec_ns(&boot_time);
    mono_ns=timespec_ns(&mono_time);realtime_ns=timespec_ns(&realtime);
    if (process_ns==UINT64_MAX || boot_ns==UINT64_MAX || mono_ns==UINT64_MAX || realtime_ns==UINT64_MAX ||
        realtime_ns < boot_ns || realtime_ns < mono_ns ||
        process_ns<tail_plan.last_process_ns ||
        tail_plan.process_accounted_ns != tail_plan.last_process_ns ||
        add_u64(process_ns,tail_plan.tail_cpu_max_ns,&process_with_tail)!=0 ||
        process_with_tail>18000000000ULL ||
        add_u64(process_ns-tail_plan.last_process_ns,tail_plan.sample_round_ns,&carrier_delta)!=0 ||
        add_u64(tail_plan.carrier_accounted_ns,carrier_delta,&carrier_with_tail)!=0 ||
        add_u64(carrier_with_tail,tail_plan.tail_cpu_max_ns,&carrier_with_tail)!=0 ||
        carrier_with_tail>9000000000ULL || tail_plan.guardian_usage_ns>9000000000ULL ||
        add_u64(tail_plan.guardian_accounted_ns,
                carrier_with_tail-tail_plan.tail_cpu_max_ns,&domain_total)!=0 ||
        domain_total<process_ns ||
        add_u64(boot_ns,tail_plan.tail_wall_max_ns,&boot_with_tail)!=0 ||
        boot_with_tail>=tail_plan.boot_deadline_ns ||
        add_u64(mono_ns,tail_plan.tail_wall_max_ns,&mono_with_tail)!=0 ||
        mono_with_tail>=tail_plan.mono_deadline_ns ||
        add_u64(realtime_ns,tail_plan.tail_wall_max_ns,&realtime_with_tail)!=0 ||
        realtime_with_tail>=tail_plan.realtime_deadline_ns) tail_fail(204);
    realtime_minus_boot = realtime_ns - boot_ns;
    realtime_minus_mono = realtime_ns - mono_ns;
    if (u64_distance(realtime_minus_boot,tail_plan.realtime_minus_boot_ns) >
            tail_plan.clock_step_tolerance_ns ||
        u64_distance(realtime_minus_mono,tail_plan.realtime_minus_mono_ns) >
            tail_plan.clock_step_tolerance_ns ||
        tail_plan.stop_latched != 0 || !tail_descriptors_valid() ||
        !tail_signalfd_fdinfo_valid() ||
        !tail_signal_configuration_valid() || !tail_guards_valid() ||
        !tail_signalfd_empty() || pending_stop_signal()) tail_fail(204);
    errno=0;
    if (read(tail_plan.fd0,&probe,1U)!=-1 || errno!=EAGAIN) tail_fail(205);
    le64_store(tail_plan.receipt+Q2_RECEIPT_PROCESS_OFFSET,process_ns);
    le64_store(tail_plan.receipt+Q2_RECEIPT_BOOTTIME_OFFSET,boot_ns);
    le64_store(tail_plan.receipt+Q2_RECEIPT_MONOTONIC_OFFSET,mono_ns);
    le64_store(tail_plan.receipt+Q2_RECEIPT_REALTIME_OFFSET,realtime_ns);
    sha256_fixed192(tail_plan.receipt,tail_plan.receipt+Q2_RECEIPT_HASH_OFFSET);
    if (restore_tail_signals()!=0) tail_fail(206);
    written=write(tail_plan.fd1,tail_plan.receipt,Q2_RECEIPT_SIZE);
    sigpipe_result=sigaction(SIGPIPE,&q2_default_signal_action,NULL);
    close_stdout_result=close(tail_plan.fd1);
    close_stderr_result=close(tail_plan.fd2);
    if (sigpipe_result!=0 || written!=(ssize_t)Q2_RECEIPT_SIZE ||
        close_stdout_result!=0 || close_stderr_result!=0) _exit(207);
    _exit(0);
}

static PyObject *
py_manifest(PyObject *self, PyObject *noargs)
{
    PyObject *manifest;
    PyObject *clone_flags;
    PyObject *exports;
    PyObject *value;
    (void)self; (void)noargs;
    manifest = PyDict_New();
    if (manifest == NULL) return NULL;
#define ADD_MANIFEST_INT(name, number) do { \
    value = PyLong_FromUnsignedLongLong((unsigned long long)(number)); \
    if (value == NULL || PyDict_SetItemString(manifest, (name), value) != 0) { \
        Py_XDECREF(value); Py_DECREF(manifest); return NULL; \
    } \
    Py_DECREF(value); \
} while (0)
#define ADD_MANIFEST_STRING(name, text) do { \
    value = PyUnicode_FromString((text)); \
    if (value == NULL || PyDict_SetItemString(manifest, (name), value) != 0) { \
        Py_XDECREF(value); Py_DECREF(manifest); return NULL; \
    } \
    Py_DECREF(value); \
} while (0)
#define ADD_MANIFEST_BOOL(name, truth) do { \
    value = PyBool_FromLong((truth) ? 1L : 0L); \
    if (value == NULL || PyDict_SetItemString(manifest, (name), value) != 0) { \
        Py_XDECREF(value); Py_DECREF(manifest); return NULL; \
    } \
    Py_DECREF(value); \
} while (0)
    ADD_MANIFEST_INT("abi_version", Q2_BRIDGE_ABI_VERSION);
    ADD_MANIFEST_INT("clone_args_size", sizeof(struct clone_args));
    clone_flags = Py_BuildValue("[ss]", "CLONE_INTO_CGROUP", "CLONE_PIDFD");
    if (clone_flags == NULL || PyDict_SetItemString(manifest, "clone_flags", clone_flags) != 0) {
        Py_XDECREF(clone_flags); Py_DECREF(manifest); return NULL;
    }
    Py_DECREF(clone_flags);
    ADD_MANIFEST_INT("clone_flags_value", CLONE_INTO_CGROUP | CLONE_PIDFD);
    ADD_MANIFEST_STRING("exit_signal", "SIGCHLD");
    ADD_MANIFEST_INT("release_byte", Q2_RELEASE_BYTE);
    ADD_MANIFEST_INT("max_gate_wait_ns", Q2_MAX_GATE_WAIT_NS);
    ADD_MANIFEST_INT("max_argv", Q2_MAX_ARGV);
    ADD_MANIFEST_INT("max_env", Q2_MAX_ENVP);
    ADD_MANIFEST_INT("max_groups", Q2_MAX_GROUPS);
    ADD_MANIFEST_STRING("module_name", "_q2_namespace_clone_bridge");
    ADD_MANIFEST_STRING("init_symbol", "PyInit__q2_namespace_clone_bridge");
    exports = Py_BuildValue("[ssss]", "fixture_clone_into_cgroup", "fixture_setup",
                            "fixture_arm", "fixture_cleanup_tail");
    if (exports == NULL || PyDict_SetItemString(manifest, "exports", exports) != 0) {
        Py_XDECREF(exports); Py_DECREF(manifest); return NULL;
    }
    Py_DECREF(exports);
    ADD_MANIFEST_INT("receipt_size", Q2_RECEIPT_SIZE);
    ADD_MANIFEST_STRING("receipt_magic_ascii", "Q2NSR001");
    ADD_MANIFEST_INT("receipt_magic_offset", Q2_RECEIPT_MAGIC_OFFSET);
    ADD_MANIFEST_INT("receipt_magic_bytes", 8U);
    ADD_MANIFEST_INT("receipt_version", 1U);
    ADD_MANIFEST_INT("receipt_version_offset", Q2_RECEIPT_VERSION_OFFSET);
    ADD_MANIFEST_STRING("receipt_byte_order", "little");
    ADD_MANIFEST_INT("receipt_process_ns_offset", Q2_RECEIPT_PROCESS_OFFSET);
    ADD_MANIFEST_INT("receipt_boottime_ns_offset", Q2_RECEIPT_BOOTTIME_OFFSET);
    ADD_MANIFEST_INT("receipt_monotonic_ns_offset", Q2_RECEIPT_MONOTONIC_OFFSET);
    ADD_MANIFEST_INT("receipt_realtime_ns_offset", Q2_RECEIPT_REALTIME_OFFSET);
    ADD_MANIFEST_INT("receipt_counter_offset", Q2_RECEIPT_COUNTER_OFFSET);
    ADD_MANIFEST_INT("receipt_previous_digest_offset", Q2_RECEIPT_PREVIOUS_DIGEST_OFFSET);
    ADD_MANIFEST_INT("receipt_h_digest_offset", Q2_RECEIPT_H_DIGEST_OFFSET);
    ADD_MANIFEST_INT("receipt_cleanup_final_digest_offset", Q2_RECEIPT_CLEANUP_FINAL_DIGEST_OFFSET);
    ADD_MANIFEST_INT("receipt_ack_capture_head_offset", Q2_RECEIPT_ACK_CAPTURE_HEAD_OFFSET);
    ADD_MANIFEST_INT("receipt_reserved_offset", Q2_RECEIPT_RESERVED_OFFSET);
    ADD_MANIFEST_INT("receipt_reserved_bytes", 8U);
    ADD_MANIFEST_INT("receipt_hash_offset", Q2_RECEIPT_HASH_OFFSET);
    ADD_MANIFEST_INT("receipt_hash_input_bytes", Q2_RECEIPT_HASH_OFFSET);
    ADD_MANIFEST_INT("receipt_sha256_bytes", Q2_RECEIPT_DIGEST_SIZE);
    ADD_MANIFEST_INT("receipt_digest_size", Q2_RECEIPT_DIGEST_SIZE);
    ADD_MANIFEST_BOOL("receipt_single_raw_nonblocking_write", 1);
    ADD_MANIFEST_STRING("fatal_timer_clock_identity",
                        "caller-sealed-not-kernel-readable:CLOCK_PROCESS_CPUTIME_ID");
    ADD_MANIFEST_STRING("atfork_registry_guard", "BLOCKED_EXTERNAL_F2_SOURCE_PROOF");
    ADD_MANIFEST_STRING("main_thread_guard", "BLOCKED_EXTERNAL_CALLER_PROOF");
#undef ADD_MANIFEST_BOOL
#undef ADD_MANIFEST_STRING
#undef ADD_MANIFEST_INT
    return manifest;
}

static PyMethodDef methods[] = {
    {"manifest",(PyCFunction)py_manifest,METH_NOARGS,"Return the fixed native ABI manifest."},
    {"fixture_clone_into_cgroup",
     (PyCFunction)(void(*)(void))py_fixture_clone_into_cgroup,METH_VARARGS|METH_KEYWORDS,
     "Atomically clone into a held cgroup and exec after a one-byte native gate."},
    {"fixture_setup",py_fixture_setup,METH_VARARGS,"Register fixed nonblocking protocol fds."},
    {"fixture_arm",py_fixture_arm,METH_VARARGS,"Arm the immutable 224-byte native receipt."},
    {"fixture_cleanup_tail",py_fixture_cleanup_tail,METH_NOARGS,
     "Non-returning allocation-free final sample, gate, receipt, close and exit."},
    {NULL,NULL,0,NULL}
};

static struct PyModuleDef module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "_q2_namespace_clone_bridge",
    .m_doc = "Sealed test-only Q2 namespace clone and cleanup bridge.",
    .m_size = -1,
    .m_methods = methods,
};

PyMODINIT_FUNC
PyInit__q2_namespace_clone_bridge(void)
{
    PyObject *created = PyModule_Create(&module);
    if (created == NULL) return NULL;
    BridgeError = PyErr_NewException("_q2_namespace_clone_bridge.BridgeError",NULL,NULL);
    if (BridgeError == NULL || PyModule_AddObjectRef(created,"BridgeError",BridgeError)!=0) {
        Py_XDECREF(BridgeError);Py_DECREF(created);return NULL;
    }
    if (PyModule_AddIntConstant(created,"ABI_VERSION",Q2_BRIDGE_ABI_VERSION)!=0 ||
        PyModule_AddIntConstant(created,"RECEIPT_SIZE",Q2_RECEIPT_SIZE)!=0) {
        Py_DECREF(created);return NULL;
    }
    return created;
}
