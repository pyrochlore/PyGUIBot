#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann



__doc__ = """
This module provides delayed asynchronous calls

Environment variables:
	LOGGING_<MODULE> -- Logging level ( NOTSET | DEBUG | INFO | WARNING | ERROR | CRITICAL )

Todo:
	* Smart breakpoints
"""

import functools
import logging
import os
import sys
import threading
import traceback
import weakref

if __name__ == '__main__':
	# Sets utf-8 (instead of latin1) as default encoding for every IO
	# import importlib; importlib.reload(sys); sys.setdefaultencoding('utf-8')
	# Runs in application's working directory
	os.chdir((os.path.dirname(os.path.realpath(__file__)) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))
	# Working interruption by Ctrl-C
	import signal; signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configures logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(getattr(logging, os.environ.get('LOGGING_' + __name__.replace('.', '_').upper(), 'WARNING')))

if __name__ == '__main__':
	# Uses PyQt as default GUI-toolkit for runs and tests
	import PyQt

# Checks if some known GUI-toolkit was loaded
if 'PyQt4' in sys.modules:
	from PyQt4 import QtCore, QtGui as QtWidgets
elif 'PyQt5' in sys.modules:
	from PyQt5 import QtCore, QtWidgets
elif 'wx' in sys.modules:
	import wx
else:
	logging.getLogger(__name__).warning('From GUI-Toolkits only PyQt4/PyQt5 and wxWidgets are supported.')

from helpers.timer import Timer


class Caller(object):
	"""This class provides delayed asynchronous calls"""

	_once_timers = dict()
	_once_threads = dict()

	@classmethod
	def call_once_after(
			cls,
			delay,  # Time interval (in sec)
			function,
			*args, **kwargs):
		"""Calls the function once asynchronous after delay, returns immediately None.

		:arguments:
			delay : float, sec
				Time interval
		:returns: None

		Example:

			>>> from PyQt5 import QtWidgets
			>>> app = QtWidgets.QApplication(sys.argv)
			>>> def callback(value, power):
			...		app.exit(value ** power)
			>>> Caller.call_once_after(.01, callback, 2, power=3)
			>>> app.exec_()
			8

		"""

		cls._save_breakpoint(function)

		# return function(*args, **kwargs)
		previous_timer = cls._once_timers.pop(function, None)
		# previous_threads = cls._once_threads.pop(function, [])
		if previous_timer is not None:
			logging.debug("Removing existing timer for: {}".format(function))
			if 'PyQt4' in sys.modules or 'PyQt5' in sys.modules:
				if isinstance(previous_timer, QtCore.QTimer):
					pass  # Qt can not stop timer from another thread. Just remove from timers list and forget.
					# # Stops QtCore.QTimer
					# previous_timer.stop()
					# previous_timer.deleteLater()
				else:
					print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'Can not stop somethin else as QTimer', file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented
			elif 'wx' in sys.modules:
				previous_timer.Stop()

		logging.debug("Setting timer for: {}".format(function))
		if 'PyQt4' in sys.modules or 'PyQt5' in sys.modules:

			def run_timer():
				def run_function(cls, timer, function):
					# If the timer was not thrown
					if cls._once_timers.get(function, None) == timer:
						previous_timer = cls._once_timers.pop(function, None)
						if logging.getLogger(__name__).level == logging.DEBUG:
							with Timer('caller for ' + (function.__func__.__name__ if hasattr(function, 'im_function') else function.__name__)):
								function(*args, **kwargs)
						else:
							try:
								# print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'FUNCTION', function; sys.stderr.flush()  # FIXME: must be removed/commented
								function(*args, **kwargs)
							except Exception as e:
								print('Traceback (most recent call last):\n', "".join(traceback.format_list(function.breakpoint[:-1])), 'Callback was set here.\n', file=sys.stderr)
								raise
				# Invokes run_function in main thread after delay. FIXME: works only in PyQt4
				timer = QtCore.QTimer()
				timer.timeout.connect(functools.partial(run_function, cls, timer, function), QtCore.Qt.DirectConnection)  # QtCore.Qt.DirectConnection adds timer into main loop
				timer.setSingleShot(True)
				timer.start(delay * 1000)  # In ms
				cls._once_timers[function] = timer
				timer.moveToThread(QtWidgets.qApp.thread())
				# timer.moveToThread(QtCore.QThread.currentThread())

			if threading.current_thread().name != 'MainThread':
				# Changes threading.Thread to QtCore.QThread, stores new QThread in _once_threads
				run_timer_thread = QtCore.QThread()
				cls._once_threads.setdefault(function, []).append(run_timer_thread)
				run_timer_thread.run = run_timer
				run_timer_thread.start()
			else:
				run_timer()

		elif 'wx' in sys.modules:
			timer = wx.CallAfter(  # Invokes wx.CallLater in GUI-thread
				wx.CallLater,  # Invokes function after delay
				delay * 1000,  # In ms
				function,
				*args, **kwargs
			)
			cls._once_timers[function] = timer
		else:
			raise Exception('No known GUI-Toolkit was loaded. Only PyQt4/PyQt5 and wxWidgets are supported.')

	@classmethod
	def call_never(cls, key):
		"""Forgets to call the function previously set with call_once_after().

		Example:

			>>> from PyQt5 import QtWidgets
			>>> app = QtWidgets.QApplication(sys.argv)
			>>> def wrong_callback(value, power):
			...		app.exit(value + power)
			>>> def right_callback(value, power):
			...		app.exit(value ** power)
			>>> Caller.call_once_after(.01, wrong_callback, 2, power=3)
			>>> Caller.call_once_after(.02, right_callback, 2, power=3)
			>>> Caller.call_never(wrong_callback)
			>>> app.exec_()
			8

		"""
		if key in cls._once_timers:
			previous_timer = cls._once_timers.pop(key)
			if 'PyQt4' in sys.modules or 'PyQt5' in sys.modules:
				if isinstance(previous_timer, QtCore.QTimer):
					# Stops QtCore.QTimer
					previous_timer.stop()
					previous_timer.deleteLater()
				else:
					print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'Can not stop somethin else as QTimer', file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented
			elif 'wx' in sys.modules:
				previous_timer.Stop()
			else:
				raise Exception('No known GUI-Toolkit was loaded. Only PyQt4/PyQt5 and wxWidgets are supported.')

	_breakpoints = weakref.WeakKeyDictionary()

	@classmethod
	def _save_breakpoint(cls, item):
		# Save current breakpoint for future exceptions
		try:
			raise Exception()
		except Exception:
			item.__dict__['breakpoint'] = traceback.extract_stack()[:-1]

		return item


# __doc__ += ''.join(sorted(['\n{0.__name__}\n\t{0.__doc__}'.format(x) for x in locals().values() if getattr(x, '__module__', None) == __name__]))


def run_caller():
	"""Runs a second thread and tries to call a callback later"""

	run_in_threading_thread = False
	run_in_threading_thread = True

	run_in_qthread = False
	# run_in_qthread = True

	from PyQt import QtWidgets
	app = QtWidgets.QApplication(sys.argv)

	def callback(*args, **kwargs):
		print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'CALLBACK():', args, kwargs, file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented

	print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'Main QThread:', QtCore.QThread.currentThread(), 'Current QThread:', QtWidgets.qApp.thread(), file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented

	# def on_run_timer():
	def run():
		Caller.call_once_after(.5, callback, 2, power=3)
		Caller.call_once_after(.5, callback, 4, power=5)
		Caller.call_once_after(.5, callback, 6, power=7)
		# Caller.call_never(callback)
	if run_in_threading_thread:  # Run in threading.Thread
		print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'running in threading.Thread', file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented
		run_thread = threading.Thread(target=run)
		run_thread.start()
	elif run_in_qthread:  # Run in Qthread
		print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'running in QThread', file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented
		run_thread = QtCore.QThread()
		run_thread.run = run
		run_thread.start()
	else:
		print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'running in main thread', file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented
		run()
	# run_timer = QtCore.QTimer()
	# run_timer.timeout.connect(on_run_timer)
	# run_timer.setSingleShot(True)
	# run_timer.start(0 * 1000)  # In ms

	def on_quit_timer():
		QtWidgets.QApplication.quit()
	quit_timer = QtCore.QTimer()
	quit_timer.timeout.connect(on_quit_timer)
	quit_timer.setSingleShot(True)
	quit_timer.start(2 * 1000)  # In ms

	print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'EVENTLOOP()', file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented
	app.exec_()
	print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'Caller._once_timers=', Caller._once_timers, file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented


def run_doctest():
	logging.basicConfig(level=logging.DEBUG)
	import doctest
	doctest.testmod()


def main():
	import argparse
	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument('-r', '--run-function', default='caller', choices=[k[len('run_'):] for k in globals() if k.startswith('run_')], help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	globals()['run_' + kwargs['run_function']]()

if __name__ == '__main__':
	main()
