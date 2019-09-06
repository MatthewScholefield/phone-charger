from os.path import abspath, join

from setuptools import setup

package_files = ['charge-phone', 'phone-charger.service']

package_data = [
    abspath(join(__file__, '..', 'phone_charger', i))
    for i in package_files
]

setup(
    name='phone-charger',
    version='0.1.0',
    description='A tool to charge android phones with a usb hub',
    url='https://github.com/matthewscholefield/phone-charger',
    author='Matthew D. Scholefield',
    author_email='matthew331199@gmail.com',
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='phone charger',
    packages=['phone_charger'],
    install_requires=[],
    entry_points={
        'console_scripts': [
            'phone-charger-setup=phone_charger.__main__:main'
        ],
    },
    package_data={
        'phone_charger': package_data
    }
)
