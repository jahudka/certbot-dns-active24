# certbot-dns-active24
Active24 DNS authenticator plugin for Certbot

An authenticator plugin for [certbot][1] to support [Let's Encrypt][2] 
DNS challenges (dns-01) for domains managed by the nameservers of [Active24][3].

This plugin is based on the [ISPConfig DNS authenticator][4] by Matthias Bilger.

## Important: Active24 REST API versions

The current version of this plugin (2.x) is implemented against the new Active24 REST API v2.
If you wish to use the old v1 API, you can still use [the 1.x branch][5], it should work
perfectly well.

## Requirements
* certbot (>=0.34.0)

_Note_: it is highly recommended that you install Certbot from PyPI (`pip install certbot`),
rather than your distribution's package manager or Snap or similar - not only is the PyPI
version usually the newest available, but there have been reports of issues with the plugin
when it's installed via PyPI and Certbot is not. If anyone has ideas on how this package
could be improved to fix these compatibility issues, please post an issue, or better yet,
a pull request - any input or help is much appreciated!

## Installation
1. First install the plugin:
   ```shell
   pip install certbot-dns-active24
   ```

2. Configure it with your Active24 credentials:
   ```shell
   sudo $EDITOR /etc/letsencrypt/active24.ini
   ```
   Paste the following into the configuration file:
   ```
   certbot_dns_active24:dns_active24_api_key = "your api key"
   certbot_dns_active24:dns_active24_secret = "your secret"
   ```

3. Make sure the file is only readable by root! Otherwise all your domains might be in danger:
   ```shell
   sudo chmod 0600 /etc/letsencrypt/active24.ini
   ```

## Usage
Request new certificates via a certbot invocation like this:

```shell
sudo certbot certonly -a certbot-dns-active24:dns-active24 -d sub.domain.tld -d *.wildcard.tld
```

Renewals will automatically be performed using the same authenticator and credentials by certbot.

## Command Line Options
```
 --certbot-dns-active24:dns-active24-credentials PATH_TO_CREDENTIALS
                        Path to Active24 account credentials INI file 
                        (default: /etc/letsencrypt/active24.ini)

 --certbot-dns-active24:dns-active24-propagation-seconds SECONDS
                        The number of seconds to wait for DNS record changes
                        to propagate before asking the ACME server to verify
                        the DNS record. Default 300.
```

## Removal

```shell
sudo pip uninstall certbot-dns-active24
```

## Development

When releasing a new version, commit all changes, create an appropriate Git tag, and then run
`./release.sh` from the project directory. This will check and prepare your environment,
push the latest code to GitHub, build the distribution package and upload it to PyPI.


[1]: https://certbot.eff.org/
[2]: https://letsencrypt.org/
[3]: https://www.active24.cz
[4]: https://github.com/m42e/certbot-dns-ispconfig
[5]: https://github.com/jahudka/certbot-dns-active24/tree/v1.x
