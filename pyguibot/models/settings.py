#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python2" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division, unicode_literals

__doc__ = """
This module provides a model to store program's settings
"""

import logging
import os
import signal
import sys

if __name__ == '__main__':
	# Sets utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')
	# Runs in application's working directory
	os.chdir((os.path.dirname(os.path.realpath(__file__)) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))
	# Working interruption by Ctrl-C
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configures logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(getattr(logging, os.environ.get('LOGGING_' + __name__.replace('.', '_').upper(), 'WARNING')))

from models.abstract import Memento, ObservableAttrDict, ObservableList, ObservableSet


class Settings(ObservableAttrDict):
	"""Stores program's settings"""

	def __init__(self, path=None):
		super(Settings, self).__init__()

		from styles import styles

		# Protects from saving default values in settings.txt
		self.__dict__['defaults'] = ObservableAttrDict(
		)

		if path is not None:
			self._memento = memento = Memento(path)
			self.update(memento.restore(parse_values=True))
			self.changed.bind(memento.save)

		self.defaults.changed.bind(self._on_model_updated)

	def _on_model_updated(self, model=None, previous=(None, ), current=(None, )):
		# logging.getLogger(__name__).warning('%s %s %s %s', self.__class__.__name__, model.__class__.__name__, previous and str(previous)[:999], current and str(current)[:999])

		if model is self.defaults:
			if current[0] is not None:
				self.update(current[0])

	def __repr__(self):
		return object.__repr__(self)

	def __getattr__(self, key):
		try:
			value = super(Settings, self).__getattr__(key)
			# print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), "from settings:", key, '=', value; sys.stderr.flush()  # FIXME: must be removed/commented
		except KeyError:
			value = getattr(self.defaults, key)
			# print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), "from defaults:", key, '=', value; sys.stderr.flush()  # FIXME: must be removed/commented
		return value


def run_settings():
	from PyQt import QtCore, QtGui, QtWidgets, uic
	app = QtWidgets.QApplication(sys.argv)
	from styles import styles  # Load once the styles for QApplication

	# settings = Settings()
	settings = Settings(path='settings.txt')

	storages = settings.shared_vocabularies_storages
	print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'storages=', storages; sys.stderr.flush()  # FIXME: must be removed/commented
	print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'storages.__class__=', storages.__class__; sys.stderr.flush()  # FIXME: must be removed/commented

	storages.add(ObservableAttrDict(name='New storage', shared_id='test_id'))
	print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'storages=', storages; sys.stderr.flush()  # FIXME: must be removed/commented


def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--run-function', default='settings', choices=[k[len('run_'):] for k in globals() if k.startswith('run_')], help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	globals()['run_' + kwargs['run_function']]()

if __name__ == '__main__':
	main()
