from time import sleep

import os
import re
import shutil
import subprocess
from argparse import ArgumentParser
from os import getcwd, chdir
from os.path import isfile, dirname, join, abspath
from pkg_resources import resource_filename, Requirement
from subprocess import CalledProcessError, PIPE
from tempfile import mkdtemp, mkstemp


def get_command(exe, *args):
    if ' ' in exe and not args:
        return exe.split(' ')
    else:
        return [exe] + [str(i) for i in args]


def call(exe, *args, **kwargs):
    return subprocess.call(get_command(exe, *args), **kwargs)


def run(exe, *args, **kwargs):
    return subprocess.check_output(get_command(exe, *args), **kwargs).decode().strip().split('\n')


def require_call(exe, *args, **kwargs):
    ret = call(exe, *args, **kwargs)
    if ret != 0:
        print('Error, command returned code {}: {}'.format(ret, [exe] + list(args)))
        raise SystemExit(1)


def install_uhubctl():
    if not shutil.which('make'):
        if shutil.which('apt-get'):
            print('Installing build tools...')
            if call('sudo apt-get install -y build-essential') != 0:
                print('Installing build-essential with apt-get failed!')
                raise SystemExit(1)
        else:
            print('Please install "make" and relevant build tools (g++)')
            raise SystemExit(1)

    uhub_exe = shutil.which('uhubctl', path=os.environ.get('PATH', '') + ':/usr/sbin')
    if not uhub_exe:
        tmp = mkdtemp()
        call('git', 'cloneg     ', 'https://github.com/mvp/uhubctl', tmp)
        prev = getcwd()
        try:
            chdir(tmp)
            print('Compiling uhubctl...')
            try:
                run('make')
            except CalledProcessError:
                if shutil.which('apt-get'):
                    if call('sudo apt-get install -y libusb-1.0-0-dev') != 0:
                        print('Failed to install libusb')
                        raise SystemExit(1)
                else:
                    call('make')
                    print('uhubctl compilation failed. Make sure to install libusb-1.0-0-dev')
                    raise SystemExit(1)
            print('Installing executable...')
            if call('sudo make install') != 0:
                print('Install failed.')
                raise SystemExit(1)
            uhub_exe = '/usr/sbin/uhubctl'
        finally:
            chdir(prev)
    return uhub_exe


def install_adb():
    exe = shutil.which('adb')
    if exe:
        return exe
    if shutil.which('apt-get'):
        print('Installing adb...')
        call('sudo apt-get install -y android-tools-adb')
        exe = shutil.which('adb')
        if exe:
            return exe
    print('Could not automatically install adb. Try installing adb and rerun this program.')
    raise SystemExit(1)


def get_adb_devices(adb):
    return {
        m.group(1): m.group(2)
        for m in [re.match(r'([a-f0-9]{8})\s+(.*)', i) for i in run(adb, 'devices')]
        if m
    }


def enable_device_perm(setup_device):
    udev_rule_path = '/etc/udev/rules.d/53-pi-phone-charger.rules'
    exe_path = '/opt/phone-charger/charge-phone'
    systemd_path = '/etc/systemd/system/phone-charger.service'
    dev_mode_fmt = 'SUBSYSTEM=="usb", ATTR{{idVendor}}=="{vendor_id}", ' \
                   'ATTR{{idProduct}}=="{product_id}", MODE="0666", ' \
                   'GROUP="plugdev", SYMLINK+="{link_name}", TAG+="systemd"'
    regex_vars = dict(vendor_id='([a-f0-9]{4})', product_id='([a-f0-9]{4})', link_name='([^"]*)')

    if setup_device:
        device_id_str = guide_and_find_device_id()
        info = get_usb_info()[device_id_str]

        print('Writing to {}...'.format(udev_rule_path))
        if isfile(udev_rule_path):
            call('sudo', 'chmod', '0666', udev_rule_path)
            with open(udev_rule_path) as f:
                data = f.read()
        else:
            data = ''

        matches = [
            re.match(re.escape(dev_mode_fmt).replace(r'\{', '{').replace(r'\}', '}').format(**regex_vars), l)
            for l in data.split('\n')
        ]
        existing = {
            (m.group(1), m.group(2))
            for m in matches if m
        }
        vendor_id, product_id = device_id_str.split(':')
        device_id = (vendor_id, product_id)

        if device_id in existing:
            print('Device already set to charge!')
            print('Continuing remaining setup...')
        else:
            print('Setting up device permissions...')
            call('sudo', 'mkdir', '-vp', dirname(udev_rule_path))
            line = dev_mode_fmt.format(vendor_id=vendor_id, product_id=product_id, link_name=info)
            new_data = data + '\n' + line
            fd, filename = mkstemp()
            try:
                os.write(fd, new_data.encode())
                os.close(fd)
                call('sudo', 'cp', '-v', filename, udev_rule_path)
            finally:
                os.remove(filename)
        print('Setting up adb...')
        adb = install_adb()
        print('Getting adb devices...')
        if device_id not in existing:
            print('Unlock your phone and accept any prompts for USB Debugging')
            sleep(1)
        devices = get_adb_devices(adb)
        if not devices:
            print('No device detected. Please ensure USB Debugging is authorized and try again.')
            raise SystemExit(1)
        print('Devices found:', ', '.join(devices.values()))

    uhubctl_exe = install_uhubctl()
    try:
        run(uhubctl_exe)
    except CalledProcessError:
        print('Permissions not set up. Configuring...')
        output = run('sudo', uhubctl_exe)
        m = re.search(r'[a-f0-9]{4}:[a-f0-9]{4}', output.split('\n')[0])
        if not m:
            print('Invalid uhub output:', output)
            raise SystemExit(1)
        hub_vendor_id, _ = m.group(0).split(':')
        hub_cmd_fmt = 'SUBSYSTEM=="usb", ATTR{{idVendor}}=="{vendor_id}", MODE="0666"\n'
        fd, filename = mkstemp()
        try:
            os.write(fd, hub_cmd_fmt.format(vendor_id=hub_vendor_id).encode())
        finally:
            os.remove(filename)
        print('Writing uhub permissions in /etc/udev...')
        hub_perm_file = '/etc/udev/rules.d/52-usb.rules'
        if isfile(hub_perm_file):
            print('Error, {} already exists'.format(hub_perm_file))
            raise SystemExit(1)

        assert call('mv', '-v', filename, hub_perm_file) == 0
        print('Reloading udev rules...')
        call('sudo udevadm trigger --attr-match=subsystem=usb')
        if call(uhubctl_exe) != 0:
            print('uhubctl still failed to run')
            raise SystemExit(1)

    charge_script = '/opt/charge-phone'
    if not isfile(charge_script):
        print('Setting up charge script at {}'.format(charge_script))
        call('sudo', 'cp', '-v', abspath(join(__file__, '..', 'charge-phone')), charge_script)

    if not shutil.which('adb'):  # Needed by script
        install_adb()

    print('Reloading rules...')
    if call('sudo udevadm control --reload-rules') != 0 or call('sudo udevadm trigger') != 0:
        print('Failed to reload rules!')
        raise SystemExit(1)

    print('Setting up service...')
    call('sudo', 'mkdir', '-vp', dirname(exe_path))
    mod_path = resource_filename(Requirement.parse("phone_charger"), 'phone_charger')
    local_script = join(mod_path, 'charge-phone')
    local_service = join(mod_path, 'phone-charger.service')

    try:
        run('sudo systemctl stop phone-charger', stderr=PIPE)
    except CalledProcessError:
        pass

    require_call('sudo', 'cp', '-v', local_script, exe_path)
    require_call('sudo', 'cp', '-v', local_service, systemd_path)
    require_call('sudo systemctl daemon-reload')
    require_call('sudo systemctl enable phone-charger')
    require_call('sudo systemctl start phone-charger')
    print('Waiting for service to start...')
    sleep(2)
    require_call('sudo systemctl status phone-charger')
    print('Setup everything successfully!')


def get_usb_info():
    info = {}
    for i in run('lsusb'):
        m = re.search(r'[0-9a-f]{4}:[0-9a-f]{4}', i)
        info[m.group()] = i[m.end():].strip()
    return info


def guide_and_find_device_id():
    input('Unplug your device. (Enter to continue)')
    prev_ids = set(get_usb_info())
    input('Plug your device in with USB debugging enabled. (Enter to continue)')
    info = get_usb_info()
    new_ids = set(info) - prev_ids

    if len(new_ids) > 1:
        print('Multiple new devices detected: {}'.format(', '.join(info[i] for i in new_ids)))
        raise SystemExit(1)

    if len(new_ids) == 0:
        print('No new devices detected. Make sure your phone is plugged in '
              'with a data cable and try waiting longer after plugging it in')
        raise SystemExit(1)

    device_id = next(iter(new_ids))
    device_info = info[device_id]
    print('Device detected: {}\nDevice id: {}'.format(device_info, device_id))
    return device_id


def main():
    parser = ArgumentParser(description='A tool to charge android phones with a usb hub')
    parser.add_argument('--setup-only', action='store_true')
    args = parser.parse_args()
    enable_device_perm(not args.setup_only)


if __name__ == '__main__':
    main()
