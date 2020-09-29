from setuptools import setup
from setuptools import find_packages

from certbot_dns_active24 import __version__

install_requires = [
    'acme>=0.21.1',
    'certbot>=0.21.1',
    'dnspython>=1.16.0',
    'requests>=2.9.1',
    'mock',
    'setuptools',
    'zope.interface',
]

data_files = [
    ('/etc/letsencrypt', ['active24.ini'])
]

with open('README.md') as f:
    long_description = f.read()

setup(
    name='certbot-dns-active24',
    version=__version__,
    description="Active24 DNS authenticator plugin for Certbot",
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='certbot letsencrypt dns-01 plugin',
    url='https://github.com/jahudka/certbot-dns-active24',
    download_url='https://github.com/jahudka/certbot-dns-active24/archive/v' + __version__ + '.tar.gz',
    author="Dan Kadera",
    author_email='me@subsonic.cz',
    license='MIT',
    python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Plugins',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Security',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Networking',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],
    install_requires=install_requires,
    data_files=data_files,
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'certbot.plugins': [
            'dns-active24 = certbot_dns_active24.dns_active24:Authenticator',
        ],
    },
    test_suite='certbot_dns_active24',
)
