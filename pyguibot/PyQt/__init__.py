# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann


import logging
import os
import signal
import sys

__doc__ = """Proxy for transparent selection between PyQt4 and PyQt5

Environment variables:
	LOGGING or LOGGING_<MODULE> -- Logging level ( NOTSET | DEBUG | INFO | WARNING | ERROR | CRITICAL )
"""

if __name__ == '__main__':
	# Runs in application's working directory
	os.chdir((os.path.dirname(os.path.realpath(__file__)) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))
	# Working interruption by Ctrl-C
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configures logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(getattr(logging, os.environ.get('LOGGING_' + __name__.replace('.', '_').upper(), os.environ.get('LOGGING', 'WARNING'))))

try:
	from PyQt5 import QtCore, QtGui, QtWidgets, uic
	try:
		from PyQt5 import QtSvg
	except ImportError:
		pass
	logging.getLogger(__name__).debug('Using PyQt5: %s', QtCore.QT_VERSION_STR)
	# Force PyQt5 be alike PyQt4
	QtCore.QString = lambda x: (x)
except ImportError:
	print('', file=sys.stderr)
	print('', file=sys.stderr)
	print('  Library possibly is not found. Try to install it using:', file=sys.stderr)
	# print('    # pip install PyQt5', file=sys.stderr)
	print('    # apt install python3-pyqt5', file=sys.stderr)
	print('', file=sys.stderr)
	print('', file=sys.stderr)
	raise
# except ImportError as e1:
#     logging.getLogger(__name__).warning('PyQt5 not found. Trying to find PyQt4...')
#     try:
#         from PyQt4 import QtCore, QtGui, uic
#         try:
#             from PyQt5 import QtSvg
#         except ImportError:
#             pass
#         logging.getLogger(__name__).debug('Using PyQt4: %s', QtCore.QT_VERSION_STR)
#         # Force PyQt4 be alike PyQt5
#         QtWidgets = QtGui
#         QtCore.qInstallMessageHandler = QtCore.qInstallMsgHandler
#     except ImportError as e2:
#         raise ImportError('%s, %s' % (e1, e2))
