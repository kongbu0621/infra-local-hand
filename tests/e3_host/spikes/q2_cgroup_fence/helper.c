/* Test-only fixed Linux/x86_64 cgroup fencing experiment.  Not a job runner. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <linux/audit.h>
#include <linux/capability.h>
#include <linux/filter.h>
#include <linux/sched.h>
#include <linux/seccomp.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/timerfd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <stddef.h>

#if !defined(__x86_64__) || defined(__ILP32__)
#error This experiment supports native Linux x86_64 only
#endif

#define NS INT64_C(1000000000)
#define CAPTURE_LIMIT (128U * 1024U)
#define MAX_EVENTS 128
#define MAX_WORKERS 8
#define MAGIC UINT32_C(0x48303746)
#define CLONE_FLAGS (CLONE_INTO_CGROUP | CLONE_PIDFD)

enum kind { K_ARMED=1, K_REQUEST, K_RECEIVED, K_IDENTITY, K_EXIT,
    K_BARRIER, K_LOST, K_CRASH, K_RELEASE, K_CLOSE, K_BURST };
struct frame { uint32_t magic, version, case_id, seq, kind, reserved;
    int64_t a,b,c,mono,boot; };
_Static_assert(sizeof(struct frame)==64, "fixed frame layout");
struct event { char name[32]; int64_t mono,boot,a,b,c; };
_Static_assert(sizeof(struct event) <= 512, "atomic guardian pipe writes");
struct result {
    struct event events[MAX_EVENTS]; unsigned count;
    unsigned char out[CAPTURE_LIMIT],err[CAPTURE_LIMIT]; size_t out_n,err_n;
    bool out_eof,err_eof,g_eof,g_exit,tree_empty,cleanup_attempted;
    bool cleanup_verified,deadline_met,output_exceeded,have_wait;
    int wait_code; int64_t start_mono,start_boot,end_mono,end_boot;
    const char *status,*reason; int case_id; bool probe;
};
struct groups { int e,g,b,s,w,kill,events,wprocs,sprocs,gprocs; };
static int64_t now(clockid_t c) { struct timespec t; if(clock_gettime(c,&t)) return -1;
    return (int64_t)t.tv_sec*NS+t.tv_nsec; }
static bool ready(int fd) { struct pollfd p={fd,POLLIN|POLLHUP,0};
    return poll(&p,1,0)==1 && (p.revents&(POLLIN|POLLHUP)); }
static bool pipe_done(int fd) { struct pollfd p={fd,POLLIN|POLLHUP,0}; int n=-1;
    return poll(&p,1,0)==1 && (p.revents&POLLHUP) && ioctl(fd,FIONREAD,&n)==0 && n==0; }
static void tiny_pause(void) { struct timespec t={0,2000000}; (void)nanosleep(&t,NULL); }
static void ev(struct result *r,const char *name,int64_t a,int64_t b,int64_t c) {
    if(r->count==MAX_EVENTS) {r->status="UNKNOWN_RETAINED";r->reason="event_limit";return;}
    struct event *e=&r->events[r->count++]; memset(e,0,sizeof(*e));
    (void)snprintf(e->name,sizeof(e->name),"%s",name);
    e->mono=now(CLOCK_MONOTONIC);e->boot=now(CLOCK_BOOTTIME);e->a=a;e->b=b;e->c=c;
}
static bool gev(int fd,const char *name,int64_t a,int64_t b,int64_t c) {
    struct event e; memset(&e,0,sizeof(e)); (void)snprintf(e.name,sizeof(e.name),"%s",name);
    e.mono=now(CLOCK_MONOTONIC);e.boot=now(CLOCK_BOOTTIME);e.a=a;e.b=b;e.c=c;
    return write(fd,&e,sizeof(e))==(ssize_t)sizeof(e);
}
static bool origin_event(int fd,const char *name,const struct frame *f,
                         int64_t a,int64_t b,int64_t c) {
    struct event e;memset(&e,0,sizeof(e));(void)snprintf(e.name,sizeof(e.name),"%s",name);
    e.mono=f->mono;e.boot=f->boot;e.a=a;e.b=b;e.c=c;
    return write(fd,&e,sizeof(e))==(ssize_t)sizeof(e);
}
static int wait_code(int status) { if(WIFEXITED(status))return WEXITSTATUS(status);
    if(WIFSIGNALED(status))return -WTERMSIG(status);
    return -999; }
static bool frame_valid(const struct frame *f,size_t size,int cid,uint32_t seq,
                        int nfds,int flags) {
    if(size!=sizeof(*f) || (flags&(MSG_TRUNC|MSG_CTRUNC)) || f->magic!=MAGIC ||
       f->version!=1 || f->case_id!=(uint32_t)cid || f->seq!=seq ||
       f->reserved || f->kind<K_ARMED || f->kind>K_BURST || f->mono<=0 || f->boot<=0) return false;
    if(f->kind==K_IDENTITY) return nfds==1 && f->a>=1 && f->a<=MAX_WORKERS &&
        f->b>0 && f->c==1;
    return nfds==0;
}
static bool send_frame_at(int fd,int cid,uint32_t *seq,int kind,int64_t a,int64_t b,
                          int64_t c,int passfd,int64_t mono,int64_t boot) {
    struct frame f={MAGIC,1,(uint32_t)cid,++*seq,(uint32_t)kind,0,a,b,c,mono,boot};
    struct iovec iov={&f,sizeof(f)}; struct msghdr msg; memset(&msg,0,sizeof(msg));
    msg.msg_iov=&iov;msg.msg_iovlen=1;
    union { struct cmsghdr align; unsigned char buf[CMSG_SPACE(sizeof(int))]; } u;
    if(passfd>=0) {memset(&u,0,sizeof(u));msg.msg_control=u.buf;msg.msg_controllen=sizeof(u.buf);
        struct cmsghdr *cm=CMSG_FIRSTHDR(&msg);cm->cmsg_level=SOL_SOCKET;cm->cmsg_type=SCM_RIGHTS;
        cm->cmsg_len=CMSG_LEN(sizeof(int));memcpy(CMSG_DATA(cm),&passfd,sizeof(int));}
    return sendmsg(fd,&msg,MSG_NOSIGNAL)==(ssize_t)sizeof(f);
}
static bool send_frame(int fd,int cid,uint32_t *seq,int kind,int64_t a,int64_t b,
                       int64_t c,int passfd) {
    return send_frame_at(fd,cid,seq,kind,a,b,c,passfd,now(CLOCK_MONOTONIC),now(CLOCK_BOOTTIME));
}
/* Return 1=frame, 0=not ready, -1=EOF, -2=invalid. Every received FD is closed
 * on rejection, including excess SCM_RIGHTS delivered in a malformed packet. */
static int recv_frame(int fd,int cid,uint32_t *seq,struct frame *f,int *passfd) {
    union { struct cmsghdr align; unsigned char buf[CMSG_SPACE(sizeof(int)*16)]; } u;
    struct iovec iov={f,sizeof(*f)};struct msghdr m; memset(&m,0,sizeof(m));
    m.msg_iov=&iov;m.msg_iovlen=1;m.msg_control=u.buf;m.msg_controllen=sizeof(u.buf);
    int flags=MSG_DONTWAIT|MSG_CMSG_CLOEXEC;
    ssize_t n=recvmsg(fd,&m,flags);*passfd=-1;
    if(n<0)return (errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR)?0:-2;
    int fds[16],nfds=0;bool ancillary_ok=true;
    for(struct cmsghdr *cm=CMSG_FIRSTHDR(&m);cm;cm=CMSG_NXTHDR(&m,cm)) {
        if(cm->cmsg_level!=SOL_SOCKET || cm->cmsg_type!=SCM_RIGHTS ||
           cm->cmsg_len<CMSG_LEN(0)) {ancillary_ok=false;continue;}
        size_t sz=cm->cmsg_len-CMSG_LEN(0);
        if(sz%sizeof(int))ancillary_ok=false;
        for(size_t j=0;j+sizeof(int)<=sz;j+=sizeof(int)) {
            int v;memcpy(&v,(unsigned char*)CMSG_DATA(cm)+j,sizeof(v));
            if(nfds<16)fds[nfds++]=v;else{close(v);ancillary_ok=false;}
        }
    }
    if(n==0){
        for(int j=0;j<nfds;j++)close(fds[j]);
        struct pollfd peer={fd,POLLHUP,0};
        return nfds==0 && ancillary_ok && poll(&peer,1,0)==1 && (peer.revents&POLLHUP)?-1:-2;
    }
    bool ok=ancillary_ok && frame_valid(f,(size_t)n,cid,*seq+1,nfds,m.msg_flags);
    if(!ok){for(int j=0;j<nfds;j++)close(fds[j]);return -2;}
    ++*seq;if(nfds==1)*passfd=fds[0];return 1;
}
static int read_at(int fd,char *buf,size_t cap) {
    if(lseek(fd,0,SEEK_SET)<0)return -1;
    ssize_t n=read(fd,buf,cap-1);
    if(n<0)return -1;
    buf[n]=0;return (int)n;
}
static int members(int fd,pid_t wanted) {char buf[2048]; if(read_at(fd,buf,sizeof(buf))<0)return -1;
    char *p=buf,*end;int count=0;bool found=false;
    while(*p){errno=0;long n=strtol(p,&end,10);if(end==p||errno||n<=0)return -1;
        count++;if(n==wanted)found=true;p=end;while(*p=='\n'||*p==' ')p++;}
    return wanted>0?(found?1:0):count;
}
static bool empty_tree(int fd) { char b[256];return read_at(fd,b,sizeof(b))>=0 &&
    (strncmp(b,"populated 0\n",12)==0 || strstr(b,"\npopulated 0\n")!=NULL); }
static bool do_kill(int fd) {return pwrite(fd,"1",1,0)==1;}
static int clone_into(int group,int *pidfd) {
    struct clone_args args;memset(&args,0,sizeof(args));args.flags=CLONE_FLAGS;
    args.pidfd=(uint64_t)(uintptr_t)pidfd;args.cgroup=(uint64_t)group;
    args.exit_signal=SIGCHLD;return (int)syscall(SYS_clone3,&args,sizeof(args));
}
static bool original_pidfd(int fd,pid_t pid) {char path[64],buf[512];
    (void)snprintf(path,sizeof(path),"/proc/self/fdinfo/%d",fd);
    int f=open(path,O_RDONLY|O_CLOEXEC);if(f<0)return false;
    ssize_t n=read(f,buf,sizeof(buf)-1);close(f);if(n<0)return false;buf[n]=0;
    char *p=strstr(buf,"Pid:\t");if(!p)return false;
    return strtol(p+5,NULL,10)==pid;
}
static const char *status_value(const char *buf,const char *key) {
    size_t n=strlen(key);const char *line=buf;
    while(line&&*line){if(strncmp(line,key,n)==0&&line[n]==':')return line+n+1;
        line=strchr(line,'\n');if(line)line++;}
    return NULL;
}
static bool zero_cap(const char *buf,const char *key) {
    const char *p=status_value(buf,key);char *end;errno=0;
    if(!p)return false;
    unsigned long long v=strtoull(p,&end,16);
    return !errno&&end!=p&&v==0&&(*end=='\n'||*end=='\0');
}
static bool process_reduced(pid_t pid,int pidfd,uid_t uid,gid_t gid,int tx) {
    if(ready(pidfd))return false;
    char path[64],buf[8192];(void)snprintf(path,sizeof(path),"/proc/%d/status",pid);
    int fd=open(path,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);if(fd<0)return false;
    ssize_t size=read(fd,buf,sizeof(buf)-1);close(fd);
    if(size<=0||size==(ssize_t)sizeof(buf)-1||ready(pidfd))return false;
    buf[size]=0;
    const char *u=status_value(buf,"Uid"),*g=status_value(buf,"Gid"),*groups=status_value(buf,"Groups");
    const char *nnp=status_value(buf,"NoNewPrivs"),*sec=status_value(buf,"Seccomp");
    unsigned ua[4],ga[4];
    if(!u||!g||!groups||!nnp||!sec||sscanf(u,"%u %u %u %u",&ua[0],&ua[1],&ua[2],&ua[3])!=4||
       sscanf(g,"%u %u %u %u",&ga[0],&ga[1],&ga[2],&ga[3])!=4)return false;
    for(int i=0;i<4;i++)if(ua[i]!=uid||ga[i]!=gid)return false;
    while(*groups==' '||*groups=='\t')groups++;
    bool caps=zero_cap(buf,"CapEff")&&zero_cap(buf,"CapPrm")&&zero_cap(buf,"CapInh");
    bool bnd=zero_cap(buf,"CapBnd"),ambient=zero_cap(buf,"CapAmb");
    bool ok=*groups=='\n'&&strtol(nnp,NULL,10)==1&&strtol(sec,NULL,10)==2&&caps&&bnd&&ambient;
    (void)gev(tx,"s_credentials",uid,gid,*groups=='\n');
    (void)gev(tx,"s_capabilities",caps?0:1,bnd?0:1,ambient?0:1);
    (void)gev(tx,"s_restrictions",strtol(nnp,NULL,10),strtol(sec,NULL,10),ok);
    return ok;
}
static void close_except(int a,int b,int c,int d,int e) {
    int keep[5]={a,b,c,d,e};
    for(int i=0;i<5;i++)for(int j=i+1;j<5;j++)if(keep[j]<keep[i]){
        int t=keep[i];keep[i]=keep[j];keep[j]=t;
    }
    unsigned first=0;
    for(int i=0;i<5;i++)if(keep[i]>=0){
        unsigned k=(unsigned)keep[i];if(k<first)continue;
        if(k>first&&syscall(SYS_close_range,first,k-1,0))_exit(120);
        first=k+1;
    }
    if(syscall(SYS_close_range,first,UINT32_MAX,0))_exit(120);
}
static bool drop_privileges(uid_t uid,gid_t gid) {
    struct __user_cap_header_struct h={_LINUX_CAPABILITY_VERSION_3,0};
    struct __user_cap_data_struct d[2];memset(d,0,sizeof(d));
    if(prctl(PR_CAP_AMBIENT,PR_CAP_AMBIENT_CLEAR_ALL,0,0,0))return false;
    for(int cap=0;cap<=CAP_LAST_CAP;cap++)
        if(prctl(PR_CAPBSET_DROP,cap,0,0,0))return false;
    if(setgroups(0,NULL)||setresgid(gid,gid,gid)||setresuid(uid,uid,uid)||
       syscall(SYS_capset,&h,d)||prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0))return false;
    memset(d,0,sizeof(d));if(syscall(SYS_capget,&h,d))return false;
    return getuid()==uid && geteuid()==uid && getgid()==gid && getegid()==gid &&
        getgroups(0,NULL)==0 && !(d[0].effective|d[1].effective|d[0].permitted|
        d[1].permitted|d[0].inheritable|d[1].inheritable);
}
/* Fixed syscall allowlist; write and IPC are additionally bound to original
 * registered FDs. A trusted launcher holds exactly one clone target FD. */
static unsigned build_filter(struct sock_filter *f,int ctl,int eventfd,bool launcher) {
    unsigned n=0;
#define ADD(x) do{f[n++]=(struct sock_filter)x;}while(0)
#define ST(code,k) ADD(BPF_STMT((code),(k)))
#define JP(code,k,t,z) ADD(BPF_JUMP((code),(k),(t),(z)))
#define ALLOW_NR(nr) do{JP(BPF_JMP|BPF_JEQ|BPF_K,(nr),0,1);ST(BPF_RET|BPF_K,SECCOMP_RET_ALLOW);}while(0)
    ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,arch));
    JP(BPF_JMP|BPF_JEQ|BPF_K,AUDIT_ARCH_X86_64,1,0);ST(BPF_RET|BPF_K,SECCOMP_RET_KILL_PROCESS);
    ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr));
    JP(BPF_JMP|BPF_JSET|BPF_K,0x40000000,0,1);ST(BPF_RET|BPF_K,SECCOMP_RET_KILL_PROCESS);
    ALLOW_NR(SYS_exit);ALLOW_NR(SYS_exit_group);ALLOW_NR(SYS_close);
    ALLOW_NR(SYS_clock_gettime);ALLOW_NR(SYS_clock_nanosleep);ALLOW_NR(SYS_nanosleep);
    ALLOW_NR(SYS_rt_sigreturn);ALLOW_NR(SYS_rt_sigprocmask);ALLOW_NR(SYS_rt_sigaction);
    ALLOW_NR(SYS_getpid);ALLOW_NR(SYS_getppid);ALLOW_NR(SYS_getuid);ALLOW_NR(SYS_geteuid);
    ALLOW_NR(SYS_getgid);ALLOW_NR(SYS_getegid);ALLOW_NR(SYS_getgroups);
    ALLOW_NR(SYS_wait4);ALLOW_NR(SYS_waitid);ALLOW_NR(SYS_poll);ALLOW_NR(SYS_ppoll);
    /* worker fork is exactly SIGCHLD and inherits its existing cgroup. */
    JP(BPF_JMP|BPF_JEQ|BPF_K,SYS_clone,0,8);
    ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[0])+4);
    JP(BPF_JMP|BPF_JEQ|BPF_K,0,1,0);
    ST(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM);
    ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[0]));
    JP(BPF_JMP|BPF_JEQ|BPF_K,SIGCHLD,0,1);ST(BPF_RET|BPF_K,SECCOMP_RET_ALLOW);
    ST(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM);
    ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr));
    if(launcher){ALLOW_NR(SYS_clone3);ALLOW_NR(SYS_seccomp);}
    JP(BPF_JMP|BPF_JEQ|BPF_K,SYS_write,0,(eventfd>=0?8:6));
    ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[0]));
    JP(BPF_JMP|BPF_JEQ|BPF_K,STDOUT_FILENO,0,1);ST(BPF_RET|BPF_K,SECCOMP_RET_ALLOW);
    JP(BPF_JMP|BPF_JEQ|BPF_K,STDERR_FILENO,0,1);ST(BPF_RET|BPF_K,SECCOMP_RET_ALLOW);
    if(eventfd>=0){JP(BPF_JMP|BPF_JEQ|BPF_K,(unsigned)eventfd,0,1);ST(BPF_RET|BPF_K,SECCOMP_RET_ALLOW);}
    ST(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM);
    ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr));
    if(ctl>=0){
        JP(BPF_JMP|BPF_JEQ|BPF_K,SYS_sendmsg,1,0);
        JP(BPF_JMP|BPF_JEQ|BPF_K,SYS_recvmsg,0,5);
        ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[0]));
        JP(BPF_JMP|BPF_JEQ|BPF_K,(unsigned)ctl,0,1);ST(BPF_RET|BPF_K,SECCOMP_RET_ALLOW);
        ST(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM);
        ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr));
    }
    /* Read-only prctl queries used for recorded NNP/filter facts. */
    JP(BPF_JMP|BPF_JEQ|BPF_K,SYS_prctl,0,6);
    ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,args[0]));
    JP(BPF_JMP|BPF_JEQ|BPF_K,PR_GET_NO_NEW_PRIVS,1,0);
    JP(BPF_JMP|BPF_JEQ|BPF_K,PR_GET_SECCOMP,0,1);ST(BPF_RET|BPF_K,SECCOMP_RET_ALLOW);
    ST(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM);
    ST(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr));
    ST(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EPERM);
    return n;
#undef ALLOW_NR
#undef JP
#undef ST
#undef ADD
}
static bool install_filter(int ctl,int eventfd,bool launcher) {
    struct sock_filter f[192];unsigned n=build_filter(f,ctl,eventfd,launcher);
    struct sock_fprog p={(unsigned short)n,f};
    return syscall(SYS_seccomp,SECCOMP_SET_MODE_FILTER,0,&p)==0;
}
static uint32_t evaluate_filter(const struct sock_filter *f,unsigned count,int nr,
                                uint32_t arch,uint64_t arg0) {
    struct seccomp_data data;memset(&data,0,sizeof(data));
    data.nr=nr;data.arch=arch;data.args[0]=arg0;uint32_t acc=0;
    for(unsigned ip=0;ip<count;ip++){
        const struct sock_filter *x=&f[ip];
        if(x->code==(BPF_LD|BPF_W|BPF_ABS)){
            if(x->k+sizeof(acc)>sizeof(data))return UINT32_MAX;
            memcpy(&acc,(unsigned char*)&data+x->k,sizeof(acc));
        }else if(x->code==(BPF_JMP|BPF_JEQ|BPF_K))ip+=(acc==x->k)?x->jt:x->jf;
        else if(x->code==(BPF_JMP|BPF_JSET|BPF_K))ip+=(acc&x->k)?x->jt:x->jf;
        else if(x->code==(BPF_RET|BPF_K))return x->k;
        else return UINT32_MAX;
    }
    return UINT32_MAX;
}
static void worker(int cid,int ctl,int wfd) {
    close(ctl);close(wfd);
    if(!install_filter(-1,-1,false))_exit(121);
    static const char out[]="fixed worker stdout\n",err[]="fixed worker stderr\n";
    if(write(1,out,sizeof(out)-1)!=(ssize_t)(sizeof(out)-1)||
       write(2,err,sizeof(err)-1)!=(ssize_t)(sizeof(err)-1))_exit(122);
    if(cid==1){struct timespec t={0,250000000};(void)nanosleep(&t,NULL);_exit(0);}
    if(cid==5){
        for(int j=0;j<7;j++){
            long p=syscall(SYS_clone,SIGCHLD,0,0,0,0);
            if(p<0)_exit(123);
            if(p==0){for(;;)tiny_pause();}
            static const char mark[]="fixed fork child\n";if(write(1,mark,sizeof(mark)-1)!=(ssize_t)(sizeof(mark)-1))_exit(154);
            struct timespec t={4,0};(void)nanosleep(&t,NULL);
        }
    }
    for(;;)tiny_pause();
}
static bool before_stop(int64_t mono,int64_t boot) {
    int64_t m=now(CLOCK_MONOTONIC),b=now(CLOCK_BOOTTIME);
    return m>=mono&&b>=boot&&m<mono+17*NS&&b<boot+17*NS;
}
static void launcher(int cid,struct groups *cg,uid_t uid,gid_t gid,int ctl,int op,int ep,
                     int64_t mono,int64_t boot) {
    if(dup2(op,1)<0||dup2(ep,2)<0)_exit(124);
    close_except(1,2,ctl,cg->w,-1);
    if(!drop_privileges(uid,gid)||!install_filter(ctl,-1,true))_exit(125);
    uint32_t sent=0,received=0;
    if(!send_frame(ctl,cid,&sent,K_ARMED,getpid(),getuid(),
                   prctl(PR_GET_SECCOMP,0,0,0,0),-1))_exit(126);
    pid_t pids[MAX_WORKERS]={0};int made=0,finished=0;
    for(;;){
        struct frame f;int pfd=-1;int r=recv_frame(ctl,cid,&received,&f,&pfd);
        if(r<0)_exit(127);
        if(r==1){
            if(pfd>=0){close(pfd);_exit(128);}
            if(!before_stop(mono,boot))_exit(155);
            if(cid==4 && made==1 && f.kind==K_RELEASE && f.a==1 && f.b==0 && f.c==0){
                (void)send_frame(ctl,cid,&sent,K_CRASH,88,0,0,-1);_exit(88);
            }
            if(f.kind!=K_REQUEST||f.a!=1||f.b!=0||f.c!=0||made)_exit(129);
            if(!send_frame(ctl,cid,&sent,K_RECEIVED,f.seq,0,0,-1))_exit(130);
            if(cid==2){
                if(!send_frame(ctl,cid,&sent,K_BARRIER,f.seq,0,0,-1))_exit(131);
                /* No clone after this barrier in C2. Release is a late negative. */
                for(;;){struct frame x;int fd=-1;int q=recv_frame(ctl,cid,&received,&x,&fd);
                    if(fd>=0)close(fd);
                    if(q<0)_exit(132);
                    if(q>0)_exit(133);
                    tiny_pause();}
            }
            int total=cid==1?2:1;
            for(int j=0;j<total;j++){
                if(!before_stop(mono,boot))_exit(156);
                int fd=-1;int p=clone_into(cg->w,&fd);
                int64_t clone_mono=now(CLOCK_MONOTONIC),clone_boot=now(CLOCK_BOOTTIME);
                if(p<0){(void)send_frame(ctl,cid,&sent,K_EXIT,j+1,-1000-errno,0,-1);_exit(134);}
                if(p==0)worker(cid,ctl,cg->w);
                pids[made]=p;made++;
                if(cid==3){(void)send_frame_at(ctl,cid,&sent,K_LOST,1,p,1,-1,clone_mono,clone_boot);
                    close(fd);for(;;)tiny_pause();}
                if(!send_frame_at(ctl,cid,&sent,K_IDENTITY,j+1,p,1,fd,clone_mono,clone_boot))_exit(135);
                close(fd);
            }
        }
        if(cid==1 && made){for(int j=0;j<made;j++)if(pids[j]>0){int st;
            pid_t p=waitpid(pids[j],&st,WNOHANG);if(p==pids[j]){
                if(!send_frame(ctl,cid,&sent,K_EXIT,j+1,wait_code(st),1,-1))_exit(136);
                pids[j]=0;finished++;}}
            (void)finished;
        }
        tiny_pause();
    }
}
static int timer_abs(clockid_t clock,int64_t deadline) {
    int fd=timerfd_create(clock,TFD_CLOEXEC|TFD_NONBLOCK);if(fd<0)return -1;
    struct itimerspec v;memset(&v,0,sizeof(v));v.it_value.tv_sec=deadline/NS;
    v.it_value.tv_nsec=deadline%NS;if(timerfd_settime(fd,TFD_TIMER_ABSTIME,&v,NULL)){
        close(fd);return -1;}return fd;
}
static void guardian(int cid,struct groups *cg,uid_t uid,gid_t gid,int tx,int ctl_t,
                     int ctl_s,int ctl_child,int op,int ep,int outread,int errread) {
    (void)prctl(PR_SET_CHILD_SUBREAPER,1,0,0,0);
    int64_t mono=now(CLOCK_MONOTONIC),boot=now(CLOCK_BOOTTIME);
    int mt=timer_abs(CLOCK_MONOTONIC,mono+17*NS),bt=timer_abs(CLOCK_BOOTTIME,boot+17*NS);
    if(mt<0||bt<0){(void)gev(tx,"native_error",1,errno,0);_exit(140);}
    /* Set the event origins to precisely the epoch used by the two clocks. */
    struct event arm;memset(&arm,0,sizeof(arm));strcpy(arm.name,"g_armed");
    arm.mono=mono;arm.boot=boot;arm.a=mono+20*NS;arm.b=boot+20*NS;arm.c=mono+17*NS;
    if(write(tx,&arm,sizeof(arm))!=(ssize_t)sizeof(arm))_exit(141);
    int sfd=-1;int sp=clone_into(cg->s,&sfd);
    if(sp<0){(void)gev(tx,"native_error",2,errno,0);_exit(142);}
    if(sp==0){close(ctl_s);launcher(cid,cg,uid,gid,ctl_child,op,ep,mono,boot);_exit(143);}
    close(ctl_child);close(op);close(ep);
    if(!gev(tx,"s_created",sp,3,members(cg->sprocs,sp)==1))_exit(144);
    uint32_t ss=0,sr=0,tr=0;int frames=0,identities=0,exits=0,late=0;
    int wfds[MAX_WORKERS];bool wexit[MAX_WORKERS];
    for(int i=0;i<MAX_WORKERS;i++){wfds[i]=-1;wexit[i]=false;}
    bool closed=false,s_exited=false,ctl_eof=false,fenced=false,barrier=false,lost=false;
    bool seen_crash=false,streams_recorded=false,tree_recorded=false,requested=false;
    bool payload_seen=false,crash_released=false;
    int close_reason=0;int64_t lastmono=mono,lastboot=boot;
    for(;;){
        int64_t m=now(CLOCK_MONOTONIC),b=now(CLOCK_BOOTTIME);
        if(m<lastmono||b<lastboot||m>mono+20*NS||b>boot+20*NS){
            (void)gev(tx,"native_error",3,0,0);(void)do_kill(cg->kill);_exit(145);}
        lastmono=m;lastboot=b;
        for(int limit=0;limit<16;limit++){
            struct frame f;int fd=-1;int q=recv_frame(ctl_s,cid,&sr,&f,&fd);
            if(q==0)break;
            if(q==-1){ctl_eof=true;break;}
            if(q<0||++frames>128){if(fd>=0)close(fd);close_reason=90;closed=true;
                (void)gev(tx,"protocol_error",q,frames,0);(void)do_kill(cg->kill);break;}
            if(f.kind==K_ARMED&&!requested&&!closed){
                if(f.a!=sp||f.b!=uid||f.c!=2||!process_reduced(sp,sfd,uid,gid,tx)){
                    close_reason=91;closed=true;(void)do_kill(cg->kill);}
                else {(void)gev(tx,"s_armed",f.a,f.b,f.c);
                    if(!before_stop(mono,boot)){(void)gev(tx,"native_error",5,0,0);_exit(157);}
                    (void)gev(tx,"request_sent",ss+1,1,0);
                    requested=send_frame(ctl_s,cid,&ss,K_REQUEST,1,0,0,-1);
                    if(!requested)_exit(162);}
            }else if(f.kind==K_RECEIVED){(void)origin_event(tx,"request_received",&f,f.a,0,0);}
            else if(f.kind==K_IDENTITY){
                int slot=(int)f.a-1;bool valid=slot>=0&&slot<MAX_WORKERS&&wfds[slot]<0&&
                    original_pidfd(fd,(pid_t)f.b);int entry=members(cg->wprocs,(pid_t)f.b);
                (void)gev(tx,"worker_request",f.a,1,1);
                (void)origin_event(tx,"worker_created",&f,f.a,f.b,1);
                (void)gev(tx,"worker_receipt",f.a,f.b,1);
                (void)gev(tx,"worker_pidfd",f.a,1,valid);
                (void)gev(tx,"worker_identity",f.a,f.b,entry==1);
                if(!valid){close(fd);close_reason=92;closed=true;(void)do_kill(cg->kill);}
                else{wfds[slot]=fd;fd=-1;identities++;}
            }else if(f.kind==K_EXIT){int slot=(int)f.a-1;
                bool valid=slot>=0&&slot<MAX_WORKERS&&wfds[slot]>=0&&ready(wfds[slot]);
                (void)gev(tx,"worker_exit",f.a,f.b,valid&&f.c==1);
                if(valid&&!wexit[slot]){wexit[slot]=true;exits++;}
                if(f.b<0){close_reason=93;closed=true;(void)do_kill(cg->kill);}
            }else if(f.kind==K_BARRIER){barrier=true;(void)gev(tx,"barrier_ready",f.a,0,0);}
            else if(f.kind==K_LOST){lost=true;(void)gev(tx,"worker_request",f.a,1,1);
                (void)origin_event(tx,"worker_created",&f,f.a,f.b,1);
                (void)gev(tx,"lost_reply",f.a,1,0);}
            else if(f.kind==K_CRASH){seen_crash=true;(void)gev(tx,"s_crash",f.a,0,0);}
            else {(void)gev(tx,"protocol_error",f.kind,0,0);close_reason=94;closed=true;(void)do_kill(cg->kill);}
            if(fd>=0)close(fd);
        }
        if(!s_exited&&ready(sfd)){int st;pid_t q=waitpid(sp,&st,WNOHANG);
            if(q==sp){s_exited=true;(void)gev(tx,"s_exit",wait_code(st),1,0);}
        }
        if(cid==6&&identities==1&&!closed){(void)gev(tx,"g_crash",86,0,0);_exit(86);}
        bool wantclose=(cid==1&&exits==2)||(cid==2&&barrier)||(cid==3&&lost)||
            (cid==4&&seen_crash&&s_exited)||m>=mono+17*NS||b>=boot+17*NS;
        if(!closed && s_exited && !(cid==4&&seen_crash))wantclose=true;
        if(!closed && wantclose){
            if(cid==4)(void)gev(tx,"streams_held",!pipe_done(outread),!pipe_done(errread),members(cg->wprocs,0));
            if(cid==5){int count=members(cg->wprocs,0);bool alive=wfds[0]>=0&&!ready(wfds[0]);
                (void)gev(tx,"burst_ready",count-1,alive,MAX_WORKERS-count);
                (void)gev(tx,"burst_at_close",count-1,alive,MAX_WORKERS-count);}
            closed=true;close_reason=cid;(void)gev(tx,"close_requested",close_reason,0,0);
            if(!do_kill(cg->kill)){(void)gev(tx,"native_error",4,errno,0);_exit(146);}
            (void)gev(tx,"b_kill",1,0,0);
        }
        for(int limit=0;limit<4;limit++){
            struct frame f;int fd=-1;int q=recv_frame(ctl_t,cid,&tr,&f,&fd);
            if(fd>=0)close(fd);
            if(q==0||q==-1)break;
            if(q>0&&cid==4&&!closed&&f.kind==K_BURST&&f.a==1&&f.b==1&&f.c==0){
                payload_seen=true;(void)gev(tx,"payload_confirmed",1,1,0);continue;
            }
            if(q<0||!closed||(f.kind!=K_RELEASE&&f.kind!=K_REQUEST)){
                (void)gev(tx,"protocol_error",95,q,0);close_reason=95;break;}
            late++;(void)gev(tx,"late_rejected",f.kind,f.seq,1);
        }
        if(cid==4&&!closed&&payload_seen&&identities==1&&!crash_released){
            if(!before_stop(mono,boot))_exit(158);
            crash_released=send_frame(ctl_s,cid,&ss,K_RELEASE,1,0,0,-1);
            if(!crash_released)_exit(159);
        }
        if(ss+sr+tr>128){(void)do_kill(cg->kill);_exit(160);}
        if(closed){bool tree=empty_tree(cg->events);
            bool eof=pipe_done(outread)&&pipe_done(errread);
            if(tree&&!tree_recorded){tree_recorded=true;(void)gev(tx,"b_empty",1,0,0);}
            if(eof&&!streams_recorded){streams_recorded=true;(void)gev(tx,"streams_eof",1,1,0);}
            if(s_exited&&tree&&eof&&ctl_eof&&(cid!=2||late==2)){
                (void)gev(tx,"control_eof",1,0,0);
                fenced=close_reason<90;(void)gev(tx,"fenced",fenced,0,0);
                (void)gev(tx,"g_summary",cid!=3&&identities==(cid==1?2:cid==2?0:1),fenced,1);
                for(int i=0;i<MAX_WORKERS;i++)if(wfds[i]>=0)close(wfds[i]);
                close(sfd);close(mt);close(bt);_exit(fenced?0:147);
            }
        }
        tiny_pause();
    }
}
static int dir_open(int parent,const char *name) {return openat(parent,name,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);}
static bool groups_open(const char *path,struct groups *cg) {
    memset(cg,0xff,sizeof(*cg));cg->e=open(path,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if(cg->e<0)return false;
    cg->g=dir_open(cg->e,"G");cg->b=dir_open(cg->e,"B");
    if(cg->g<0||cg->b<0)return false;
    cg->s=dir_open(cg->b,"S");cg->w=dir_open(cg->b,"W");
    if(cg->s<0||cg->w<0)return false;
    cg->kill=openat(cg->b,"cgroup.kill",O_WRONLY|O_NOFOLLOW|O_CLOEXEC);
    cg->events=openat(cg->b,"cgroup.events",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    cg->wprocs=openat(cg->w,"cgroup.procs",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    cg->sprocs=openat(cg->s,"cgroup.procs",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    cg->gprocs=openat(cg->g,"cgroup.procs",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    return cg->kill>=0&&cg->events>=0&&cg->wprocs>=0&&cg->sprocs>=0&&cg->gprocs>=0;
}
static void capture(int fd,unsigned char *buf,size_t *length,bool *eof,struct result *r) {
    for(int j=0;j<8;j++){unsigned char chunk[4096];ssize_t n=read(fd,chunk,sizeof(chunk));
        if(n==0){*eof=true;return;}if(n<0){if(errno!=EAGAIN&&errno!=EINTR)r->reason="capture_error";return;}
        size_t total=r->out_n+r->err_n;
        if((size_t)n>CAPTURE_LIMIT-total){r->output_exceeded=true;return;}
        memcpy(buf+*length,chunk,(size_t)n);*length+=(size_t)n;
    }
}
static void probe_child(struct groups *cg,uid_t uid,gid_t gid,int tx) {
    close_except(tx,-1,-1,-1,-1);
    if(!drop_privileges(uid,gid))_exit(150);
    struct __user_cap_header_struct h={_LINUX_CAPABILITY_VERSION_3,0};
    struct __user_cap_data_struct caps[2];memset(caps,0,sizeof(caps));
    if(syscall(SYS_capget,&h,caps))_exit(161);
    (void)gev(tx,"probe_capabilities",caps[0].effective|caps[1].effective,
        caps[0].permitted|caps[1].permitted,caps[0].inheritable|caps[1].inheritable);
    if(!install_filter(-1,tx,false))_exit(150);
    (void)cg;
    (void)gev(tx,"probe_armed",getuid(),prctl(PR_GET_NO_NEW_PRIVS,0,0,0,0),prctl(PR_GET_SECCOMP,0,0,0,0));
    int calls[]={SYS_socket,SYS_connect,SYS_openat,SYS_execve,SYS_unshare,SYS_setns,
        SYS_ptrace,SYS_process_vm_writev,SYS_mount,SYS_clone3};
    bool ok=true;
    for(unsigned i=0;i<sizeof(calls)/sizeof(calls[0]);i++){
        errno=0;long q=syscall(calls[i],-1,0,0,0,0,0);int en=errno;
        bool denied=q==-1&&en==EPERM;ok=ok&&denied;
        (void)gev(tx,"probe_denial",calls[i],en,denied);
    }
    (void)gev(tx,"probe_ready",ok,0,0);for(;;)tiny_pause();
}
static void events_read(int fd,struct result *r,unsigned char *partial,size_t *used) {
    for(int k=0;k<16;k++){
        ssize_t n=read(fd,partial+*used,sizeof(struct event)-*used);
        if(n==0){r->g_eof=true;if(*used){r->status="UNKNOWN_RETAINED";r->reason="truncated_guardian_event";}return;}
        if(n<0){if(errno!=EAGAIN&&errno!=EINTR){r->status="UNKNOWN_RETAINED";r->reason="guardian_stream_error";}return;}
        *used+=(size_t)n;if(*used==sizeof(struct event)){
            struct event e;memcpy(&e,partial,sizeof(e));*used=0;
            if(!memchr(e.name,0,sizeof(e.name))||r->count==MAX_EVENTS){r->status="UNKNOWN_RETAINED";r->reason="guardian_event_invalid";return;}
            r->events[r->count++]=e;
        }
    }
}
static bool has_event(const struct result *r,const char *name) {
    for(unsigned i=0;i<r->count;i++)if(strcmp(r->events[i].name,name)==0)return true;
    return false;
}
static void native_run(struct result *r,struct groups *cg,uid_t uid,gid_t gid) {
    int op[2],ep[2],gp[2],st[2],ts[2];
    if(pipe2(op,O_CLOEXEC|O_NONBLOCK)||pipe2(ep,O_CLOEXEC|O_NONBLOCK)||
       pipe2(gp,O_CLOEXEC|O_NONBLOCK)||socketpair(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0,st)||
       socketpair(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0,ts)){
        r->reason="channel_setup";return;}
    if(prctl(PR_SET_CHILD_SUBREAPER,1,0,0,0)){r->reason="subreaper_setup";return;}
    int gfd=-1;int pid=clone_into(r->probe?cg->w:cg->g,&gfd);
    if(pid<0){r->status="UNSUPPORTED";r->reason="clone3_atomic_unavailable";
        ev(r,"clone_error",errno,0,0);return;}
    if(pid==0){close(gp[0]);close(ts[0]);
        if(r->probe)probe_child(cg,uid,gid,gp[1]);
        guardian(r->case_id,cg,uid,gid,gp[1],ts[1],st[0],st[1],op[1],ep[1],op[0],ep[0]);_exit(151);}
    close(gp[1]);close(op[1]);close(ep[1]);close(st[0]);close(st[1]);close(ts[1]);
    ev(r,r->probe?"probe_created":"g_created",pid,3,members(r->probe?cg->wprocs:cg->gprocs,pid)==1);
    ev(r,"stream_originals",2,1,1);
    unsigned char partial[sizeof(struct event)];size_t used=0;uint32_t late_seq=0;
    bool late_sent=false,killed=false,payload_reported=false;int64_t stop=r->start_mono+20*NS;
    for(;;){
        capture(op[0],r->out,&r->out_n,&r->out_eof,r);
        capture(ep[0],r->err,&r->err_n,&r->err_eof,r);
        events_read(gp[0],r,partial,&used);
        if(!r->probe&&r->case_id==2&&!late_sent&&has_event(r,"close_requested")){
            ev(r,"late_attempt",2,1,1);
            bool a=send_frame(ts[0],2,&late_seq,K_RELEASE,0,0,0,-1);
            bool b=send_frame(ts[0],2,&late_seq,K_REQUEST,1,0,0,-1);
            ev(r,"late_send_result",a,b,a&&b);late_sent=true;
        }
        if(!r->probe&&r->case_id==4&&!payload_reported&&r->out_n&&r->err_n){
            ev(r,"payload_started",(int64_t)r->out_n,(int64_t)r->err_n,1);
            payload_reported=send_frame(ts[0],4,&late_seq,K_BURST,1,1,0,-1);
            if(!payload_reported){r->status="UNKNOWN_RETAINED";r->reason="payload_notice_failed";}
        }
        if(r->probe&&!killed&&(has_event(r,"probe_ready")||
            now(CLOCK_MONOTONIC)>=r->start_mono+17*NS||now(CLOCK_BOOTTIME)>=r->start_boot+17*NS)){
            r->cleanup_attempted=true;killed=do_kill(cg->kill);ev(r,"probe_kill",killed,0,0);
        }
        if(!r->g_exit&&ready(gfd)){int stcode;pid_t p=waitpid(pid,&stcode,WNOHANG);
            if(p==pid){r->g_exit=true;r->have_wait=true;r->wait_code=wait_code(stcode);
                ev(r,r->probe?"t_probe_exit":"t_g_exit",r->wait_code,1,0);}
        }
        if(!r->probe&&r->g_exit&&r->case_id==6&&!killed){r->cleanup_attempted=true;
            killed=do_kill(cg->kill);ev(r,"t_cleanup",killed,0,0);}
        bool tree=empty_tree(cg->events);r->tree_empty=tree;
        if(r->g_exit&&r->g_eof&&r->out_eof&&r->err_eof&&tree)break;
        int64_t m=now(CLOCK_MONOTONIC),b=now(CLOCK_BOOTTIME);
        if(r->output_exceeded||m>=stop||b>=r->start_boot+20*NS){
            r->status="UNKNOWN_RETAINED";r->reason=r->output_exceeded?"capture_limit":"native_deadline";
            r->cleanup_attempted=true;(void)do_kill(cg->kill);
            (void)syscall(SYS_pidfd_send_signal,gfd,SIGKILL,NULL,0);break;
        }
        if(r->g_exit&&!tree&&!killed&&r->case_id!=6){r->cleanup_attempted=true;
            killed=do_kill(cg->kill);ev(r,"t_cleanup",killed,0,0);
            r->status="UNKNOWN_RETAINED";r->reason="guardian_lost_unexpectedly";}
        tiny_pause();
    }
    /* No fresh observation deadline here. Late cleanup remains unproven; outer
     * fixture may clean exact registered objects but cannot invent our seal. */
    r->tree_empty=empty_tree(cg->events);
    r->cleanup_verified=r->tree_empty&&r->g_exit&&r->g_eof&&r->out_eof&&r->err_eof;
    ev(r,"t_b_empty",r->tree_empty,0,0);
    ev(r,"t_streams_eof",r->out_eof,r->err_eof,0);
    ev(r,"t_cleanup_verified",r->tree_empty,r->out_eof&&r->err_eof,r->g_exit&&r->g_eof);
    if(r->probe && (!has_event(r,"probe_ready") || r->wait_code!=-SIGKILL)){
        r->status="UNSUPPORTED";r->reason="probe_not_qualified";
        if(!r->cleanup_verified)r->status="UNKNOWN_RETAINED";
    }
    if(!r->probe && (r->case_id==3||r->case_id==6) &&
       strcmp(r->status,"OBSERVED")==0 && strcmp(r->reason,"fixed_case_observed")==0){
        r->status="UNKNOWN_RETAINED";
        r->reason=r->case_id==3?"expected_lost_identity":"expected_guardian_loss";
    }
    while(waitpid(-1,NULL,WNOHANG)>0){}
    close(gfd);close(op[0]);close(ep[0]);close(gp[0]);close(ts[0]);
}
static void b64(const unsigned char *p,size_t n) {
    static const char table[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    putchar('"');for(size_t i=0;i<n;i+=3){uint32_t v=(uint32_t)p[i]<<16;
        if(i+1<n)v|=(uint32_t)p[i+1]<<8;
        if(i+2<n)v|=p[i+2];
        putchar(table[(v>>18)&63]);putchar(table[(v>>12)&63]);
        putchar(i+1<n?table[(v>>6)&63]:'=');putchar(i+2<n?table[v&63]:'=');}putchar('"');
}
#define BOOL(x) ((x)?"true":"false")
static void output(const struct result *r) {
    char cid[16];if(r->probe)strcpy(cid,"PROBE");else(void)snprintf(cid,sizeof(cid),"C%d",r->case_id);
    printf("{\"schema_version\":1,\"kind\":\"%s\",\"case_id\":\"%s\",\"status\":\"%s\",\"reason\":\"%s\",",
        r->probe?"probe":"case",cid,r->status,r->reason);
    printf("\"start_mono_ns\":%lld,\"start_boot_ns\":%lld,\"end_mono_ns\":%lld,\"end_boot_ns\":%lld,\"events\":[",
        (long long)r->start_mono,(long long)r->start_boot,(long long)r->end_mono,(long long)r->end_boot);
    for(unsigned i=0;i<r->count;i++){const struct event *e=&r->events[i];
        printf("%s{\"event\":\"%s\",\"seq\":%u,\"mono_ns\":%lld,\"boot_ns\":%lld,\"a\":%lld,\"b\":%lld,\"c\":%lld}",
            i?",":"",e->name,i+1,(long long)e->mono,(long long)e->boot,(long long)e->a,(long long)e->b,(long long)e->c);}
    printf("],\"guardian_pidfd_exit\":%s,\"guardian_wait_code\":",BOOL(r->g_exit));
    if(r->have_wait)printf("%d",r->wait_code);else printf("null");
    printf(",\"guardian_stream_eof\":%s,\"tree_empty\":%s,\"streams\":{\"stdout\":{\"bytes\":%zu,\"data_base64\":",BOOL(r->g_eof),BOOL(r->tree_empty),r->out_n);
    b64(r->out,r->out_n);printf(",\"eof\":%s},\"stderr\":{\"bytes\":%zu,\"data_base64\":",BOOL(r->out_eof),r->err_n);
    b64(r->err,r->err_n);printf(",\"eof\":%s}},\"cleanup_attempted\":%s,\"cleanup_verified\":%s,\"deadline_met\":%s,\"output_exceeded\":%s}\n",
        BOOL(r->err_eof),BOOL(r->cleanup_attempted),BOOL(r->cleanup_verified),BOOL(r->deadline_met),BOOL(r->output_exceeded));
}
static int selftest(void) {
    struct frame f={MAGIC,1,1,1,K_REQUEST,0,1,0,0,1,1};int passed=0;
#define CHECK(x) do {if(!(x)){fprintf(stderr,"selftest failed line %d\n",__LINE__);return 1;}passed++;}while(0)
    CHECK(frame_valid(&f,sizeof(f),1,1,0,0));
    CHECK(!frame_valid(&f,sizeof(f)-1,1,1,0,0));
    CHECK(!frame_valid(&f,sizeof(f)+1,1,1,0,0));
    CHECK(!frame_valid(&f,sizeof(f),2,1,0,0));
    CHECK(!frame_valid(&f,sizeof(f),1,2,0,0));
    CHECK(!frame_valid(&f,sizeof(f),1,1,1,0));
    CHECK(!frame_valid(&f,sizeof(f),1,1,0,MSG_TRUNC));
    CHECK(!frame_valid(&f,sizeof(f),1,1,0,MSG_CTRUNC));
    f.magic=0;CHECK(!frame_valid(&f,sizeof(f),1,1,0,0));f.magic=MAGIC;
    f.version=2;CHECK(!frame_valid(&f,sizeof(f),1,1,0,0));f.version=1;
    f.reserved=1;CHECK(!frame_valid(&f,sizeof(f),1,1,0,0));f.reserved=0;
    f.kind=99;CHECK(!frame_valid(&f,sizeof(f),1,1,0,0));
    f.kind=K_IDENTITY;f.a=1;f.b=123;f.c=1;
    CHECK(frame_valid(&f,sizeof(f),1,1,1,0));
    CHECK(!frame_valid(&f,sizeof(f),1,1,0,0));
    CHECK(!frame_valid(&f,sizeof(f),1,1,2,0));
    f.a=0;CHECK(!frame_valid(&f,sizeof(f),1,1,1,0));f.a=9;
    CHECK(!frame_valid(&f,sizeof(f),1,1,1,0));f.a=1;f.b=0;
    CHECK(!frame_valid(&f,sizeof(f),1,1,1,0));f.b=123;f.c=0;
    CHECK(!frame_valid(&f,sizeof(f),1,1,1,0));
    struct sock_filter policy[192];
    unsigned count=build_filter(policy,17,-1,true);
    CHECK(evaluate_filter(policy,count,SYS_write,AUDIT_ARCH_X86_64,1)==SECCOMP_RET_ALLOW);
    CHECK(evaluate_filter(policy,count,SYS_write,AUDIT_ARCH_X86_64,2)==SECCOMP_RET_ALLOW);
    CHECK(evaluate_filter(policy,count,SYS_write,AUDIT_ARCH_X86_64,9)==(SECCOMP_RET_ERRNO|EPERM));
    CHECK(evaluate_filter(policy,count,SYS_sendmsg,AUDIT_ARCH_X86_64,17)==SECCOMP_RET_ALLOW);
    CHECK(evaluate_filter(policy,count,SYS_recvmsg,AUDIT_ARCH_X86_64,17)==SECCOMP_RET_ALLOW);
    CHECK(evaluate_filter(policy,count,SYS_sendmsg,AUDIT_ARCH_X86_64,18)==(SECCOMP_RET_ERRNO|EPERM));
    CHECK(evaluate_filter(policy,count,SYS_prctl,AUDIT_ARCH_X86_64,PR_GET_SECCOMP)==SECCOMP_RET_ALLOW);
    CHECK(evaluate_filter(policy,count,SYS_prctl,AUDIT_ARCH_X86_64,PR_SET_DUMPABLE)==(SECCOMP_RET_ERRNO|EPERM));
    CHECK(evaluate_filter(policy,count,SYS_clone3,AUDIT_ARCH_X86_64,0)==SECCOMP_RET_ALLOW);
    CHECK(evaluate_filter(policy,count,SYS_openat,AUDIT_ARCH_X86_64,0)==(SECCOMP_RET_ERRNO|EPERM));
    CHECK(evaluate_filter(policy,count,SYS_clone,AUDIT_ARCH_X86_64,SIGCHLD)==SECCOMP_RET_ALLOW);
    CHECK(evaluate_filter(policy,count,SYS_clone,AUDIT_ARCH_X86_64,((uint64_t)1<<32)|SIGCHLD)==(SECCOMP_RET_ERRNO|EPERM));
    CHECK(evaluate_filter(policy,count,SYS_clone,AUDIT_ARCH_X86_64,SIGCHLD|CLONE_NEWUSER)==(SECCOMP_RET_ERRNO|EPERM));
    CHECK(evaluate_filter(policy,count,SYS_write,AUDIT_ARCH_I386,1)==SECCOMP_RET_KILL_PROCESS);
    CHECK(evaluate_filter(policy,count,0x40000001,AUDIT_ARCH_X86_64,1)==SECCOMP_RET_KILL_PROCESS);
    count=build_filter(policy,-1,19,false);
    CHECK(evaluate_filter(policy,count,SYS_write,AUDIT_ARCH_X86_64,19)==SECCOMP_RET_ALLOW);
    CHECK(evaluate_filter(policy,count,SYS_prctl,AUDIT_ARCH_X86_64,PR_GET_NO_NEW_PRIVS)==SECCOMP_RET_ALLOW);
    CHECK(evaluate_filter(policy,count,SYS_clone3,AUDIT_ARCH_X86_64,0)==(SECCOMP_RET_ERRNO|EPERM));
    CHECK(evaluate_filter(policy,count,SYS_sendmsg,AUDIT_ARCH_X86_64,17)==(SECCOMP_RET_ERRNO|EPERM));
    CHECK(evaluate_filter(policy,count,SYS_socket,AUDIT_ARCH_X86_64,0)==(SECCOMP_RET_ERRNO|EPERM));
    printf("{\"schema_version\":1,\"native_parser_selftest_passed\":%d}\n",passed);return 0;
#undef CHECK
}
int main(int argc,char **argv) {
    if(argc==2&&strcmp(argv[1],"selftest")==0)return selftest();
    bool probe=argc==5&&strcmp(argv[1],"probe")==0;
    bool run=argc==6&&strcmp(argv[1],"case")==0;
    if(!probe&&!run){fprintf(stderr,"fixed usage: helper selftest | probe E UID GID | case C[1-6] E UID GID\n");return 64;}
    int ci=0;if(run){if(strlen(argv[2])!=2||argv[2][0]!='C'||argv[2][1]<'1'||argv[2][1]>'6')return 64;ci=argv[2][1]-'0';}
    int off=run?1:0;char *end=NULL;errno=0;unsigned long uid=strtoul(argv[3+off],&end,10);
    if(errno||!end||*end||uid==0||uid>UINT32_MAX)return 64;
    errno=0;unsigned long gid=strtoul(argv[4+off],&end,10);
    if(errno||!end||*end||gid==0||gid>UINT32_MAX||geteuid()!=0)return 64;
    struct rlimit core={0,0};if(setrlimit(RLIMIT_CORE,&core))return 65;
    struct sigaction sa;memset(&sa,0,sizeof(sa));sa.sa_handler=SIG_IGN;sigemptyset(&sa.sa_mask);
    (void)sigaction(SIGPIPE,&sa,NULL);
    struct result r;memset(&r,0,sizeof(r));r.case_id=ci;r.probe=probe;
    r.status="OBSERVED";r.reason="fixed_case_observed";
    r.start_mono=now(CLOCK_MONOTONIC);r.start_boot=now(CLOCK_BOOTTIME);
    struct groups cg;
    if(!groups_open(argv[2+off],&cg)){r.status="UNSUPPORTED";r.reason="fixed_group_open";ev(&r,"group_error",errno,0,0);}
    else if(!empty_tree(cg.events)||members(cg.gprocs,0)!=0){r.status="UNKNOWN_RETAINED";r.reason="nonempty_fixture";}
    else {
        int fds[]={cg.e,cg.g,cg.b,cg.s,cg.w};
        const char *names[]={"e_identity","g_identity","b_identity","s_identity","w_identity"};
        bool identities=true;
        for(unsigned i=0;i<sizeof(fds)/sizeof(fds[0]);i++){
            struct stat st;if(fstat(fds[i],&st)){identities=false;break;}
            ev(&r,names[i],(int64_t)st.st_dev,(int64_t)st.st_ino,(int64_t)st.st_mode);
        }
        if(identities)native_run(&r,&cg,(uid_t)uid,(gid_t)gid);
        else {r.status="UNSUPPORTED";r.reason="held_group_identity";}
    }
    r.end_mono=now(CLOCK_MONOTONIC);r.end_boot=now(CLOCK_BOOTTIME);
    r.deadline_met=r.end_mono-r.start_mono<=20*NS&&r.end_boot-r.start_boot<=20*NS;
    if(!r.deadline_met&&strcmp(r.status,"UNSUPPORTED"))r.status="UNKNOWN_RETAINED";
    output(&r);return strcmp(r.status,"OBSERVED")==0?0:strcmp(r.status,"UNSUPPORTED")==0?2:3;
}
