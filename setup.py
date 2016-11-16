#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann (gehrmann.mail@gmail.com)

from __future__ import division

__doc__ = """
* Linux, build:              ./setup.py build
* Mac, build:                ./setup.py bdist_mac
* Mac, build DMG:            ./setup.py bdist_dmg
* Windows, build MSI:        ./setup.py bdist_msi
* Windows, build installer:  ./setup.py bdist_wininst
"""

import cx_Freeze
import logging
import os
import signal
import sys

if __name__ == '__main__':
	# Configures logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(logging.DEBUG)


def run_setup(**kwargs):
	cx_Freeze.setup(
		name='PyGUIBot',
		description='Tool to make GUI-tests',
		version='0.1',
		author='gehrmann',
		author_email='gehrmann.mail@gmail.com',
		options=dict(
			build_exe=dict(
				packages=['controllers'],
				excludes=['urllib'],  # Fixes "cx_Freeze.freezer.ConfigError: no file named sys (for module urllib.sys)"
				includes=['atexit'],
				include_files=[
					'__startup__.py',  # Run script
					'views',
					'data',  # Example data
					'images',
				],
				# zip_includes=[
				# ],
			)
		),
		executables=[
			cx_Freeze.Executable(
				script='pyguibot.py',
				# initScript='Console',
				# initScript='ConsoleSetLibPath',
				# initScript='SharedLib',
				# initScript='SharedLibSource',
				# initScript='__startup__',
				base=('Win32GUI' if sys.platform == 'win32' else None),  # Marks as GUI-application if windows
				# compress=True,
			),
		],
		# entry_points={
		#     'console_scripts': [
		#         # 'foo = other_module:some_func',
		#         'pyguibot_capture = controllers.capture',
		#         'pyguibot_restore = controllers.restore',
		#     ],
		#     'gui_scripts': [
		#         # 'foo = other_module:some_func',
		#         'pyguibot = controllers.qt_gui',
		#         'pyguibot_qt = controllers.qt_gui',
		#         'pyguibot_wx = controllers.wx_gui',
		#     ]
		# }
	)


def main():
	import argparse
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
	parser.add_argument('action', choices=[
		'build', 'bdist_dmg', 'bdist_mac', 'bdist_msi', 'bdist_wininst',
		'build_exe', 'install', 'install_exe', 'setup', 'bdist_rpm',
	], help='Action type')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	run_setup(**kwargs)

if __name__ == '__main__':
	main()
