# Phone Charger

*A tool to charge android phones with a usb hub*

Charging smartphone batteries to 100%, while not dangerous, can
slightly shorten the life of the battery. This tool uses a USB
hub or raspberry pi to continuously charge Android devices to
only 80%.

Required tools:

 - Android device with USB debugging enabled
 - Computer + [compatible USB hub](https://github.com/mvp/uhubctl#compatible-usb-hubs) or a raspberry pi

## Installation

```bash
sudo pip3 install phone-charger
phone-charger-setup 
```

This sets up a service (called `phone-charger`) that enables
or disables the usb hub based on the batter level of all
authorized and connected adb devices.

**Note:** All devices that you want to charge must be set
up with `phone-charger-setup` individually. This enables
udev permissions and authorizes via ADB


## How it works

It works by doing the following:

 - Reading the battery level with `adb shell dumpsys battery`
 - Enabling or disabling the USB hub with [uhubctl](https://github.com/mvp/uhubctl)


## Disclaimer

This has only been tested on a Raspberry pi. There might be
some issues that need to be sorted out when attempting to
use this on a usb hub rather than a pi.
