#!/usr/bin/env python

from distutils.core import setup
from libfacebooknotify import APP_NAME, APP_DESCRIPTION, APP_VERSION, APP_AUTHORS, APP_HOMEPAGE, APP_LICENSE

setup(
    name=APP_NAME.replace(" ","-").lower(),
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    author="John Stowers",
    author_email="john.stowers@gmail.com",
    url=APP_HOMEPAGE,
    license=APP_LICENSE,
    scripts=["facebook-notify.py"],
    packages=["libfacebooknotify"],
    data_files=[
        ('share/applications', ['facebook.desktop']),
        ('usr/share/icons/hicolor/16x16/apps', ['icons/hicolor/16x16/apps/facebook.png']),
        ('usr/share/icons/hicolor/22x22/apps', ['icons/hicolor/22x22/apps/facebook.png']),
        ('usr/share/icons/hicolor/48x48/apps', ['icons/hicolor/48x48/apps/facebook.png'])],
)



