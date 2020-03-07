"""DNS Authenticator for Active24 DNS."""
import logging

import requests

import zope.interface

import dns
import dns.message
import dns.name
import dns.query
import dns.rdatatype
import dns.resolver

from time import sleep

from certbot import errors
from certbot import interfaces
from certbot.plugins import dns_common

logger = logging.getLogger(__name__)


@zope.interface.implementer(interfaces.IAuthenticator)
@zope.interface.provider(interfaces.IPluginFactory)
class Authenticator(dns_common.DNSAuthenticator):
    """DNS Authenticator for Active24 DNS

    This Authenticator uses the Active24 DNS API to fulfill a dns-01 challenge.
    """

    description = 'Obtain certificates using a DNS TXT record (if you are using Active24 for DNS).'

    def __init__(self, *args, **kwargs):
        super(Authenticator, self).__init__(*args, **kwargs)
        self.credentials = None

    @classmethod
    def add_parser_arguments(cls, add):  # pylint: disable=arguments-differ
        super(Authenticator, cls).add_parser_arguments(add, default_propagation_seconds=0)
        add('credentials', help='Path to Active24 credentials INI file', default='/etc/letsencrypt/active24.ini')

    def more_info(self):  # pylint: disable=missing-docstring,no-self-use
        return 'This plugin configures a DNS TXT record to respond to a dns-01 challenge using ' + \
               'the Active24 API.'

    def _setup_credentials(self):
        self.credentials = self._configure_credentials(
            'credentials',
            'path to Active24 credentials INI file',
            {
                'token': 'API token for the Active24 account.',
            }
        )

    def _perform(self, domain, validation_name, validation):
        self._get_active24_client().add_txt_record(validation_name, validation)
        _wait_for_propagation(validation_name)

    def _cleanup(self, domain, validation_name, validation):
        self._get_active24_client().del_txt_record(validation_name, validation)

    def _get_active24_client(self):
        return _Active24Client(self.credentials.conf('token'))


def _wait_for_propagation(validation_name):
    nss = _get_nameservers(validation_name)
    query = dns.message.make_query(dns.name.from_text(validation_name), dns.rdatatype.TXT)

    while len(nss) > 0:
        nss = [ns for ns in nss if len(dns.query.udp(query, ns).answer) == 0]
        sleep(1)


def _get_nameservers(domain):
    resolver = dns.resolver.get_default_resolver()
    answer = resolver.query(domain, 'NS', raise_on_no_answer=False)
    nameservers = [rr.target.to_text() for rr in answer.response.authority[0]]
    return [resolver.query(ns)[0].to_text() for ns in nameservers]


class _Active24Client(object):
    """
    Encapsulates all communication with the Active24
    """

    def __init__(self, token):
        self.token = token if isinstance(token, str) else ','.join(token)
        self.test = False

    def add_txt_record(self, record_name, record_content):
        """
        Add a TXT record using the supplied information.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :param str record_content: The record content (typically the challenge validation).
        :raises certbot.errors.PluginError: if an error occurs communicating with the Active24 API
        """

        domain, record = self._parse_domain(record_name)

        try:
            logger.debug('Attempting to add record: %s', record)
            response = self._send_request('POST', '/dns/{0}/txt/v1'.format(domain), {
                'name': record,
                'text': record_content,
                'ttl': 300,
            })
        except requests.exceptions.RequestException as e:
            logger.error('Encountered error adding TXT record: %s', e)
            raise errors.PluginError('Error communicating with the Active24 API: {0}'.format(e))

        if response.status_code != 204:
            logger.error('Encountered error adding TXT record: %s', response)
            raise errors.PluginError('Error communicating with the Active24 API: {0}'.format(response))

        logger.debug('Successfully added TXT record')

    def del_txt_record(self, record_name, record_content):
        """
        Delete a TXT record using the supplied information.
        Note that both the record's name and content are used to ensure that similar records
        created concurrently (e.g., due to concurrent invocations of this plugin) are not deleted.
        Failures are logged, but not raised.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :param str record_content: The record content (typically the challenge validation).
        """

        domain, record = self._parse_domain(record_name)

        try:
            logger.debug('Attempting to delete record: %s', record)
            hash_id = self._find_hash_id(domain, record)
            response = self._send_request('DELETE', '/dns/{0}/{1}/v1'.format(domain, hash_id))
        except requests.exceptions.RequestException as e:
            logger.warning('Encountered error deleting TXT record: %s', e)
            return

        if response.status_code != 204:
            logger.warning('Encountered error deleting TXT record: %s', response)
            return

        logger.debug('Successfully deleted TXT record.')

    def _find_hash_id(self, domain_name, record_name):
        response = self._send_request('GET', '/dns/{0}/records/v1'.format(domain_name))
        records = response.json()

        for record in records:
            if record['name'] == record_name:
                return record['hashId']

        raise RuntimeError('Cannot find DNS record "{0}" for domain "{1}"'.format(record_name, domain_name))

    def _parse_domain(self, domain):
        """
        Parses full domain into base domain name and record name
        :param str domain: Domain name
        :returns: Top-level
        :rtype: tuple
        """
        pieces = domain.split('.')
        return '.'.join(pieces[-2:]), '.'.join(pieces[:-2])

    def _send_request(self, method, endpoint, payload=None):
        base_url = 'https://sandboxapi.active24.com' if self.test else 'https://api.active24.com'

        response = requests.request(
            method,
            base_url + endpoint,
            json=payload,
            headers={'Authorization': 'Bearer ' + self.token}
        )

        response.raise_for_status()
        return response
