# certbot-dns-active24
Active24 DNS authenticator plugin for Certbot

An authenticator plugin for [certbot](https://certbot.eff.org/) to support [Let's Encrypt](https://letsencrypt.org/) 
DNS challenges (dns-01) for domains managed by the nameservers of [Active24](https://www.active24.cz).

This plugin is based on the [Reg.ru DNS authenticator](https://github.com/free2er/certbot-regru) by Max Pryakhin.

## Requirements
* certbot (>=0.21.1)

_Note_: it is highly recommended that you install Certbot from PyPI (`pip install certbot`), rather than your distribution's
package manager or Snap or similar - not only is the PyPI version usually the newest available, but there have been reports
of issues with the plugin when it's installed via PyPI and Certbot is not. If anyone has ideas on how this package could
be improved to fix these compatibility issues, please post an issue, or better yet, a pull request - any input or help
is much appreciated!

## Installation
1. First install the plugin:
   ```
   pip install certbot-dns-active24
   ```

2. Configure it with your Active24 credentials:
   ```
   sudo $EDITOR /etc/letsencrypt/active24.ini
   ```
   Paste the following into the configuration file:
   ```
   dns_active24_token="your-token"
   ```

3. Make sure the file is only readable by root! Otherwise all your domains might be in danger:
   ```
   sudo chmod 0600 /etc/letsencrypt/active24.ini
   ```

## Usage
Request new certificates via a certbot invocation like this:

    sudo certbot certonly -a dns-active24 -d sub.domain.tld -d *.wildcard.tld

Renewals will automatically be performed using the same authenticator and credentials by certbot.

## Note on parameter naming
For reasons beyond my comprehension some Certbot installations don't recognise the plugin when you specify it using
the abovementioned `-a dns-active24`. If Certbot complains that it can't find the plugin under that name, you need
to prefix it with the full plugin name. And even that isn't as straightforward as one could hope, because you need
to prefix both the plugin name on the command line and the plugin options in the config file, but each time with
a different variation of the prefix:

* In the config file you need to use `underscore_delimited_plugin_name`, so e.g. `certbot_dns_active24:dns_active24_token="your-token"`
* On the command line you need to use `dash-delimited-plugin-name`, so e.g. `-a certbot-dns-active24:dns-active24`

If you know how this can be fixed to work consistently across all installations, please reach out and help me do it via issue #7.

## Command Line Options
```
 --dns-active24-credentials PATH_TO_CREDENTIALS
                        Path to Active24 account credentials INI file 
                        (default: /etc/letsencrypt/active24.ini)

 --dns-active24-propagation-seconds SECONDS
                        The number of seconds to wait for DNS record changes
                        to propagate before asking the ACME server to verify
                        the DNS record. Default 0. Do not use this, the plugin
                        actually checks the authoritative nameservers repeatedly
                        to ensure the changes have propagated, regardless of
                        this setting.
```

See also `certbot --help dns-active24` for further information.

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
