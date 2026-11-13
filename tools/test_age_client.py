import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from email.message import Message

from age_client import AgeClient, AgeClientError, Session


class Response:
    def __init__(self, value, status=200, raw=None, headers=None):
        self.body = json.dumps(value).encode() if raw is None else raw
        self.status = status
        self.headers = Message()
        for key, val in (headers or {'Content-Type': 'application/json', 'Content-Length': str(len(self.body)),
                                    'Cache-Control': 'no-store'}).items():
            self.headers[key] = val

    def getheader(self, key):
        return self.headers.get(key)

    def read(self, maximum):
        return self.body[:maximum]


class Connection:
    def __init__(self, response):
        self.response, self.requests, self.closed = response, [], False

    def request(self, method, path, body, headers):
        self.requests.append((method, path, json.loads(body), headers))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class AgeClientTest(unittest.TestCase):
    def setUp(self):
        self.key = 'k' * 43
        self.client = AgeClient('https://age.example', 'municipality', self.key, 'https://service.example')
        self.session = Session('i' * 43, 'b' * 43, 120, {})

    def call(self, response, operation):
        conn = Connection(response)
        with patch('age_client.http.client.HTTPSConnection', return_value=conn):
            result = operation()
        self.assertTrue(conn.closed)
        return result, conn.requests

    def test_start_has_fixed_origin_and_no_secret_in_repr(self):
        response = {'id': 'i' * 43, 'binding': 'b' * 43, 'expiresIn': 119,
                    'presentation': {'method': 'dc_api', 'requests': [{'protocol': 'org-iso-mdoc', 'data': {}}]}}
        session, requests = self.call(Response(response), self.client.start)
        self.assertNotIn('b' * 43, repr(session))
        method, path, body, headers = requests[0]
        self.assertEqual(('POST', '/age/start'), (method, path))
        self.assertEqual({'siteId': 'municipality', 'origin': 'https://service.example', 'method': 'dc_api'}, body)
        self.assertEqual({'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.key}, headers)

    def test_consumption_requires_exact_boolean_and_no_identity(self):
        for value in [{'age_over_18': False}, {'age_over_18': 1}, {'age_over_18': 'true'},
                      {'age_over_18': True, 'name': 'Synthetic'}, {'state': 'VERIFIED'}]:
            with self.subTest(value=value), self.assertRaises(AgeClientError):
                self.call(Response(value), lambda: self.client.consume(self.session))
        ok, requests = self.call(Response({'age_over_18': True}), lambda: self.client.consume(self.session))
        self.assertIs(ok, True)
        self.assertEqual('b' * 43, requests[0][2]['binding'])

    def test_redirect_error_or_lost_response_never_retried_or_echoed(self):
        for status in [301, 302, 307, 400, 401, 429, 500]:
            connection = Connection(Response({'secret': self.key}, status))
            with patch('age_client.http.client.HTTPSConnection', return_value=connection), self.assertRaises(AgeClientError) as error:
                self.client.consume(self.session)
            self.assertEqual(1, len(connection.requests))
            self.assertNotIn(self.key, str(error.exception))
            self.assertTrue(connection.closed)
        with patch('age_client.http.client.HTTPSConnection', side_effect=OSError(self.key)), self.assertRaises(AgeClientError) as error:
            self.client.consume(self.session)
        self.assertNotIn(self.key, str(error.exception))

    def test_bad_json_framing_and_cacheable_responses_rejected(self):
        responses = [Response({}, raw=b'{"state":"VERIFIED","state":"DENIED"}'),
                     Response({}, raw=b'{"state":NaN}'), Response({}, raw=b'[]'),
                     Response({}, headers={'Content-Length': '999999', 'Content-Type': 'application/json', 'Cache-Control': 'no-store'}),
                     Response({}, headers={'Content-Length': '2', 'Content-Type': 'application/json'}),
                     Response({}, headers={'Content-Length': '2', 'Transfer-Encoding': 'chunked', 'Content-Type': 'application/json', 'Cache-Control': 'no-store'})]
        for response in responses:
            with self.subTest(response=response), self.assertRaises(AgeClientError):
                self.call(response, lambda: self.client.poll(self.session))

    def test_session_state_and_method_are_checked(self):
        for value in [{'state': []}, {'state': 'APPROVED'}, {'state': 'VERIFIED', 'binding': 'leak'}]:
            with self.subTest(value=value), self.assertRaises(AgeClientError):
                self.call(Response(value), lambda: self.client.poll(self.session))
        for method in ('poll', 'cancel', 'complete'):
            args = (self.session, {}) if method == 'complete' else (self.session,)
            state, requests = self.call(Response({'state': 'PENDING'}), lambda: getattr(self.client, method)(*args))
            self.assertEqual('PENDING', state)
            self.assertEqual('/age/' + method, requests[0][1])
        with self.assertRaises(AgeClientError):
            self.client.start('automatic-fallback')

    def test_http_credentials_urls_and_injected_host_are_rejected(self):
        for url in ['http://age.example', 'https://a:b@age.example', 'https://age.example/path',
                    'https://age.example?key=1', 'https://age.example\n', 'https://age.example:99999']:
            with self.subTest(url=url), self.assertRaises(AgeClientError):
                AgeClient(url, 'municipality', self.key, 'https://service.example')

    def test_openapi_examples_and_operations_match_client(self):
        spec = json.loads((Path(__file__).resolve().parents[1] / 'openapi/age-verification.json').read_text())
        self.assertEqual('3.0.1', spec['openapi'])
        self.assertEqual({'/age/' + name for name in ('start', 'poll', 'complete', 'consume', 'cancel')}, set(spec['paths']))
        for path, item in spec['paths'].items():
            self.assertEqual({'post'}, set(item))
            self.assertEqual([{'SiteKey': []}], item['post']['security'])
            response = item['post']['responses']['200']['content']['application/json']['example']
            if path == '/age/start':
                self.call(Response(response), self.client.start)
            elif path == '/age/consume':
                self.call(Response(response), lambda: self.client.consume(self.session))
            else:
                self.assertIn(response['state'], self.client.STATES)


if __name__ == '__main__':
    unittest.main()
