#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division
import logging
import os
import signal
import subprocess
import sys
import threading
import time

import cv2

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')
	# Run in application's working directory
	sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + '/..')
	# os.chdir(sys.path[0])
	# Working interruption by Ctrl-C (immediately, try..finally wont work)
	# signal.signal(signal.SIGINT, signal.SIG_DFL)
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configure logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(logging.DEBUG)

from controllers.abstract import AbstractController
from models.logger import Logger

__doc__ = """"""


class CaptureController(AbstractController):
	"""
	Test example for doctest
	>>> x = 5
	>>> x
	6
	"""

	def __init__(self, path, verbose):
		self._dst_path = dst_path = path

		self._capture_keys = False
		self._key_sequence = []  # Storage for pressed/released keys for some event types
		self._latest_key_triggered_timestamp = time.time()

		self._log_event_thread = None

		if not os.path.exists(dst_path):
			os.mkdir(dst_path)

		# Screen._print_backends()

	"""Model's event handlers"""

	def __on_key_triggered(self, code, key, press):
		"""Callback for key press/release"""
		logging.getLogger(__name__).debug('Key %s%s', '+' if press else '-', key)

		if key == 'Pause' or key == 'Break':
			if press:
				if key == 'Break':
					pass

				# Only one running thread is allowed. Skips if it is already running.
				if self._log_event_thread is not None and self._log_event_thread.isAlive():
					pass
				else:
					self._log_event_thread = thread = threading.Thread(target=self._create, kwargs=dict(dst_path=self._dst_path, dst=self._dst))
					thread.setDaemon(True)
					thread.start()

		else:
			if self._capture_keys:
				self._key_sequence.append(('+' if press else '-') + key)
				self._latest_key_triggered_timestamp = time.time()

	"""Helpers"""

	def loop(self):
		with open(os.path.join(self._dst_path if self._dst_path is not None else '.', 'events.log'), 'a') as self._dst:
			logger = Logger(tapped=self.__on_key_triggered)
			logger.loop()


def run_init():
	"""Runs command-line capture tool."""
	import argparse
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('-p', '--path', required=bool(sys.stdin.isatty()), help='Directory path where to load tests')
	parser.add_argument('-v', '--verbose', action='count', help='Raises logging level')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	# Raises verbosity level for script (through arguments -v and -vv)
	logging.getLogger(__name__).setLevel((logging.WARNING, logging.INFO, logging.DEBUG)[min(kwargs['verbose'] or 0, 2)])

	sys.exit(CaptureController(**kwargs).loop())


def main():
	import argparse
	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument('-r', '--run-function', default='init', choices=[k[len('run_'):] for k in globals() if k.startswith('run_')], help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	globals()['run_' + kwargs['run_function']]()

if __name__ == '__main__':
	main()
