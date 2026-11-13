"""Server-side client for Tjipp's private age-verification pilot."""
from dataclasses import dataclass, field
import http.client
import json
import re
import ssl
from urllib.parse import urlsplit


class AgeClientError(ValueError):
    pass


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AgeClientError('invalid response')
        result[key] = value
    return result


def _invalid_constant(value):
    raise AgeClientError('invalid response')


def _origin(value):
    if not isinstance(value, str) or not re.fullmatch(r'https://[a-z0-9.-]+(?::[0-9]+)?', value):
        raise AgeClientError('invalid HTTPS origin')
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise AgeClientError('invalid HTTPS origin') from None
    if (not parsed.hostname or (port is not None and not 1 <= port <= 65535) or
            any(not label or len(label) > 63 or label.startswith('-') or label.endswith('-')
                for label in parsed.hostname.split('.'))):
        raise AgeClientError('invalid HTTPS origin')
    return parsed


def _session_fields(value):
    return all(isinstance(value.get(name), str) and
               re.fullmatch(r'[A-Za-z0-9_-]{43}', value[name]) for name in ('id', 'binding'))


@dataclass(frozen=True)
class Session:
    id: str = field(repr=False)
    binding: str = field(repr=False)
    expires_in: int
    presentation: dict = field(repr=False)


class AgeClient:
    """Keep this instance, the API key and Session in the RP's server session.

    Pass only session.presentation to the browser. A state of VERIFIED is not
    an authorization decision: consume() must succeed exactly once.
    """
    MAX_BODY = 128 * 1024
    STATES = frozenset({'STARTING', 'PENDING', 'VERIFYING', 'VERIFIED', 'DENIED',
                        'FAILED', 'EXPIRED', 'CANCELLED', 'CONSUMED'})

    def __init__(self, base_url, site_id, api_key, origin, *, ca_file=None, timeout=10):
        self._url = _origin(base_url)
        _origin(origin)
        if not isinstance(site_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', site_id):
            raise AgeClientError('invalid site ID')
        if not isinstance(api_key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43,128}', api_key):
            raise AgeClientError('invalid API key')
        if type(timeout) not in (int, float) or not 0 < timeout <= 30:
            raise AgeClientError('invalid timeout')
        self.site_id, self.origin, self._key, self.timeout = site_id, origin, api_key, timeout
        self._tls = ssl.create_default_context(cafile=ca_file)

    def _post(self, path, payload):
        connection = None
        try:
            body = json.dumps(payload, separators=(',', ':'), allow_nan=False).encode()
            if len(body) > self.MAX_BODY:
                raise AgeClientError('request too large')
            connection = http.client.HTTPSConnection(self._url.hostname, self._url.port,
                                                     timeout=self.timeout, context=self._tls)
            connection.request('POST', path, body, {'Content-Type': 'application/json',
                               'Authorization': 'Bearer ' + self._key})
            response = connection.getresponse()
            # No redirects, retries or forwarding headers: the configured origin
            # is the only destination and a lost consume response stays ambiguous.
            if response.status != 200:
                raise AgeClientError('request rejected or outcome unknown')
            lengths = response.headers.get_all('Content-Length', [])
            if (len(lengths) != 1 or not re.fullmatch(r'[0-9]+', lengths[0]) or
                    int(lengths[0]) > self.MAX_BODY or response.getheader('Transfer-Encoding') is not None or
                    response.getheader('Content-Type') != 'application/json' or
                    response.getheader('Cache-Control') != 'no-store' or
                    response.getheader('Content-Encoding') is not None):
                raise AgeClientError('invalid response')
            raw = response.read(self.MAX_BODY + 1)
            if len(raw) != int(lengths[0]):
                raise AgeClientError('invalid response')
            value = json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_constant)
            if not isinstance(value, dict):
                raise AgeClientError('invalid response')
            return value
        except Exception:
            # Server bodies and transport errors may contain credentials or proofs.
            raise AgeClientError('age request failed; do not retry consume automatically') from None
        finally:
            if connection is not None:
                connection.close()

    def start(self, method='dc_api'):
        if method not in ('dc_api', 'openid4vp'):
            raise AgeClientError('unsupported method')
        value = self._post('/age/start', {'siteId': self.site_id, 'origin': self.origin, 'method': method})
        if (set(value) != {'id', 'binding', 'expiresIn', 'presentation'} or not _session_fields(value) or
                type(value['expiresIn']) is not int or not 1 <= value['expiresIn'] <= 120):
            raise AgeClientError('invalid session')
        presentation = value['presentation']
        if not isinstance(presentation, dict) or presentation.get('method') != method:
            raise AgeClientError('invalid presentation')
        if method == 'dc_api':
            if (set(presentation) != {'method', 'requests'} or
                    not isinstance(presentation['requests'], list) or not presentation['requests'] or
                    any(not isinstance(item, dict) for item in presentation['requests'])):
                raise AgeClientError('invalid presentation')
        elif (set(presentation) != {'method', 'authorizationRequest'} or
              not isinstance(presentation['authorizationRequest'], str) or
              not presentation['authorizationRequest'].startswith('openid4vp://')):
            raise AgeClientError('invalid presentation')
        return Session(value['id'], value['binding'], value['expiresIn'], presentation)

    def _session(self, session):
        if not isinstance(session, Session) or not _session_fields({'id': session.id, 'binding': session.binding}):
            raise AgeClientError('invalid session')
        return {'siteId': self.site_id, 'id': session.id, 'binding': session.binding}

    def _state(self, value):
        if set(value) != {'state'} or not isinstance(value['state'], str) or value['state'] not in self.STATES:
            raise AgeClientError('invalid state')
        return value['state']

    def poll(self, session):
        return self._state(self._post('/age/poll', self._session(session)))

    def complete(self, session, credential):
        return self._state(self._post('/age/complete', self._session(session) | {'credential': credential}))

    def cancel(self, session):
        return self._state(self._post('/age/cancel', self._session(session)))

    def consume(self, session):
        value = self._post('/age/consume', self._session(session))
        if set(value) != {'age_over_18'} or value['age_over_18'] is not True:
            raise AgeClientError('no age approval')
        return True
