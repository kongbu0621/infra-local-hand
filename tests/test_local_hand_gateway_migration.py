"""Preserve real migration controls without relaxing the gateway to arbitrary nginx."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from admin.local_hand_deploy.gateway import GatewayAdapter, _resource_config
from admin.local_hand_deploy.runtime import PlanningEnvironment
from admin.local_hand_deploy.model import DeployError
from admin.local_hand_deploy.supervision import AdapterError
from local_hand_jobs.contract import JobError
from local_hand_mcp import gateway_guard as guard


NGINX = b'''worker_processes 1; error_log stderr warn;
events { worker_connections 128; }
http {
 access_log off; server_tokens off;
 client_max_body_size 128k;
 client_body_temp_path /run/local-hand-gateway/client-body;
 proxy_temp_path /run/local-hand-gateway/proxy-temp;
 resolver 127.0.0.11 valid=10s ipv6=off;
 limit_req_zone $binary_remote_addr zone=auth:1m rate=10r/s;
 upstream local_mcp { server unix:/run/example-mcp/http.sock; }
 server {
  listen 127.0.0.1:18081; server_name example.test;
  set $lh_backend_identity http://identity:8080;
  location /realms/example/login-actions/ {
   limit_req zone=auth burst=20 nodelay; proxy_pass $lh_backend_identity;
  }
  location /resources/ { limit_except GET { deny all; } proxy_pass $lh_backend_identity; }
  location = /.well-known/oauth-authorization-server/realms/example {
   rewrite ^ /realms/example/.well-known/openid-configuration break;
   proxy_pass $lh_backend_identity;
  }
  location = /mcp {
   client_max_body_size 512k; proxy_pass http://local_mcp;
   proxy_http_version 1.1; proxy_set_header Connection "";
   proxy_buffering off; proxy_request_buffering off; proxy_read_timeout 65s;
  }
  location / { return 404; }
 }
}
'''


def config():
    return dict(schema=guard.SCHEMA,node_id='example',deployment_digest='a'*64,
        payload_digest='b'*64,manager_socket='/run/example-manager/manager.sock',
        nginx_config='/etc/example-gateway/nginx.conf',public_port=8081,upstream_port=18081,
        status_socket='/run/local-hand-gateway/status.sock')


def limits():
    return dict(cpus=1,mem_limit='64m',pids_limit=32,cap_drop=['ALL'],
        cap_add=['CHOWN','SETUID','SETGID'],group_add=['1234'],read_only=True,
        security_opt=['no-new-privileges:true'],
        tmpfs={'/run/local-hand-gateway':'rw,nosuid,nodev,noexec,size=16m,mode=0755'},
        logging={'driver':'local','options':{'max-file':'2','max-size':'5m'}})


class GrammarTests(unittest.TestCase):
    def test_fixed_auth_controls_and_exact_discovery_rewrite(self):
        self.assertEqual(guard.validate_nginx(NGINX,18081),NGINX)

    def test_body_limit_units_boundaries(self):
        for value in ('1','128k','512K','64m','67108864'):
            with self.subTest(value=value):guard.validate_nginx(NGINX.replace(b'128k',value.encode()),18081)
        for value in ('0','65m','67108865','128g','-1','True'):
            with self.subTest(value=value),self.assertRaises(JobError):
                guard.validate_nginx(NGINX.replace(b'128k',value.encode()),18081)

    def test_unused_module_temp_paths_are_confined_for_readonly_root(self):
        for module in ('fastcgi', 'uwsgi', 'scgi'):
            directive = f'{module}_temp_path /run/local-hand-gateway/{module}-temp;'.encode()
            raw = NGINX.replace(b'access_log off;', b'access_log off; ' + directive)
            guard.validate_nginx(raw, 18081)
            with self.assertRaises(JobError):
                guard.validate_nginx(raw.replace(directive, f'{module}_temp_path /tmp;'.encode()),18081)

    def test_undeclared_dynamic_or_overridden_backend_cannot_proxy(self):
        cases=[NGINX.replace(b'set $lh_backend_identity http://identity:8080;',b''),
            NGINX.replace(b'http://identity:8080',b'$http_host'),
            NGINX.replace(b'http://identity:8080',b'http://identity:99999'),
            NGINX.replace(b'proxy_pass $lh_backend_identity',b'proxy_pass $http_host'),
            NGINX.replace(b'set $lh_backend_identity',b'set $remote_addr'),
            NGINX.replace(b'set $lh_backend_identity http://identity:8080;',
                b'set $lh_backend_identity http://identity:8080; set $lh_backend_identity http://other:8080;')]
        for raw in cases:
            with self.subTest(raw=raw),self.assertRaises(JobError):guard.validate_nginx(raw,18081)

    def test_rate_method_and_rewrite_scope_remain_finite(self):
        changes=[(b'zone=auth burst',b'zone=missing burst'),(b'rate=10r/s',b'rate=1001r/s'),
            (b'burst=20',b'burst=1025'),(b'deny all;',b'allow all;'),(b'limit_except GET',b'limit_except POST'),
            (b'rewrite ^ /realms/example/.well-known/openid-configuration break;',b'rewrite ^ https://other.test/ redirect;'),
            (b'location = /.well-known',b'location /.well-known'),(b'ipv6=off',b'ipv6=on'),
            (b'valid=10s',b'valid=0s'),(b'127.0.0.11',b'169.254.169.254')]
        for old,new in changes:
            with self.subTest(new=new),self.assertRaises(JobError):guard.validate_nginx(NGINX.replace(old,new),18081)

    def test_selected_worker_group_binds_name_gid_and_configuration(self):
        default=config();selected={**default,'worker_group':{'name':'mcp-read','gid':1234}}
        guard.validate_config(selected)
        with patch.object(guard.pwd,'getpwnam',return_value=SimpleNamespace(pw_uid=101,pw_gid=101)), \
             patch.object(guard.grp,'getgrnam',return_value=SimpleNamespace(gr_gid=1234)):
            self.assertEqual(guard.nginx_identity(default),(101,101,'nginx'))
            self.assertEqual(guard.nginx_identity(selected),(101,1234,'nginx mcp-read'))
            with self.assertRaises(JobError):guard.nginx_identity({**selected,'worker_group':{'name':'mcp-read','gid':1235}})
        a=guard.configuration_binding(default,read=lambda _:NGINX)
        b=guard.configuration_binding(selected,read=lambda _:NGINX)
        self.assertNotIn('worker_group',a);self.assertEqual(b['worker_group'],selected['worker_group'])
        for group in ({'name':'root','gid':0},{'name':'mcp; root','gid':1},{'name':'mcp','gid':True}):
            with self.subTest(group=group),self.assertRaises(JobError):guard.validate_config({**default,'worker_group':group})


class ResourcesTests(unittest.TestCase):
    def adapter(self):
        service={**limits(),'image':'sha256:'+'a'*64,'networks':{},'user':'0:0',
            'entrypoint':['/opt/local-hand/gateway/bin/python','-B','-m','local_hand_mcp.gateway_guard'],
            'command':['--config','/etc/example-gateway/guard.json'],
            'ports':[{'target':8081,'published':28081,'host_ip':'127.0.0.1'}],
            'volumes':[{'type':'bind','source':path,'target':path,'read_only':True}
                for path in ('/etc/example-gateway','/run/example-manager')]}
        profile={'project':'example','service':'gateway','container_name':'example-gateway',
            'compose':{'services':{'gateway':service}},'daemon_id':'example'}
        return GatewayAdapter(profile,SimpleNamespace(timeout=30)),service

    def test_create_preserves_limits_and_observation_rejects_each_drift(self):
        adapter,source=self.adapter()
        body=adapter._create_body({'config_digest':'b'*64,'deployment_digest':'c'*64},'test')
        expected=_resource_config(source)
        self.assertEqual(expected['Memory'],64*1024**2);self.assertEqual(expected['NanoCpus'],10**9)
        for field,value in expected.items():self.assertEqual(body['HostConfig'][field],value)
        inspected={'Image':source['image'],'Config':{'User':'0:0','Entrypoint':source['entrypoint'],
            'Cmd':source['command'],'Env':[]},'HostConfig':body['HostConfig'],
            'Mounts':[{'Type':'bind','Source':m['source'],'Destination':m['target'],'RW':False} for m in source['volumes']],
            'NetworkSettings':{'Networks':{'none':{}}}}
        with patch.object(adapter,'prerequisites',return_value={'image_id':source['image'],'image_config':{},'networks':{}}):
            self.assertTrue(adapter._matches_spec(inspected,adapter.profile['compose']))
            for field in expected:
                bad=copy.deepcopy(inspected);bad['HostConfig'][field]=None
                with self.subTest(field=field):self.assertFalse(adapter._matches_spec(bad,adapter.profile['compose']))
            tmp={'Type':'tmpfs','Source':'','Destination':'/run/local-hand-gateway','RW':True}
            inspected['Mounts'].append(tmp);self.assertTrue(adapter._matches_spec(inspected,adapter.profile['compose']))
            tmp['Destination']='/etc';self.assertFalse(adapter._matches_spec(inspected,adapter.profile['compose']))

    def test_unsafe_resource_scope_or_unlimited_values_refused(self):
        cases=[{'cpus':True},{'cpus':float('nan')},{'cpus':'1e99999999'},{'cpus':0},{'cpus':100},{'cpus':0.0000000001},
            {'mem_limit':0},{'mem_limit':'64g'},{'pids_limit':-1},{'pids_limit':True},
            {'cap_add':['SYS_ADMIN']},{'group_add':['0']},{'group_add':['1234','1234']},
            {'tmpfs':{'/etc':'size=16m'}},{'tmpfs':{'/run/local-hand-gateway':'rw,size=16m,mode=0777'}},
            {'logging':{'driver':'syslog','options':{'syslog-address':'remote'}}},
            {'logging':{'driver':'local','options':{'max-file':'0','max-size':'5m'}}}]
        for values in cases:
            with self.subTest(values=values),self.assertRaises(AdapterError):_resource_config(values)

    def test_readonly_guard_requires_runtime_tmpfs_and_exact_capabilities(self):
        adapter,source=self.adapter();environment=PlanningEnvironment({'gateway':adapter.profile})
        environment._gateway_input_mounts(config(),'/etc/example-gateway/guard.json')
        for change in ('tmpfs','capability'):
            altered=copy.deepcopy(adapter.profile['compose'])
            if change=='tmpfs':altered['services']['gateway'].pop('tmpfs')
            else:altered['services']['gateway']['cap_add'].remove('SETGID')
            with self.subTest(change=change),self.assertRaises(DeployError):
                environment._gateway_input_mounts(config(),'/etc/example-gateway/guard.json',compose=altered)


if __name__=='__main__':unittest.main()
