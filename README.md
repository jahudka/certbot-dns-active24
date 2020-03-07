# certbot-dns-active24
Active24 DNS authenticator plugin for Certbot

An authenticator plugin for [certbot](https://certbot.eff.org/) to support [Let's Encrypt](https://letsencrypt.org/) 
DNS challenges (dns-01) for domains managed by the nameservers of [Active24](https://www.active24.cz).

This plugin is based on the [Reg.ru DNS authenticator](https://github.com/free2er/certbot-regru) by Max Pryakhin.

## Requirements
* certbot (>=0.21.1)

## Installation
1. First install the plugin:
   ```
   pip install certbot-dns-active24
   ```

2. Configure it with your Active24 credentials:
   ```
   sudo vim /etc/letsencrypt/active24.ini
   ```

3. Make sure the file is only readable by root! Otherwise all your domains might be in danger:
   ```
   sudo chmod 0600 /etc/letsencrypt/active24.ini
   ```

## Usage
Request new certificates via a certbot invocation like this:

    sudo certbot certonly -a certbot-dns-active24:dns -d sub.domain.tld -d *.wildcard.tld

Renewals will automatically be performed using the same authenticator and credentials by certbot.

## Command Line Options
```
 --certbot-active24:dns-credentials PATH_TO_CREDENTIALS
                        Path to Active24 account credentials INI file 
                        (default: /etc/letsencrypt/active24.ini)

```

See also `certbot --help certbot-active24:dns` for further information.

## Removal
   ```
   sudo pip uninstall certbot-dns-active24
   ```

## Development

When releasing a new version, run `./release.sh <type>` from the project directory; `<type>` can be
either `major`, `minor` or `patch`. This will update the `__version__` constant in `certbot_dns_active24/__init__.py`,
commit the change and create an appropriate Git tag; next it will push these changes to the upstream repository,
cleanup the `dist` directory, run `python setup.py sdist`, install `twine` if it isn't already installed and
upload the latest release to PyPI. 