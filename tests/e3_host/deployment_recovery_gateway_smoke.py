"""Opt-in real Docker/nginx gateway acceptance, separate from live adoption.

Use a verified installed runtime/admin projection on PYTHONPATH and an already
built exact image ID. --run-isolated-gateway requires root. It creates only one
random container, no networks/volumes/host ports, and removes that exact object.
The manager fixture uses production authorization and a real private socket;
it is not the resident business manager. Engine responses are deliberately
discarded *after* actual effects; this is not a daemon power-loss test.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import signal
import socket
import socketserver
import struct
import subprocess
import sys
import tempfile
import time
import uuid

from admin.local_hand_deploy.gateway import DockerEngine, GatewayAdapter
from admin.local_hand_deploy.runtime import PlanningEnvironment
from admin.local_hand_deploy.supervision import SupervisedRunner
from local_hand.provenance import full_payload_digest
from local_hand_jobs import maintenance, startup
from local_hand_jobs.contract import JobError
from local_hand_mcp.gateway_guard import configuration_binding, validate_nginx


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def wait_for(function, seconds=15):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            value = function()
            if value:
                return value
        except (OSError, ValueError, RuntimeError) as error:
            last = error
        time.sleep(.1)
    raise RuntimeError('Bounded platform observation did not converge') from last


def migration_nginx():
    return '''worker_processes 1; error_log stderr warn;
events { worker_connections 128; }
http {
 access_log off; server_tokens off; client_max_body_size 128k;
 client_body_temp_path /run/local-hand-gateway/client-body;
 proxy_temp_path /run/local-hand-gateway/proxy-temp;
 fastcgi_temp_path /run/local-hand-gateway/fastcgi-temp;
 uwsgi_temp_path /run/local-hand-gateway/uwsgi-temp;
 scgi_temp_path /run/local-hand-gateway/scgi-temp;
 resolver 127.0.0.11 valid=10s ipv6=off;
 limit_req_zone $binary_remote_addr zone=auth:1m rate=1r/s;
 upstream mcp_check { server unix:/run/local-hand-mcp-check/http.sock; }
 server {
  listen 127.0.0.1:18081; server_name _;
  set $lh_backend_identity http://127.0.0.1:19090;
  location / { return 404; }
  location /realms/example/login-actions/ {
   limit_req zone=auth burst=2 nodelay; proxy_pass $lh_backend_identity;
  }
  location /resources/ { limit_except GET { deny all; } proxy_pass $lh_backend_identity; }
  location = /.well-known/oauth-authorization-server/realms/example {
   rewrite ^ /realms/example/.well-known/openid-configuration break;
   proxy_pass $lh_backend_identity;
  }
  location = /mcp {
   client_max_body_size 512k; proxy_pass http://mcp_check;
   proxy_http_version 1.1; proxy_set_header Connection "";
   proxy_buffering off; proxy_request_buffering off;
  }
 }
}
'''


def fixture(root, worker_gid=None):
    """Protected, synthetic inputs. No daemon access or fake platform claims."""
    gate_dir = root / 'gate'; gate_dir.mkdir(mode=0o700)
    gate = maintenance.MaintenanceGate(gate_dir, 'gateway-fixture', owner_uid=os.geteuid())
    deployment = hashlib.sha256(b'isolated-gateway-platform-fixture').hexdigest()
    gate.initialize(deployment, 'original', bootstrap=True)
    nginx = root / 'nginx.conf'
    nginx.write_text('worker_processes 1; error_log stderr warn;\n'
        'events { worker_connections 32; }\nhttp { access_log off;\n'
        'client_body_temp_path /run/local-hand-gateway/client-body;\n'
        'proxy_temp_path /run/local-hand-gateway/proxy-temp;\n'
        'server { listen 127.0.0.1:18081; server_name _;\n'
        'location / { return 404; } location = /mcp { return 401; } } }\n')
    nginx.chmod(0o600)
    config = dict(schema='local-hand-gateway-startup/v1', node_id='gateway-fixture',
        deployment_digest=deployment, payload_digest=full_payload_digest(),
        manager_socket=str(root / 'manager.sock'), nginx_config=str(nginx),
        public_port=18080, upstream_port=18081,
        status_socket='/run/local-hand-gateway/status.sock')
    if worker_gid is not None:
        if type(worker_gid) is not int or not 1 <= worker_gid <= 2**31 - 1:
            raise ValueError('A positive nonroot worker gid is required')
        config['worker_group'] = {'name': 'local-hand-mcp', 'gid': worker_gid}
        nginx.write_text(migration_nginx())
    config_path = root / 'guard.json'; save(config_path, config)
    binding = startup.digest(configuration_binding(config))
    selection = dict(schema=startup.SCHEMA, node_id=config['node_id'],
        deployment_digest=deployment, decision_id='original', mode='stable', owner=None,
        permit=None, members=[dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                              for path in (nginx, config_path)],
        components={'gateway': dict(configuration_digest=binding,
            payload_digest=config['payload_digest'], entry='public', running=True)})
    startup.publish(root / 'selection.json', selection, gate,
                    expected_digest=None, owner_uid=os.geteuid())
    return gate, config, selection


def manager(root):
    """A separate process: adapter supervision must remain single threaded."""
    gate = maintenance.MaintenanceGate(root / 'gate', 'gateway-fixture')
    config = {'maintenance': {'startup_descriptor': str(root / 'selection.json')}}
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(root / 'manager.sock')); os.chmod(root / 'manager.sock', 0o600)
        server.listen(4); server.settimeout(.2)
        while not stopped:
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            with connection:
                try:
                    pid, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    request = startup._frame_read(connection, time.monotonic() + 1)
                    if (set(request) != {'action', 'component', 'mode'}
                            or request['action'] != 'startup_authorize' or request['component'] != 'gateway'):
                        raise ValueError('Not the fixed gateway authorization request')
                    startup.serve_gateway_authorization(connection, config, gate,
                        peer_pid=pid, peer_uid=uid, mode=request['mode'])
                except (JobError, OSError, ValueError):
                    # Refusals while candidate/blocked are expected. Real proofs
                    # and host namespace identity are verified by the parent.
                    continue


class LoseResponse(DockerEngine):
    def request(self, method, path, body=None, *, missing=False):
        result = super().request(method, path, body, missing=missing)
        if method != 'GET':
            raise ConnectionResetError('Fixture discarded a completed Engine mutation response')
        return result


def profile_for(root, config, image_id, daemon_id, name):
    service = dict(image=image_id, container_name=name, user='0:0', restart='no',
        entrypoint=['/opt/local-hand/gateway/bin/python', '-B', '-m', 'local_hand_mcp.gateway_guard'],
        command=['--config', str(root / 'guard.json')], environment={}, ports=[], networks={},
        volumes=[dict(type='bind', source=str(root), target=str(root), read_only=True)])
    if 'worker_group' in config:
        service.update(read_only=True, cpus=1, mem_limit='64m', pids_limit=32,
            cap_drop=['ALL'], cap_add=['CHOWN', 'SETUID', 'SETGID'],
            group_add=[str(config['worker_group']['gid'])], security_opt=['no-new-privileges:true'],
            tmpfs={'/run/local-hand-gateway': 'rw,nosuid,nodev,noexec,size=16m,mode=0755'},
            logging={'driver': 'local', 'options': {'max-file': '2', 'max-size': '5m'}})
        service['volumes'].append(dict(type='bind', source=str(root / 'backend'),
            target='/run/local-hand-mcp-check', read_only=True))
    return dict(project=name, service='gateway', container_name=name, component='gateway',
        daemon_id=daemon_id, network_ids={}, dependency_container_ids={},
        compose={'name': name, 'services': {'gateway': service}, 'networks': {}})


def namespace_http(pid, port, path):
    # Only enter the isolated network namespace; never change host networking.
    code = ('import http.client,sys\n'
            'c=http.client.HTTPConnection("127.0.0.1",int(sys.argv[1]),timeout=1)\n'
            'try:\n c.request("GET",sys.argv[2]);r=c.getresponse();print(r.status);r.read(4096)\n'
            'except OSError:\n print("CLOSED")\n'
            'finally:\n c.close()\n')
    result = subprocess.run(['/usr/bin/nsenter', '--target', str(pid), '--net',
        '/usr/bin/python3', '-I', '-B', '-c', code, str(port), path],
        capture_output=True, timeout=3, check=True)
    return result.stdout.decode().strip()


def backend(address):
    """No business: bounded HTTP echo in a private Unix or isolated TCP listener."""
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            self.connection.settimeout(2)
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 600 * 1024: raise ValueError('Fixture body bound')
            body = self.rfile.read(length)
            if len(body) != length: raise ValueError('Fixture short body')
            value = {'path': self.path, 'length': length}
            if self.connection.family == socket.AF_UNIX:
                _, uid, gid = struct.unpack('3i', self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                value.update(uid=uid, gid=gid)
            raw = json.dumps(value).encode()
            self.send_response(401 if self.command == 'GET' and self.path == '/mcp' else 200)
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
        do_POST = do_GET
    if address == 'tcp':
        server = http.server.HTTPServer(('127.0.0.1', 19090), Handler)
    else:
        server = socketserver.UnixStreamServer(address, Handler)
        parent = Path(address).parent.stat()
        os.chown(address, 0, parent.st_gid); os.chmod(address, 0o660)
    with server:
        server.serve_forever(poll_interval=.1)


def migration_requests(pid, worker_gid):
    code = '''import http.client,json
def request(path,method='GET',size=0):
 c=http.client.HTTPConnection('127.0.0.1',18080,timeout=2)
 try:
  c.request(method,path,body=b'x'*size);r=c.getresponse();raw=r.read(8192)
  return r.status,raw.decode()
 finally:c.close()
rows={}
rows['rewrite']=request('/.well-known/oauth-authorization-server/realms/example')
rows['method']=request('/resources/test','POST')
rows['body_default']=request('/resources/test','POST',128*1024+1)
rows['body_mcp']=request('/mcp','POST',512*1024)
rows['body_mcp_reject']=request('/mcp','POST',512*1024+1)
rows['rate']=[request('/realms/example/login-actions/test')[0] for _ in range(8)]
print(json.dumps(rows))
'''
    result = subprocess.run(['/usr/bin/nsenter', '--target', str(pid), '--net',
        '/usr/bin/python3', '-I', '-B', '-c', code], capture_output=True, timeout=25, check=True)
    rows = json.loads(result.stdout)
    assert rows['rewrite'][0] == 200
    assert json.loads(rows['rewrite'][1])['path'] == '/realms/example/.well-known/openid-configuration'
    assert rows['method'][0] == 403 and rows['body_default'][0] == 413
    assert rows['body_mcp'][0] == 200 and rows['body_mcp_reject'][0] == 413
    mcp = json.loads(rows['body_mcp'][1])
    assert mcp['length'] == 512 * 1024 and mcp['uid'] != 0 and mcp['gid'] == worker_gid
    assert rows['rate'][0] == 200 and 503 in rows['rate'] and set(rows['rate']) <= {200, 503}
    return rows


def run(root, image_id, worker_gid=None, selected_nginx=None):
    if os.geteuid() != 0:
        raise RuntimeError('Real isolated Docker acceptance requires root')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
        raise ValueError('An exact already-built image ID is required')
    engine = DockerEngine(timeout=15)
    daemon = engine.request('GET', '/info')
    name = 'lh-gateway-check-' + uuid.uuid4().hex[:16]
    gate, config, original = fixture(root, worker_gid)
    if selected_nginx is not None:
        if worker_gid is None: raise ValueError('Selected config check requires the migration profile')
        raw = startup.protected_read(str(selected_nginx), owner_uid=0, maximum=256*1024)
        validate_nginx(raw, config['upstream_port'])
        with (root / 'selected-nginx.conf').open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600); stream.write(raw)
    profile = profile_for(root, config, image_id, daemon['ID'], name)
    env = PlanningEnvironment({'owner_uid': 0, 'gateway': profile,
        'probes': {'gateway': {'kind': 'gateway', 'socket': config['status_socket'], 'peer_uid': 0}}})
    runner = SupervisedRunner(root / 'calls', timeout=25)
    selection_path = root / 'selection.json'
    def guard_check(_, target):
        selected = startup.read_selection(selection_path)
        startup.verify_members(selected)
        part = selected['components']['gateway']; permit = selected.get('permit') or {}
        return dict(descriptor_digest=startup.digest(selected), config_digest=part['configuration_digest'],
            deployment_digest=selected['deployment_digest'], mode=selected['mode'],
            target_running=part['running'], boot=permit.get('boot_id'), attempt_id=permit.get('attempt_id'))
    adapter = GatewayAdapter(profile, runner, engine=LoseResponse(timeout=15),
        guard_check=guard_check, route_probe=env._route)
    env._gateway = adapter
    report = dict(schema='local-hand-isolated-gateway-check/v1', image_id=image_id,
        payload_digest=config['payload_digest'], node_id=config['node_id'],
        scope='real Docker/nginx/authorization/probe/adapter; synthetic manager and routes',
        live_service_mutations=False, host_ports_published=False, actions=[], status='RUNNING')
    save(root / 'test-inputs.json', {'profile': profile, 'source': original})
    helper = None
    backends = []
    owned_id = None
    cleanup_errors = []
    lock = os.open(root / 'node.lock', os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX)
    def publish(value, maintenance_owner=None):
        current = startup.read_selection(selection_path)
        startup.publish(selection_path, value, gate, expected_digest=startup.digest(current),
                        maintenance_owner=maintenance_owner)
    def candidate(attempt):
        value = copy.deepcopy(original)
        value.update(mode='candidate', owner='check', decision_id=None,
            permit=dict(boot_id=startup.boot_id(), attempt_id=attempt, claims={}))
        publish(value)
    def perform(action, attempt):
        recorded = []
        report['pending_action'] = dict(action=action, attempt=attempt)
        def persist(binding):
            save(root / ('intent-' + attempt + '.json'), binding); recorded.append(binding)
        try:
            result = adapter.execute(action, attempt_id=attempt, lock_fd=lock, persist_intent=persist)
        except (OSError, RuntimeError) as error:
            if hasattr(error, 'observation'):
                report['pending_action']['refused_observation'] = error.observation
            # A start reply can be lost before nginx is ready. The original
            # durable attempt remains the only candidate for observation.
            if not recorded:
                raise
        if not recorded:
            raise AssertionError('Expected one actually dispatched isolated operation')
        previous = runner.observe(recorded[0], lock_fd=lock)
        def observed():
            value = adapter.observe_action(action, previous, lock_fd=lock)
            return value if value['postcondition'] and value['closed'] else None
        result = wait_for(observed)
        assert previous['result']['status'] == 'unknown'
        assert sum(e['kind'] == 'engine_dispatch' for e in previous['events']) == 1
        before = sorted(str(p) for p in (root / 'calls').iterdir())
        repeated = adapter.execute(action, attempt_id=attempt, lock_fd=lock,
            persist_intent=lambda _: (_ for _ in ()).throw(AssertionError('Duplicate dispatch')),
            previous=previous)
        assert repeated['postcondition'] and repeated['closed']
        assert before == sorted(str(p) for p in (root / 'calls').iterdir())
        report['actions'].append(dict(kind=action['kind'], attempt=attempt,
            recovered=result, repeat_without_dispatch=True))
        report.pop('pending_action', None)
        return result
    try:
        if worker_gid is not None:
            directory = root / 'backend'; directory.mkdir(mode=0o750)
            os.chown(directory, 0, worker_gid)
            log = (root / 'unix-backend.log').open('xb')
            with log:
                backends.append(subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                    '--serve-fixture-backend', str(directory / 'http.sock')], stdout=log, stderr=subprocess.STDOUT))
            wait_for(lambda: (directory / 'http.sock').is_socket() and backends[-1].poll() is None)
        assert adapter.observe()['kind'] == 'absent'
        helper_log = (root / 'manager.log').open('xb')
        with helper_log:
            helper = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                '--serve-fixture-manager', str(root)], stdout=helper_log, stderr=subprocess.STDOUT)
        wait_for(lambda: (root / 'manager.sock').is_socket() and helper.poll() is None)
        gate.close('check')
        target = dict(present=True, running=True, deployment_digest=config['deployment_digest'],
                      config_digest=original['components']['gateway']['configuration_digest'])
        actions = adapter.plan(target)
        assert [a['kind'] for a in actions] == ['gateway_create', 'gateway_start']
        candidate('create_lost')
        created = perform(actions[0], 'create_lost')
        owned_id = created['observation']['id']
        report['container_id'] = owned_id
        candidate('start_lost')
        started = perform(actions[1], 'start_lost')
        proof = env._probe('gateway')['loaded']; pid = proof['pid']
        if worker_gid is not None:
            log = (root / 'tcp-backend.log').open('xb')
            with log:
                backends.append(subprocess.Popen(['/usr/bin/nsenter', '--target', str(pid), '--net',
                    sys.executable, '-B', str(Path(__file__).resolve()), '--serve-fixture-backend', 'tcp'],
                    stdout=log, stderr=subprocess.STDOUT))
            wait_for(lambda: namespace_http(pid, 19090, '/ready') == '200')
        assert proof['container_id'] == owned_id and not proof['public_ready']
        assert namespace_http(pid, 18080, '/mcp') == 'CLOSED'
        assert namespace_http(pid, 18081, '/mcp') == '401'
        report['candidate_local_only'] = True
        stable = {**original, 'decision_id': 'committed'}
        publish(stable, 'check'); gate.release('check', 'committed', config['deployment_digest'])
        wait_for(lambda: env._probe('gateway')['loaded']['public_ready'])
        assert namespace_http(pid, 18080, '/mcp') == '401'
        assert namespace_http(pid, 18080, '/') == '404'
        report['released_public_in_namespace'] = True
        if worker_gid is not None:
            report['migration_controls'] = migration_requests(pid, worker_gid)
            report['container_resource_controls'] = engine.request('GET', '/containers/' + owned_id + '/json')['HostConfig']
            if selected_nginx is not None:
                # Only parse the retained real config, in this already bound
                # isolated container. This does not reload nginx or reach its backends.
                checked = subprocess.run(['/usr/bin/docker', 'exec', owned_id, '/usr/sbin/nginx',
                    '-p', '/run/local-hand-gateway/', '-c', str(root / 'selected-nginx.conf'),
                    '-g', 'daemon off; user nginx local-hand-mcp; pid /run/local-hand-gateway/nginx.pid;', '-t'],
                    capture_output=True, timeout=15, check=True)
                report['selected_nginx'] = {'sha256': hashlib.sha256(raw).hexdigest(),
                    'syntax_passed': True, 'output': (checked.stdout + checked.stderr)[-8192:].decode(errors='replace')}
        gate.close('isolate')
        publish({**stable, 'mode': 'blocked', 'owner': 'isolate'})
        wait_for(lambda: not env._probe('gateway')['loaded']['public_ready'], seconds=5)
        assert namespace_http(pid, 18080, '/mcp') == 'CLOSED'
        assert namespace_http(pid, 18081, '/mcp') == '401'
        report['revoked_public_preserved_local'] = True
        # Recovery can stop/remove the exact container with public access blocked.
        stop, remove = adapter.plan({'present': False, 'running': False})
        perform(stop, 'stop_lost')
        perform(remove, 'remove_lost')
        assert adapter.observe()['kind'] == 'absent'
        report['status'] = 'PASSED'
    except BaseException as error:
        report.update(status='FAILED', error_type=type(error).__name__, error=str(error)[:2000])
    finally:
        # Cleanup never selects arbitrary containers. Even a lost create reply
        # must match this run's full specification and attempt-labelled object.
        try:
            remaining = adapter.observe(require_route=False)
            if remaining['kind'] == 'container':
                identity = remaining['id']
                if ((owned_id is not None and identity != owned_id)
                        or remaining['labels'].get('local-hand.deploy.attempt') != 'create_lost'):
                    raise RuntimeError('Refusing cleanup of independently replaced container')
                if report['status'] != 'PASSED':
                    # Only this fixed synthetic container: no live service logs.
                    try:
                        logs = subprocess.run(['/usr/bin/docker', 'logs', '--tail', '100', identity],
                            capture_output=True, timeout=5)
                        report['container_log_tail'] = (logs.stdout + logs.stderr)[-32768:].decode(errors='replace')
                    except (OSError, subprocess.TimeoutExpired) as error:
                        report['log_error'] = type(error).__name__
                if remaining['status'] == 'running':
                    engine.request('POST', '/containers/' + identity + '/stop?t=10')
                engine.request('DELETE', '/containers/' + identity + '?force=false&v=false')
            if adapter.observe(require_route=False)['kind'] != 'absent':
                raise RuntimeError('Isolated container is not absent after cleanup')
        except BaseException as error:
            cleanup_errors.append(type(error).__name__ + ': ' + str(error)[:1000])
        for process in [helper, *backends]:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=3)
        os.close(lock)
        report['cleanup_errors'] = cleanup_errors
        if cleanup_errors:
            report['status'] = 'FAILED'
        save(root / 'gateway-result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--run-isolated-gateway', action='store_true')
    group.add_argument('--validate-fixture-only', action='store_true')
    group.add_argument('--serve-fixture-manager', type=Path)
    group.add_argument('--serve-fixture-backend')
    parser.add_argument('--migration-worker-gid', type=int)
    parser.add_argument('--selected-nginx', type=Path)
    parser.add_argument('--image-id')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.serve_fixture_manager:
        manager(args.serve_fixture_manager); return 0
    if args.serve_fixture_backend:
        backend(args.serve_fixture_backend); return 0
    if args.validate_fixture_only:
        with tempfile.TemporaryDirectory(prefix='lh-gateway-inputs-') as directory:
            root = Path(directory)
            gate, config, selection = fixture(root, args.migration_worker_gid)
            startup.verify_members(selection, owner_uid=os.geteuid())
            profile = profile_for(root, config, 'sha256:' + 'a' * 64, 'fixture-daemon', 'fixture-gateway')
            adapter = GatewayAdapter(profile, type('Budget', (), {'timeout': 30})())
            body = adapter._create_body({'config_digest': 'b' * 64, 'deployment_digest': 'c' * 64}, 'fixture')
            assert body['HostConfig']['NetworkMode'] == 'none'
            assert not body['HostConfig']['PortBindings'] and not body['NetworkingConfig']['EndpointsConfig']
            assert gate.snapshot()['state'] == 'OPEN'
            gate.close('check')
            candidate = {**selection, 'mode': 'candidate', 'owner': 'check', 'decision_id': None,
                'permit': {'boot_id': startup.boot_id(), 'attempt_id': 'start_lost', 'claims': {}}}
            startup.publish(root / 'selection.json', candidate, gate,
                            expected_digest=startup.digest(selection), owner_uid=os.geteuid())
            stable = {**selection, 'decision_id': 'committed'}
            startup.publish(root / 'selection.json', stable, gate,
                expected_digest=startup.digest(candidate), owner_uid=os.geteuid(), maintenance_owner='check')
            gate.release('check', 'committed', config['deployment_digest'])
            gate.close('isolate')
            startup.publish(root / 'selection.json', {**stable, 'mode': 'blocked', 'owner': 'isolate'}, gate,
                            expected_digest=startup.digest(stable), owner_uid=os.geteuid())
        print('Fixture schema, protected inputs and isolated container scope passed; no Docker access.')
        return 0
    if args.image_id is None or args.output is None or not args.output.is_absolute():
        parser.error('--image-id and an absolute new --output directory are required')
    if os.geteuid() != 0:
        parser.error('Run this opt-in isolated check as root')
    def interrupted(signum, frame):
        raise TimeoutError('Isolated gateway check interrupted; attempt exact cleanup')
    signal.signal(signal.SIGTERM, interrupted)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    report = run(args.output, args.image_id, args.migration_worker_gid, args.selected_nginx)
    print(json.dumps({'status': report['status'], 'report': str(args.output / 'gateway-result.json')}))
    return 0 if report['status'] == 'PASSED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
