"""Tests for certbot_dns_active24.dns."""

import os
import unittest

import mock
import requests

from certbot import errors
from certbot.plugins import dns_test_common
from certbot.plugins.dns_test_common import DOMAIN
from certbot.tests import util as test_util

TOKEN = '123456qwerty-ok'

HTTP_ERROR = requests.exceptions.RequestException()


class AuthenticatorTest(test_util.TempDirTestCase, dns_test_common.BaseAuthenticatorTest):

    def setUp(self):
        from certbot_dns_active24.dns_active24 import Authenticator

        super(AuthenticatorTest, self).setUp()

        path = os.path.join(self.tempdir, 'file.ini')
        dns_test_common.write({"active24_token": TOKEN}, path)

        self.config = mock.MagicMock(active24_credentials=path, active24_propagation_seconds=0)  # don't wait during tests

        self.auth = Authenticator(self.config, "active24")

        self.mock_client = mock.MagicMock()
        # _get_active24_client | pylint: disable=protected-access
        self.auth._get_active24_client = mock.MagicMock(return_value=self.mock_client)

    def test_perform(self):
        self.auth.perform([self.achall])

        expected = [mock.call.add_txt_record('_acme-challenge.' + DOMAIN, mock.ANY)]
        self.assertEqual(expected, self.mock_client.mock_calls)

    def test_cleanup(self):
        # _attempt_cleanup | pylint: disable=protected-access
        self.auth._attempt_cleanup = True
        self.auth.cleanup([self.achall])

        expected = [mock.call.del_txt_record('_acme-challenge.' + DOMAIN, mock.ANY)]
        self.assertEqual(expected, self.mock_client.mock_calls)


class Active24ClientTest(unittest.TestCase):

    record_prefix = "_acme-challenge"
    record_name = record_prefix + "." + DOMAIN
    record_content = "test"

    def setUp(self):
        from certbot_dns_active24.dns_active24 import _Active24Client

        self.client = _Active24Client(TOKEN)

        # _send_request | pylint: disable=protected-access
        self.client._send_request = mock.Mock()

    def test_add_txt_record(self):
        self.client._send_request.side_effect = [self._create_response(204)]
        self.client.add_txt_record(self.record_name, self.record_content)
        self.client._send_request.assert_called_with('POST', '/dns/{0}/txt/v1'.format(DOMAIN), {
            'name': self.record_prefix,
            'text': self.record_content,
            'ttl': 300,
        })

    def test_add_txt_record_subdomain(self):
        self.client._send_request.side_effect = [self._create_response(204)]
        self.client.add_txt_record(self.record_prefix + '.subdomain.' + DOMAIN, self.record_content)
        self.client._send_request.assert_called_with('POST', '/dns/{0}/txt/v1'.format(DOMAIN), {
            'name': self.record_prefix + '.subdomain',
            'text': self.record_content,
            'ttl': 300,
        })

    def test_add_txt_record_error_send_request(self):
        self.client._send_request.side_effect = HTTP_ERROR
        self.assertRaises(errors.PluginError, self.client.add_txt_record, self.record_name, self.record_content)

    def test_del_txt_record(self):
        self.client._send_request.side_effect = [
            self._create_response(200, [{'name': self.record_prefix, 'hashId': 'asdfqwert'}]),
            self._create_response(204)
        ]
        self.client.del_txt_record(self.record_name, self.record_content)

    def test_del_txt_record_subdomain(self):
        self.client._send_request.side_effect = [
            self._create_response(200, [{'name': self.record_prefix + '.subdomain', 'hashId': 'asdfqwert'}]),
            self._create_response(204)
        ]
        self.client.del_txt_record(self.record_prefix + '.subdomain.' + DOMAIN, self.record_content)

    def _create_response(self, status=200, payload=None):
        def rfs():
            if status >= 400:
                raise requests.exceptions.HTTPError()

        res = mock.Mock()
        res.status_code = status
        res.json = lambda: payload
        res.raise_for_status = rfs
        return res


if __name__ == "__main__":
    unittest.main()  # pragma: no cover
