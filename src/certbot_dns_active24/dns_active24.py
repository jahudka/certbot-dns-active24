"""DNS Authenticator for Active24 DNS."""
import logging

import requests

import zope.interface
from typing import List

import dns.query
import dns.resolver
from dns.exception import DNSException

import hmac
import hashlib
from datetime import datetime, timezone
from time import time, sleep

from acme import challenges
from certbot import achallenges
from certbot import errors
from certbot import interfaces
from certbot.plugins import dns_common
from certbot.display import util as display_util
from requests import Response

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
        super(Authenticator, cls).add_parser_arguments(add, default_propagation_seconds=300)
        add('credentials', help='Path to Active24 credentials INI file', default='/etc/letsencrypt/active24.ini')

    def more_info(self):  # pylint: disable=missing-docstring,no-self-use
        return 'This plugin configures a DNS TXT record to respond to a dns-01 challenge using ' + \
               'the Active24 REST API v2.'

    def perform(self, achalls: List[achallenges.AnnotatedChallenge]
                ) -> List[challenges.ChallengeResponse]: # pylint: disable=missing-function-docstring
        self._setup_credentials()

        self._attempt_cleanup = True

        responses = []
        for achall in achalls:
            domain = achall.domain
            validation_domain_name = achall.validation_domain_name(domain)
            validation = achall.validation(achall.account_key)

            self._perform(domain, validation_domain_name, validation)
            responses.append(achall.response(achall.account_key))

        propagation_delay = self.conf('propagation-seconds')

        if propagation_delay > 0:
            display_util.notify(f'Waiting at most {propagation_delay} seconds for DNS changes to propagate')
            wait_until = time() + propagation_delay
        else:
            display_util.notify(f'Waiting for DNS changes to propagate')
            wait_until = time() + 3600

        while time() < wait_until:
            if _all_challenges_propagated(achalls):
                break
            sleep(5)

        return responses

    def _setup_credentials(self):
        self.credentials = self._configure_credentials(
            'credentials',
            'Path to Active24 credentials INI file',
            {
                'api_key': 'API key for the Active24 account.',
                'secret': 'Secret key for the Active24 account.',
            }
        )

    def _perform(self, domain, validation_name, validation):
        self._get_active24_client().add_txt_record(validation_name, validation)

    def _cleanup(self, domain, validation_name, validation):
        self._get_active24_client().del_txt_record(validation_name, validation)

    def _get_active24_client(self):
        return _Active24Client(self.credentials.conf('api_key'), self.credentials.conf('secret'))


class _Active24Client(object):
    """
    Encapsulates all communication with the Active24
    """

    def __init__(self, api_key, secret):
        self.api_key = api_key
        self.secret = secret
        self.test = False

    def add_txt_record(self, record_name, record_content):
        """
        Add a TXT record using the supplied information.
        :param str record_name: The record name (typically beginning with '_acme-challenge.').
        :param str record_content: The record content (typically the challenge validation).
        :raises certbot.errors.PluginError: if an error occurs communicating with the Active24 API
        """

        domain, record = self._parse_domain(record_name)
        logger.debug('Attempting to add record %s with content %s' % (record, record_content))

        try:
            service = self._find_service(domain)

            response = self._send_request('POST', '/v2/service/%s/dns/record' % service, {
                'type': 'TXT',
                'name': record,
                'content': record_content,
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
        service = self._find_service(domain)
        dns_record = self._find_record(service, record_name, record_content)

        if dns_record is not None:
            try:
                response = self._send_request('DELETE', '/v2/service/%s/dns/record/%s' % (service, dns_record['id']))
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

    def _find_service(self, domain_name):
        response = self._send_request('GET', '/v1/user/self/service')
        payload = response.json()

        for service in payload['items']:
            if service['serviceName'] == 'domain' and service['name'] == domain_name:
                return service['id']

        return None

    def _find_record(self, service, record_name, record_content):
        response = self._send_request('GET', '/v2/service/%d/dns/record' % service, query={
            'name': record_name,
            'type': ['TXT'],
        })
        payload = response.json()

        for record in payload['data']:
            if record['type'] == 'TXT' and record['name'] == record_name and record['content'] == record_content:
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

    def _send_request(self, method, path, payload=None, query=None) -> Response:
        base_url = 'https://rest.active24.cz'
        timestamp = int(time())
        request = "%s %s %s" % (method, path, timestamp)
        signature = hmac.new(bytes(self.secret, 'UTF-8'), bytes(request, 'UTF-8'), hashlib.sha1).hexdigest()

        response = requests.request(
            method,
            base_url + path,
            json=payload,
            params=query,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Date": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
            },
            auth=(
                self.api_key,
                signature,
            ),
        )

        response.raise_for_status()
        return response


def _all_challenges_propagated(achalls: List[achallenges.AnnotatedChallenge]) -> bool:
    for achall in achalls:
        try:
            if not _has_propagated(achall.validation_domain_name(achall.domain),
                                   achall.validation(achall.account_key)):
                return False
        except:
            return False

    return True

def _has_propagated(record: str, challenge: str) -> bool:
    nameservers = _resolve_authoritative_nameservers(record)
    query = dns.message.make_query(record, dns.rdatatype.TXT)

    for ns in nameservers:
        response = dns.query.udp(query, ns)
        rcode = response.rcode()

        if rcode != dns.rcode.NOERROR:
            return False

        for rrset in response.answer:
            for rr in rrset:
                if rr.rdtype == dns.rdatatype.TXT and rr.to_text().strip('"') != challenge:
                    return False

    return True

def _resolve_authoritative_nameservers(domain: str) -> List[str]:
    default = dns.resolver.get_default_resolver()
    ns = default.nameservers[0]
    parts = domain.split('.')
    result = list()

    for i in range(len(parts), 0, -1):
        sub = '.'.join(parts[i-1:])
        query = dns.message.make_query(sub, dns.rdatatype.NS)
        response = dns.query.udp(query, ns)
        rcode = response.rcode()

        if rcode != dns.rcode.NOERROR:
            if rcode == dns.rcode.NXDOMAIN:
                raise DNSException(f'{sub} does not exist.')
            else:
                raise DNSException(f'Error {dns.rcode.to_text(rcode)}')

        if len(response.authority) > 0:
            rrsets = response.authority
        elif len(response.additional) > 0:
            rrsets = [response.additional]
        else:
            rrsets = response.answer

        for rrset in rrsets:
            for rr in rrset:
                if rr.rdtype == dns.rdatatype.A:
                    ns = rr.items[0].address
                elif rr.rdtype == dns.rdatatype.NS:
                    ns = default.resolve(rr.to_text()).rrset[0].to_text()
                    result = rrset

    return [default.resolve(rr.to_text()).rrset[0].to_text() for rr in result]
