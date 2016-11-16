# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division, unicode_literals
import logging
import os
import signal
import sys

if __name__ == '__main__':
	# Runs in application's working directory
	os.chdir((os.path.dirname(__file__) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))
	# Working interruption by Ctrl-C
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configures logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(logging.DEBUG)

__doc__ = """Proxy for transparent selection between PyQt4 and PyQt5"""

try:
	from PyQt5 import QtCore, QtGui, QtWidgets, uic
	logging.getLogger(__name__).debug('Using PyQt5: %s', QtCore.QT_VERSION_STR)
	# Force PyQt5 be alike PyQt4
	QtCore.QString = lambda x: (x)
except ImportError as e1:
	try:
		from PyQt4 import QtCore, QtGui, uic
		logging.getLogger(__name__).debug('Using PyQt4: %s', QtCore.QT_VERSION_STR)
		# Force PyQt4 be alike PyQt5
		QtWidgets = QtGui
		QtCore.qInstallMessageHandler = QtCore.qInstallMsgHandler
	except ImportError as e2:
		raise ImportError('%s, %s' % (e1, e2))
