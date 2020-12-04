#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann



__doc__ = """This module provides 'Observer-Observable' Pattern

Environment variables:
	LOGGING_<MODULE> -- Logging level ( NOTSET | DEBUG | INFO | WARNING | ERROR | CRITICAL )

Todo:
	* Rewrite the implementation of breakpoints to weak dictionary
"""

from colorama import (
	Fore as FG,
	Back as BG,
	Style as ST,
)
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

from helpers.timer import Timer


class Observable(object):
	"""Decorator, creates descriptor (unbound Observable)

	Example:

		>>> from observable import Observable  # <=== (1)
		>>> class Source(object):
		... 	@Observable  # <=== (2)
		... 	def changed(self, message):
		... 		return message
		>>> def handler(message):
		... 	print 'Handler:', message
		>>> source = Source()
		>>> source.changed # doctest: +ELLIPSIS
		<observable._Observable object at 0x...>
		>>> source.changed.bind(handler)  # <=== (3)
		>>> source.changed("Test")
		Handler: Test
		u'Test'

	"""

	def __init__(self, function):
		self.__doc__ = function.__func__.__doc__ if hasattr(function, '__func__') else function.__doc__

		self._function = function
		self._descriptors = weakref.WeakKeyDictionary()

	def __repr__(self):
		return '<{self.__class__.__module__}.{self.__class__.__name__} from {self._function} at 0x{address:x}>'.format(self=self, address=id(self))

	def __get__(self, im_self, im_class):
		im_item = im_self if im_self is not None else im_class
		if im_item not in self._descriptors:
			self._descriptors[im_item] = _Observable(self, im_self, im_class)
		return self._descriptors[im_item]


class _Observable(object):
	"""Bound Observable, sends events to observers if decorated function/method is called"""

	def __init__(self, observable, im_self, im_class):
		self._observable = observable
		self._im_class_ref = None if im_class is None else weakref.ref(im_class)
		self._im_self_ref = None if im_self is None else weakref.ref(im_self)
		self._handlers = set()
		self._handlers_to_signals = weakref.WeakKeyDictionary()

	def bind(self, handler, invoke_in_main_thread=False):
		self._save_breakpoint(handler)

		self._handlers.add(handler)

		if invoke_in_main_thread:
			if 'PyQt4' in sys.modules or 'PyQt5' in sys.modules:
				if 'PyQt4' in sys.modules:
					from PyQt4 import QtCore
				elif 'PyQt5' in sys.modules:
					from PyQt5 import QtCore

				class _Signal(QtCore.QObject):
					trigger = QtCore.pyqtSignal(str, str)
					args = dict()
					kwargs = dict()

					def __init__(self, function):
						super(_Signal, self).__init__()

						def invoke(args_id, kwargs_id):
							if logging.getLogger(__name__).level == logging.DEBUG:
								with Timer('observable for ' + (function.__func__.__name__ if hasattr(function, 'im_function') else function.__name__)):
									function(*self.args.pop(str(args_id)), **self.kwargs.pop(str(kwargs_id)))
							else:
								function(*self.args.pop(str(args_id)), **self.kwargs.pop(str(kwargs_id)))

						self.trigger.connect(invoke)
			else:
				raise Exception('Argument "invoke_in_main_thread" was enabled, but from GUI-Toolkits only PyQt4/PyQt5 are supported.')
			self._handlers_to_signals[handler] = _Signal(handler)

	def unbind(self, handler):
		self._handlers.discard(handler)

	def __call__(self, *args, **kwargs):
		im_class = self._im_class_ref and self._im_class_ref()
		im_self = self._im_self_ref and self._im_self_ref()

		# Call function
		try:
			result = self._observable._function.__get__(im_class if isinstance(self._observable._function, classmethod) else im_self, im_class)(*args, **kwargs)
		except Exception:
			print(FG.RED, '__call__:', self._observable._function, 'from', self._observable._function.__class__.__module__, self._observable._function.__class__.__name__, 'called with', args, kwargs, FG.RESET, file=sys.stderr); sys.stdout.flush()  # FIXME: must be removed
			raise

		# Call handlers
		# print >>sys.stderr, "self._handlers,", im_class, im_self, self._handlers; sys.stderr.flush()  # FIXME: must be removed
		for handler in list(self._handlers):
			try:
				# Attention! Here is supposed that nobody renamed the name of main thread!
				if handler in self._handlers_to_signals and threading.current_thread().name != 'MainThread':
					signal = self._handlers_to_signals[handler]

					# QT can pass only primitive types so we pass two strings
					args_id, kwargs_id = str(id(args)), str(id(kwargs))
					signal.args[args_id], signal.kwargs[kwargs_id] = args, kwargs
					signal.trigger.emit(args_id, kwargs_id)
				else:
					handler(*args, **kwargs)
			except Exception as e:
				# Print breakpoint where observer was set
				print("Observer was bound here:\n", "".join(traceback.format_list(handler.breakpoint[:-1])), file=sys.stderr)
				print("Handler,", handler, "\n", file=sys.stderr)
				raise

		return result

	@classmethod
	def _save_breakpoint(cls, item):
		"""Stores current breakpoint, helps to detect, for example, where was broken callback set"""
		try:
			raise Exception()
		except Exception:
			item.__dict__['breakpoint'] = traceback.extract_stack()[:-1]

		return item


# __doc__ += ''.join(sorted(['\n{0.__name__}\n\t{0.__doc__}'.format(x) for x in locals().values() if getattr(x, '__module__', None) == __name__]))


def run_observable():
	class Source(object):
		@Observable
		@classmethod
		def class_changed(cls, *args, **kwargs):
			print("Source.class_changed is called with:", 'cls=' + str(cls), 'args=' + str(args), 'kwargs=' + str(kwargs), file=sys.stderr); sys.stdout.flush()  # FIXME: must be removed
			return args

		@Observable
		def instance_changed(self, *args, **kwargs):
			print("source.instance_changed is called with:", 'self=' + str(self), 'args=' + str(args), 'kwargs=' + str(kwargs), file=sys.stderr); sys.stdout.flush()  # FIXME: must be removed
			return args

	class Listener(object):
		@classmethod
		def class_handler(cls, *args, **kwargs):
			print("Listener.class_handler is called with:", 'cls=' + str(cls), 'args=' + str(args), 'kwargs=' + str(kwargs), file=sys.stderr); sys.stdout.flush()  # FIXME: must be removed

		def instance_handler(self, *args, **kwargs):
			print("Listener.instance_handler is called with:", 'self=' + str(self), 'args=' + str(args), 'kwargs=' + str(kwargs), file=sys.stderr); sys.stdout.flush()  # FIXME: must be removed

	def class_handler(*args, **kwargs):
		print("class_handler is called with:", 'args=' + str(args), 'kwargs=' + str(kwargs), file=sys.stderr); sys.stdout.flush()  # FIXME: must be removed

	def instance_handler(*args, **kwargs):
		print("instance_handler is called with:", 'args=' + str(args), 'kwargs=' + str(kwargs), file=sys.stderr); sys.stdout.flush()  # FIXME: must be removed

	print("\nTest bind/unbind...", file=sys.stderr); sys.stdout.flush()  # FIXME... must be removed
	Source.class_changed.bind(Listener.class_handler)
	Source.class_changed.unbind(Listener.class_handler)

	print("\nTest with classmethod...", file=sys.stderr); sys.stdout.flush()  # FIXME... must be removed
	Source.class_changed.bind(Listener.class_handler)
	Source.class_changed.bind(class_handler)
	result = Source.class_changed('class is changed')
	print("result:", result, file=sys.stderr); sys.stdout.flush()  # FIXME: must be removed

	print("\nTest with instancemethod...", file=sys.stderr); sys.stdout.flush()  # FIXME... must be removed
	source = Source()
	listener = Listener()
	source.instance_changed.bind(listener.instance_handler)
	source.instance_changed.bind(instance_handler)
	result = source.instance_changed('instance is changed')
	print("result:", result, file=sys.stderr); sys.stdout.flush()  # FIXME: must be removed


def run_signal():
	# def function(*args, **kwargs):
	#     print >>sys.stderr, "args, kwargs,", args, kwargs; sys.stderr.flush()  # FIXME: must be removed
	# signal = Signal(function)
	# print >>sys.stderr, "signal,", signal; sys.stderr.flush()  # FIXME: must be removed
	# print >>sys.stderr, "signal.connect,", signal.connect; sys.stderr.flush()  # FIXME: must be removed
	# print >>sys.stderr, "signal.emit,", signal.emit; sys.stderr.flush()  # FIXME: must be removed
	from PyQt5 import QtCore, QtGui, uic
	print("'PyQt5' in sys.modules,", 'PyQt5' in sys.modules, file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed


def main():
	import argparse
	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument('-r', '--run-function', default='observable', choices=[k[len('run_'):] for k in globals() if k.startswith('run_')], help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	globals()['run_' + kwargs['run_function']]()

if __name__ == '__main__':
	main()
