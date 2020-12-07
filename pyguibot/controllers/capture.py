#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann

import contextlib
import logging
import os
import signal
import subprocess
import sys
import threading
import time

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	# import importlib; importlib.reload(sys); sys.setdefaultencoding('utf-8')
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
		super(CaptureController, self).__init__(path=path)
		state_model = self._state_model

		# logging.getLogger(__name__).warning('os.getpgrp()=' + '%s', os.getpgrp())

		"""Models"""
		state_model.capture_keys = False
		state_model.key_sequence = []  # Storage for pressed/released keys for some event types
		state_model.latest_key_triggered_timestamp = time.time()

		self._log_event_thread = None

		self._logger = Logger(tapped=self.__on_key_triggered)

		# Screen._print_backends()

	"""Model's event handlers"""

	def __on_key_triggered(self, code, key, press):
		"""Callback for key press/release"""
		logging.getLogger(__name__).debug('Key %s%s', '+' if press else '-', key)
		state_model = self._state_model

		if key in ('Pause', ):
			if press:
				logging.getLogger(__name__).info('Terminated by user')
				self._logger.exit()

		elif key in ('Break', 'Insert'):
			if press:
				# Only one running thread is allowed. Skips if it is already running.
				if self._log_event_thread is not None and self._log_event_thread.is_alive():
					pass
				else:
					def create():
						with (
								contextlib.nullcontext(enter_result=sys.stdout)
								if not state_model.src_path or os.path.exists(state_model.src_path) and os.path.isdir(state_model.src_path) else
								open(state_model.src_path, 'a')
						) as dst:
							event = self._create(
								with_exceptions=True,
								# with_exceptions=False,
							)

							print(self._dump(event), end='', file=dst)
							dst.flush()
					self._log_event_thread = thread = threading.Thread(target=create)
					thread.setDaemon(True)
					thread.start()

		else:
			if state_model.capture_keys:
				state_model.key_sequence.append(('+' if press else '-') + key)
				state_model.latest_key_triggered_timestamp = time.time()

	"""Helpers"""

	def loop(self):
		self._logger.loop()


def run_init():
	"""Runs command-line capture tool."""
	import argparse
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('-p', '--path', default='', help='Directory path where to load tests')
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
