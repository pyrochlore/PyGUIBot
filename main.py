#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division

__doc__ = """"""

import logging
import os
import signal
import sys

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')
	# Working interruption by Ctrl-C
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configure logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(logging.DEBUG)

from controllers.qt_gui import QtGuiController as MainController
# from controllers.wx_gui import WxGuiController as MainController


def main():
	import argparse
	parser = argparse.ArgumentParser(description='Restores mouse and keyboard events from storage.')
	parser.add_argument('path', nargs='?', default='data', help='Directory path where to load the data (default "data")')
	kwargs = vars(parser.parse_args())  # Breaks here if something goes wrong

	MainController(**kwargs).loop()

if __name__ == '__main__':
	main()
