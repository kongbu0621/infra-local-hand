"""Kernel /proc/PID/stat field layout for known control-child tests."""
import os


def stat_record(pid, *, start=None, cpu_ticks=25, rss_bytes=1048576,
                state=b"S", name=b"fixture"):
    fields = [b"0"] * 50
    fields[0] = state
    fields[11] = str(cpu_ticks).encode()
    fields[19] = str(100 + pid if start is None else start).encode()
    fields[21] = str(rss_bytes // os.sysconf("SC_PAGE_SIZE")).encode()
    return str(pid).encode() + b" (" + name + b") " + b" ".join(fields) + b"\n"
