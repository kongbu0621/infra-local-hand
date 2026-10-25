"""Small direct libsystemd client; no subprocess or shell and no bus dependencies.

Only fixed service methods are exposed by services.py. This module is an internal
transport, and has no CLI for caller-selected methods, destinations or bus URLs.
"""
from __future__ import annotations

import ctypes as C
import re
import time

from .supervision import AdapterError


class SystemdBus:
    DEST = b"org.freedesktop.systemd1"
    ROOT = b"/org/freedesktop/systemd1"
    MANAGER = b"org.freedesktop.systemd1.Manager"

    def __init__(self, *, user=False, timeout=20.0):
        # find_library() may spawn ldconfig/gcc; the supervisor has no subprocess
        # tree. Resolve only the installed ABI SONAME through the dynamic loader.
        try:
            self.lib = C.CDLL("libsystemd.so.0")
        except OSError as error:
            raise AdapterError("LIBSYSTEMD_UNAVAILABLE") from error
        self.bus = C.c_void_p()
        self.timeout = timeout
        self.slots = []
        self.callbacks = []
        self._signatures()
        self._check((self.lib.sd_bus_open_user if user else self.lib.sd_bus_open_system)(C.byref(self.bus)))
        self._check(self.lib.sd_bus_set_method_call_timeout(self.bus, int(timeout * 1_000_000)))

    def _signatures(self):
        signatures = {
            "sd_bus_open_system": ([C.POINTER(C.c_void_p)], C.c_int),
            "sd_bus_open_user": ([C.POINTER(C.c_void_p)], C.c_int),
            "sd_bus_set_method_call_timeout": ([C.c_void_p, C.c_uint64], C.c_int),
            "sd_bus_message_new_method_call": ([C.c_void_p, C.POINTER(C.c_void_p), C.c_char_p, C.c_char_p, C.c_char_p, C.c_char_p], C.c_int),
            "sd_bus_message_append_basic": ([C.c_void_p, C.c_char, C.c_void_p], C.c_int),
            "sd_bus_message_open_container": ([C.c_void_p, C.c_char, C.c_char_p], C.c_int),
            "sd_bus_message_close_container": ([C.c_void_p], C.c_int),
            "sd_bus_call": ([C.c_void_p, C.c_void_p, C.c_uint64, C.c_void_p, C.POINTER(C.c_void_p)], C.c_int),
            "sd_bus_message_peek_type": ([C.c_void_p, C.POINTER(C.c_char), C.POINTER(C.c_char_p)], C.c_int),
            "sd_bus_message_read_basic": ([C.c_void_p, C.c_char, C.c_void_p], C.c_int),
            "sd_bus_message_enter_container": ([C.c_void_p, C.c_char, C.c_char_p], C.c_int),
            "sd_bus_message_exit_container": ([C.c_void_p], C.c_int),
            "sd_bus_message_at_end": ([C.c_void_p, C.c_int], C.c_int),
            "sd_bus_message_unref": ([C.c_void_p], C.c_void_p),
            "sd_bus_slot_unref": ([C.c_void_p], C.c_void_p),
            "sd_bus_flush_close_unref": ([C.c_void_p], C.c_void_p),
            "sd_bus_process": ([C.c_void_p, C.c_void_p], C.c_int),
            "sd_bus_wait": ([C.c_void_p, C.c_uint64], C.c_int),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.lib, name)
            fn.argtypes, fn.restype = args, result

    @staticmethod
    def _check(code):
        if code < 0:
            raise AdapterError(f"SYSTEMD_BUS_ERRNO_{-code}")
        return code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        for slot in self.slots:
            self.lib.sd_bus_slot_unref(slot)
        self.lib.sd_bus_flush_close_unref(self.bus)

    def _append(self, message, signature, value):
        if signature == "a(sv)":
            # Internal convenience for SetUnitProperties' a(sv): resource
            # properties are explicitly uint64, never caller-selected variants.
            self._check(self.lib.sd_bus_message_open_container(message, b"a", b"(sv)"))
            for name, number in value:
                if type(number) is not int or not 0 <= number < 2**64:
                    raise AdapterError("SYSTEMD_ARGUMENT_TYPE")
                self._check(self.lib.sd_bus_message_open_container(message, b"r", b"sv"))
                self._append(message, "s", name)
                self._check(self.lib.sd_bus_message_open_container(message, b"v", b"t"))
                data = C.c_uint64(number)
                self._check(self.lib.sd_bus_message_append_basic(message, b"t", C.byref(data)))
                self._check(self.lib.sd_bus_message_close_container(message))
                self._check(self.lib.sd_bus_message_close_container(message))
            self._check(self.lib.sd_bus_message_close_container(message))
        elif signature == "as":
            self._check(self.lib.sd_bus_message_open_container(message, b"a", b"s"))
            for item in value:
                self._append(message, "s", item)
            self._check(self.lib.sd_bus_message_close_container(message))
        elif signature in ("s", "o"):
            self._check(self.lib.sd_bus_message_append_basic(message, signature.encode(), C.c_char_p(value.encode())))
        elif signature == "b":
            data = C.c_int(bool(value))
            self._check(self.lib.sd_bus_message_append_basic(message, b"b", C.byref(data)))
        else:
            raise AdapterError("SYSTEMD_ARGUMENT_TYPE")

    def _value(self, message):
        kind, contents = C.c_char(), C.c_char_p()
        self._check(self.lib.sd_bus_message_peek_type(message, C.byref(kind), C.byref(contents)))
        kind = kind.value
        types = {b"s": C.c_char_p, b"o": C.c_char_p, b"g": C.c_char_p, b"b": C.c_int,
                 b"u": C.c_uint32, b"i": C.c_int32, b"t": C.c_uint64, b"x": C.c_int64,
                 b"y": C.c_ubyte, b"q": C.c_uint16, b"n": C.c_int16, b"d": C.c_double}
        if kind in types:
            value = types[kind]()
            self._check(self.lib.sd_bus_message_read_basic(message, kind, C.byref(value)))
            if kind in (b"s", b"o", b"g"):
                return value.value.decode()
            return bool(value.value) if kind == b"b" else value.value
        if kind not in (b"a", b"r", b"e", b"v"):
            raise AdapterError("SYSTEMD_REPLY_TYPE")
        self._check(self.lib.sd_bus_message_enter_container(message, kind, contents))
        values = self._body(message)
        self._check(self.lib.sd_bus_message_exit_container(message))
        return values[0] if kind == b"v" and len(values) == 1 else values

    def _body(self, message):
        values = []
        while not self._check(self.lib.sd_bus_message_at_end(message, 0)):
            if len(values) >= 16384:
                raise AdapterError("SYSTEMD_REPLY_BOUND")
            values.append(self._value(message))
        return values

    def call(self, method, arguments=(), *, path=None, interface=None, destination=None):
        request, reply = C.c_void_p(), C.c_void_p()
        try:
            self._check(self.lib.sd_bus_message_new_method_call(
                self.bus, C.byref(request), destination or self.DEST, path or self.ROOT,
                interface or self.MANAGER, method.encode()))
            for signature, value in arguments:
                self._append(request, signature, value)
            self._check(self.lib.sd_bus_call(self.bus, request, int(self.timeout * 1_000_000), None, C.byref(reply)))
            return self._body(reply)
        finally:
            if request:
                self.lib.sd_bus_message_unref(request)
            if reply:
                self.lib.sd_bus_message_unref(reply)

    def properties(self, path, interface):
        value = self.call("GetAll", (("s", interface),), path=path.encode(), interface=b"org.freedesktop.DBus.Properties")
        return dict(value[0])

    def unit(self, name):
        path = self.call("LoadUnit", (("s", name),))[0]
        properties = self.properties(path, "org.freedesktop.systemd1.Unit")
        interface = {"service": "Service", "slice": "Slice"}.get(name.rsplit(".", 1)[-1])
        if properties.get("LoadState") == "loaded" and interface is not None:
            properties.update(self.properties(path, "org.freedesktop.systemd1." + interface))
        if isinstance(properties.get("InvocationID"), list):
            properties["InvocationID"] = bytes(properties["InvocationID"]).hex()
        if name.endswith(".service"):
            # Managed services need an independently checked enable policy.
            # Read-only dependencies may have no unit file: system.slice is
            # loaded/active while GetUnitFileState returns ENOENT. Preserve its
            # actual Unit properties instead of treating that as an absent or
            # unreadable dependency (or inventing an enable policy for it).
            try:
                properties["UnitFileState"] = self.call("GetUnitFileState", (("s", name),))[0]
            except AdapterError:
                if properties.get("LoadState") != "not-found":
                    raise
                properties["UnitFileState"] = "absent"
        return properties

    def jobs(self):
        return self.call("ListJobs")[0]

    def unique_name(self):
        value = C.c_char_p()
        self.lib.sd_bus_get_unique_name.argtypes = [C.c_void_p, C.POINTER(C.c_char_p)]
        self.lib.sd_bus_get_unique_name.restype = C.c_int
        self._check(self.lib.sd_bus_get_unique_name(self.bus, C.byref(value)))
        return value.value.decode()

    def fence_sender(self, name):
        """Observe a disconnected recorded sender, then drain the manager queue.

        Supported on the local message bus (not peer-to-peer/remote transports):
        the bus has processed/discarded the dead sender before NameHasOwner=false;
        a subsequent manager call is ordered behind previously forwarded calls.
        ListJobs then covers effects already enqueued by those method handlers.
        This does not prove those jobs finished; the caller checks their presence.
        """
        if not re.fullmatch(r":[0-9]+\.[0-9]+", name):
            raise AdapterError("SYSTEMD_SENDER_NAME")
        present = self.call("NameHasOwner", (("s", name),), destination=b"org.freedesktop.DBus",
                            path=b"/org/freedesktop/DBus", interface=b"org.freedesktop.DBus")[0]
        if present:
            return {"closed": False, "jobs": []}
        return {"closed": True, "jobs": self.jobs()}

    def run_job(self, unit, method, emit, *, mode="fail"):
        """Subscribe before dispatch; job return and JobRemoved are both recorded."""
        if method not in ("StartUnit", "StopUnit"):
            raise AdapterError("SYSTEMD_ACTION")
        if mode not in ("fail", "ignore-requirements") or (mode != "fail" and method != "StartUnit"):
            raise AdapterError("SYSTEMD_JOB_MODE")
        completed = []
        callback_errors = []
        callback_type = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_void_p)
        def received(message, userdata, error):
            try:
                fields = self._body(message)
                if len(fields) == 4 and fields[2] == unit:
                    event = {"kind": "job_removed", "job_id": fields[0], "job_path": fields[1],
                             "unit": fields[2], "result": fields[3]}
                    emit(event)
                    completed.append(event)
            except BaseException as failure:
                callback_errors.append(failure)
            return 0
        callback = callback_type(received)
        self.callbacks.append(callback)
        slot = C.c_void_p()
        self.lib.sd_bus_add_match.argtypes = [C.c_void_p, C.POINTER(C.c_void_p), C.c_char_p, callback_type, C.c_void_p]
        self.lib.sd_bus_add_match.restype = C.c_int
        match = b"type='signal',sender='org.freedesktop.systemd1',interface='org.freedesktop.systemd1.Manager',member='JobRemoved'"
        self._check(self.lib.sd_bus_add_match(self.bus, C.byref(slot), match, callback, None))
        self.slots.append(slot)
        emit({"kind": "bus_binding", "sender": self.unique_name(), "unit": unit})
        self.call("Subscribe")
        emit({"kind": "dispatching", "unit": unit, "method": method, "job_mode": mode})
        job_path = self.call(method, (("s", unit), ("s", mode)))[0]
        emit({"kind": "job_accepted", "unit": unit, "job_path": job_path})
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            while self._check(self.lib.sd_bus_process(self.bus, None)):
                pass
            if callback_errors:
                raise callback_errors[0]
            found = next((value for value in completed if value["job_path"] == job_path), None)
            if found:
                return found
            self._check(self.lib.sd_bus_wait(self.bus, 100000))
        raise TimeoutError("SYSTEMD_JOB_COMPLETION_UNKNOWN")
