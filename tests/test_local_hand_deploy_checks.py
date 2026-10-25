"""Public observations are bounded, isolated and never advance deployment."""
import hashlib
import io
import os
import signal
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

from admin.local_hand_deploy import checks
from admin.local_hand_deploy.model import DeployError


class Response(io.BytesIO):
    def __init__(self, body=b'{}', status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}


class PublicCheckTests(unittest.TestCase):
    def spec(self, **extra):
        return {'url': 'https://probe.example.invalid/mcp', 'statuses': [200], **extra}

    def batch(self, *specs):
        return {'deployment_digest': 'a' * 64, 'checks': list(specs or (self.spec(),))}

    def observe(self, response, spec=None, *, error=False):
        opener = mock.Mock()
        if error: opener.open.side_effect = response
        else: opener.open.return_value = response
        with mock.patch.object(checks.urllib.request, 'build_opener', return_value=opener):
            return checks.check_public(self.batch(spec or self.spec()))

    def test_isolated_json_success_has_only_digests_and_observation(self):
        body = b'{"resource":"mcp"}'
        result = self.observe(Response(body), self.spec(json_equals={'resource': 'mcp'}))
        self.assertEqual('PASSED', result['status'])
        self.assertEqual('NOT_CHECKED', result['client_acceptance'])
        self.assertEqual('a' * 64, result['deployment_digest'])
        row = result['checks'][0]
        self.assertEqual(hashlib.sha256(body).hexdigest(), row['response_digest'])
        self.assertEqual({'endpoint_digest', 'observed_ns', 'status', 'http_status', 'response_digest'}, set(row))

    def test_request_is_get_without_ambient_proxy_or_authentication(self):
        opener = mock.Mock(); opener.open.return_value = Response()
        with mock.patch.object(checks.urllib.request, 'build_opener', return_value=opener) as build:
            self.assertEqual('PASSED', checks._request(self.spec())['status'])
        handlers = build.call_args.args
        self.assertEqual({}, handlers[0].proxies)
        self.assertIsInstance(handlers[1], checks.NoRedirect)
        request = opener.open.call_args.args[0]
        self.assertEqual('GET', request.get_method())
        self.assertNotIn('authorization', {key.lower() for key in request.headers})
        self.assertIsNone(request.data)

    def test_401_challenge_is_observed_without_following_auth(self):
        error = urllib.error.HTTPError(self.spec()['url'], 401, 'Unauthorized',
            {'WWW-Authenticate': 'Bearer resource_metadata="https://probe.example.invalid/metadata"'}, io.BytesIO(b''))
        result = self.observe(error, self.spec(statuses=[401], www_authenticate='Bearer resource_metadata='), error=True)
        self.assertEqual('PASSED', result['status'])
        self.assertEqual(401, result['checks'][0]['http_status'])
        self.assertEqual('FAILED', self.observe(Response(status=401),
            self.spec(statuses=[401], www_authenticate='Bearer'))['checks'][0]['status'])

    def test_redirect_is_not_followed_and_cannot_masquerade_as_200(self):
        request = urllib.request.Request(self.spec()['url'])
        self.assertIsNone(checks.NoRedirect().redirect_request(request, None, 302, 'Found', {},
                                                              'https://other.example.invalid/'))
        error = urllib.error.HTTPError(self.spec()['url'], 302, 'Found',
            {'Location': 'https://other.example.invalid/'}, io.BytesIO(b''))
        result = self.observe(error, error=True)
        self.assertEqual('NOT_PASSED', result['status'])
        self.assertEqual('FAILED', result['checks'][0]['status'])
        self.assertEqual(302, result['checks'][0]['http_status'])

    def test_oversize_body_is_unknown_and_never_echoed(self):
        result = self.observe(Response(b'secret' * (checks.MAX_BODY_BYTES // 6 + 1)))
        self.assertEqual('UNKNOWN', result['checks'][0]['status'])
        self.assertEqual('ValueError', result['checks'][0]['error'])
        self.assertNotIn('secret', str(result))

    def test_invalid_ambiguous_and_nonfinite_json_are_unknown(self):
        for raw in (b'not json', b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff'):
            with self.subTest(raw=raw):
                result = self.observe(Response(raw), self.spec(json_equals={'a': 1}))
                self.assertEqual('UNKNOWN', result['checks'][0]['status'])

    def test_json_expectations_distinguish_missing_null_boolean_and_integer(self):
        for raw, expected in ((b'{}', {'a': None}), (b'{"a":true}', {'a': 1}),
                              (b'{"a":1}', {'a': True})):
            with self.subTest(raw=raw, expected=expected):
                self.assertEqual('FAILED', self.observe(Response(raw),
                    self.spec(json_equals=expected))['checks'][0]['status'])

    def test_bad_later_spec_fails_before_any_request(self):
        for bad_url in ('http://probe.example.invalid/', 'https://user:pass@probe.example.invalid/',
                        'https://probe.example.invalid/?token=secret', 'https://probe.example.invalid/#secret',
                        'https://probe.example.invalid:bad/', 'https://probe.example.invalid/\nnext'):
            with self.subTest(url=bad_url), mock.patch.object(checks, '_isolated') as probe:
                with self.assertRaises(DeployError):
                    checks.check_public(self.batch(self.spec(), self.spec(url=bad_url)))
                probe.assert_not_called()

    def test_blocked_resolver_has_total_limit_and_child_is_reaped(self):
        original_fork = os.fork
        child_pids = []
        def fork():
            pid = original_fork()
            if pid: child_pids.append(pid)
            return pid
        def blocked_resolver(*args, **kwargs):
            time.sleep(10)
            return []
        started = time.monotonic()
        with mock.patch.object(checks.os, 'fork', side_effect=fork), \
                mock.patch('socket.getaddrinfo', side_effect=blocked_resolver):
            result = checks._isolated(self.spec(), timeout=.15)
        self.assertEqual({'status': 'UNKNOWN', 'error': 'PROBE_TIMEOUT'}, result)
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(1, len(child_pids))
        with self.assertRaises(ChildProcessError): os.waitpid(child_pids[0], os.WNOHANG)

    def test_slow_drip_response_cannot_extend_deadline(self):
        class SlowResponse(Response):
            def read(self, size=-1):
                # Models repeated socket reads that each finish inside the
                # socket timeout but never complete the full response.
                for _ in range(100): time.sleep(.05)
                return b'{}'
        opener = mock.Mock(); opener.open.return_value = SlowResponse()
        started = time.monotonic()
        with mock.patch.object(checks.urllib.request, 'build_opener', return_value=opener):
            result = checks._isolated(self.spec(), timeout=.15)
        self.assertEqual('PROBE_TIMEOUT', result['error'])
        self.assertLess(time.monotonic() - started, 2)

    def test_parent_deadline_kills_worker_ignoring_alarm(self):
        def ignore_alarm(_):
            signal.signal(signal.SIGALRM, signal.SIG_IGN)
            time.sleep(10)
        started = time.monotonic()
        with mock.patch.object(checks, '_request', side_effect=ignore_alarm):
            result = checks._isolated(self.spec(), timeout=.15)
        self.assertEqual('PROBE_TIMEOUT', result['error'])
        self.assertLess(time.monotonic() - started, 2)

    def test_unconfirmed_cleanup_stops_batch_without_action(self):
        with mock.patch.object(checks, '_isolated', return_value={
                'status': 'UNKNOWN', 'error': 'PROBE_CLEANUP_UNCONFIRMED'}) as probe:
            result = checks.check_public(self.batch(self.spec(), self.spec()))
        self.assertEqual(1, probe.call_count)
        self.assertEqual('NOT_PASSED', result['status'])
        self.assertEqual('NOT_CHECKED', result['client_acceptance'])


if __name__ == '__main__': unittest.main()
