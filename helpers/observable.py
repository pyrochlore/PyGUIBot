#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division, unicode_literals

__doc__ = """This module provides 'Observer-Observable' Pattern

Todo:
	* Rewrite the implementation of breakpoints to weak dictionary
"""

from colorama import (
	Fore as FG,
	Back as BG,
	Style as ST,
)
import os
import sys
import threading
import traceback
import weakref

if __name__ == '__main__':
	reload(sys); sys.setdefaultencoding('utf-8')
	os.chdir((os.path.dirname(__file__) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))


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
		_make_breakpoint(handler)
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
							function(*self.args.pop(str(args_id)), **self.kwargs.pop(str(kwargs_id)))

						self.trigger.connect(invoke)
			else:
				raise Exception('Argument "invoke_in_main_thread" was enabled, but from GUI-Toolkits only PyQt4/PyQt5 is supported.')
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
			print >>sys.stderr, FG.RED, '__call__:', self._observable._function, 'from', self._observable._function.__class__.__module__, self._observable._function.__class__.__name__, 'called with', args, kwargs, FG.RESET; sys.stdout.flush()  # FIXME: must be removed
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
				print >>sys.stderr, "Observer was bound here:\n", "".join(traceback.format_list(handler.breakpoint[:-1]))
				print >>sys.stderr, "Handler,", handler, "\n"
				raise

		return result


def _make_breakpoint(item):
	"""Stores current breakpoint, helps to detect, for example, where was broken callback set"""
	try:
		raise Exception()
	except Exception:
		item.__dict__['breakpoint'] = traceback.extract_stack()[:-1]

	return item


# __doc__ += ''.join(sorted(['\n{0.__name__}\n\t{0.__doc__}'.format(x) for x in locals().values() if getattr(x, '__module__', None) == __name__]))


def _run_Observable():
	class Source(object):
		@Observable
		@classmethod
		def class_changed(cls, *args, **kwargs):
			print >>sys.stderr, "Source.class_changed is called with:", 'cls=' + str(cls), 'args=' + str(args), 'kwargs=' + str(kwargs); sys.stdout.flush()  # FIXME: must be removed
			return args

		@Observable
		def instance_changed(self, *args, **kwargs):
			print >>sys.stderr, "source.instance_changed is called with:", 'self=' + str(self), 'args=' + str(args), 'kwargs=' + str(kwargs); sys.stdout.flush()  # FIXME: must be removed
			return args

	class Listener(object):
		@classmethod
		def class_handler(cls, *args, **kwargs):
			print >>sys.stderr, "Listener.class_handler is called with:", 'cls=' + str(cls), 'args=' + str(args), 'kwargs=' + str(kwargs); sys.stdout.flush()  # FIXME: must be removed

		def instance_handler(self, *args, **kwargs):
			print >>sys.stderr, "Listener.instance_handler is called with:", 'self=' + str(self), 'args=' + str(args), 'kwargs=' + str(kwargs); sys.stdout.flush()  # FIXME: must be removed

	def class_handler(*args, **kwargs):
		print >>sys.stderr, "class_handler is called with:", 'args=' + str(args), 'kwargs=' + str(kwargs); sys.stdout.flush()  # FIXME: must be removed

	def instance_handler(*args, **kwargs):
		print >>sys.stderr, "instance_handler is called with:", 'args=' + str(args), 'kwargs=' + str(kwargs); sys.stdout.flush()  # FIXME: must be removed

	print >>sys.stderr, "\nTest bind/unbind..."; sys.stdout.flush()  # FIXME... must be removed
	Source.class_changed.bind(Listener.class_handler)
	Source.class_changed.unbind(Listener.class_handler)

	print >>sys.stderr, "\nTest with classmethod..."; sys.stdout.flush()  # FIXME... must be removed
	Source.class_changed.bind(Listener.class_handler)
	Source.class_changed.bind(class_handler)
	result = Source.class_changed('class is changed')
	print >>sys.stderr, "result:", result; sys.stdout.flush()  # FIXME: must be removed

	print >>sys.stderr, "\nTest with instancemethod..."; sys.stdout.flush()  # FIXME... must be removed
	source = Source()
	listener = Listener()
	source.instance_changed.bind(listener.instance_handler)
	source.instance_changed.bind(instance_handler)
	result = source.instance_changed('instance is changed')
	print >>sys.stderr, "result:", result; sys.stdout.flush()  # FIXME: must be removed


def _run_Signal():
	# def function(*args, **kwargs):
	#     print >>sys.stderr, "args, kwargs,", args, kwargs; sys.stderr.flush()  # FIXME: must be removed
	# signal = Signal(function)
	# print >>sys.stderr, "signal,", signal; sys.stderr.flush()  # FIXME: must be removed
	# print >>sys.stderr, "signal.connect,", signal.connect; sys.stderr.flush()  # FIXME: must be removed
	# print >>sys.stderr, "signal.emit,", signal.emit; sys.stderr.flush()  # FIXME: must be removed
	from PyQt5 import QtCore, QtGui, uic
	print >>sys.stderr, "'PyQt5' in sys.modules,", 'PyQt5' in sys.modules; sys.stderr.flush()  # FIXME: must be removed


def main():
	# _run_Observable()
	_run_Signal()

if __name__ == '__main__':
	main()
