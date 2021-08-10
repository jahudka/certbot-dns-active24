"""DNS Authenticator for Active24 DNS."""
import logging

import requests

import zope.interface

import signal

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

    def perform(self, achalls):
        responses = super(Authenticator, self).perform(achalls)

        if self.conf('propagation-seconds') <= 0:
            _wait_for_propagation(achalls)

        return responses

    def _perform(self, domain, validation_name, validation):
        self._get_active24_client().add_txt_record(validation_name, validation)

    def _cleanup(self, domain, validation_name, validation):
        self._get_active24_client().del_txt_record(validation_name, validation)

    def _get_active24_client(self):
        return _Active24Client(self.credentials.conf('token'))


def _wait_for_propagation(challenges):
    queue = [(ch.validation_domain_name(ch.domain), ch.validation(ch.account_key)) for ch in challenges]
    queue = [(o[0], o[1], dns.message.make_query(dns.name.from_text(o[0]), dns.rdatatype.TXT)) for o in queue]
    queue = [(ns, o[1], o[2]) for o in queue for ns in _get_nameservers(o[0])]

    logger.debug('Waiting for propagation to authoritative servers')
    i = 0

    def break_loop(*_):
        logger.debug('Interrupted by user signal')
        queue.clear()

    orig = signal.signal(signal.SIGUSR1, break_loop)

    while len(queue) > 0:
        queue = [(ns, content, query) for (ns, content, query) in queue if not _check_nameserver(ns, query, content)]
        sleep(1)
        i += 1

        if (i % 30) == 0:
            logger.debug('Remaining records to check: %d' % len(queue))

    signal.signal(signal.SIGUSR1, orig)


def _check_nameserver(ns, query, content):
    result = dns.query.udp(query, ns)

    try:
        answers = [a for r in result.answer for a in r]

        for a in answers:
            value = ''.join([s.decode('utf-8') for s in a.strings])

            if value == content:
                return True
    except (KeyError, IndexError):
        return False

    return False


def _get_nameservers(domain):
    resolver = dns.resolver.get_default_resolver()

    while True:
        try:
            rrset = resolver.query(domain, 'NS')
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            try:
                domain = domain[domain.index('.') + 1:]
                continue
            except ValueError:
                return []

        if len(rrset) == 0:
            return []

        nameservers = [resolver.query(rr.target.to_text(), raise_on_no_answer=False) for rr in rrset]
        return [ns[0].to_text() for ns in nameservers if len(ns) > 0]


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
        logger.debug('Attempting to add record: %s' % record)

        try:
            response = self._send_request('POST', '/dns/%s/txt/v1' % domain, {
                'name': record,
                'text': record_content,
                'ttl': 300,
            })
        except requests.exceptions.RequestException as e:
            logger.error('Encountered error adding TXT record: %s', e)

            if e.response is not None:
                logger.error(e.response.text)

            raise errors.PluginError('Error communicating with the Active24 API: %s' % e)

        if response.status_code != 204:
            logger.error('Encountered error adding TXT record: %s' % response)
            raise errors.PluginError('Error communicating with the Active24 API: %s' % response)

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
        logger.debug('Attempting to delete record: %s' % record)
        dns_record = self._find_record(domain, record, record_content)

        if dns_record is not None:
            try:
                response = self._send_request('DELETE', '/dns/%s/%s/v1' % (domain, dns_record['hashId']))
            except requests.exceptions.RequestException as e:
                logger.warning('Encountered error deleting TXT record: %s' % e)
                return
        else:
            logger.debug('Record doesn\'t appear to exist, aborting')
            return

        if response.status_code != 204:
            logger.warning('Encountered error deleting TXT record: %s' % response)
            return

        logger.debug('Successfully deleted TXT record.')

    def _find_record(self, domain_name, record_name, record_content):
        response = self._send_request('GET', '/dns/%s/records/v1' % domain_name)
        records = response.json()

        for record in records:
            if record['type'] == 'TXT' and record['name'] == record_name and record['text'] == record_content:
                return record

        return None

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
            headers={'Authorization': 'Bearer %s' % self.token}
        )

        response.raise_for_status()
        return response
