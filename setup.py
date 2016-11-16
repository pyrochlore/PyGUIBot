#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann (gehrmann.mail@gmail.com)

"""

*** Build ***

For Linux:
		python setup.py build

For Mac:
		python setup.py bdist_dmg
	or
		python setup.py bdist_mac

For Windows:
		python setup.py bdist_msi
	or
		python setup.py bdist_wininst

"""

import os
import sys
from cx_Freeze import setup, Executable

if not sys.argv[1:]:
	print >>sys.stderr, "{} [ build | bdist_dmg | bdist_mac | bdist_msi | bdist_wininst ]".format(sys.argv[0])
	sys.exit()

setup(
	name='PyGUIBot',
	version='0.1',
	description='Tool to make GUI-tests',
	author='gehrmann',
	author_email='gehrmann.mail@gmail.com',
	options=dict(
		build_exe=dict(
			packages=['controllers'],
			excludes=[],
			includes=["atexit"],
		)
	),
	executables=[
		Executable('main.py', base=('Win32GUI' if sys.platform == 'win32' else None)),
	],
)
