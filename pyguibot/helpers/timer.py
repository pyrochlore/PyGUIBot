#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann



__doc__ = """
This module provides tools for time measurement

Environment variables:
	LOGGING or LOGGING_<MODULE> -- Logging level ( NOTSET | DEBUG | INFO | WARNING | ERROR | CRITICAL )
"""

import datetime
import logging
import os
import sys
import time

if __name__ == '__main__':
	# Sets utf-8 (instead of latin1) as default encoding for every IO
	# import importlib; importlib.reload(sys); sys.setdefaultencoding('utf-8')
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


class Timer(object):
	"""
	Example:

	>>> with Timer('making something'):
	...		pass

	"""
	def __init__(self, fmt='', show=True):
		self._fmt = fmt
		self._show = show
		self._stop_time = None

	def __enter__(self):
		self._module = sys._getframe(1).f_globals['__name__']
		self._start_time = time.time()
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self._stop_time = time.time()
		if self._show and logging.getLogger(self._module).level in (logging.DEBUG, logging.INFO):
			print(datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3], '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe().f_back), str(self) + ' - took ' + self._fmt, file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed

	def __str__(self):
		return b'{:.06f}s'.format(float(self))

	def __float__(self):
		return (self._stop_time or time.time()) - self._start_time


def run_timer():
	with Timer() as timer:
		logging.getLogger(__name__).debug('abc')


def main():
	import argparse
	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument('-r', '--run-function', default='timer', choices=[k[len('run_'):] for k in globals() if k.startswith('run_')], help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	globals()['run_' + kwargs['run_function']]()

if __name__ == '__main__':
	main()
