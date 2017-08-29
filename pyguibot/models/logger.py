#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division
import logging
import os
import sys
import threading
import time

# import pymouse
import pykeyboard

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')
	# Run in application's working directory
	sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + '/..')
	os.chdir(sys.path[0])
	# Working interruption by Ctrl-C
	# import signal; signal.signal(signal.SIGINT, signal.SIG_DFL)
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configure logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
	logging.getLogger(__name__).setLevel(logging.DEBUG)

import models.devices

__doc__ = """"""


class Logger(object):
	""""""

	def __init__(self, tapped=None, moved=None, clicked=None, scrolled=None):
		self._keyboard_events = keyboard_events = pykeyboard.PyKeyboardEvent()
		keyboard_events.tap = tapped

		keyboard_events.escape = self.__on_tapping

		# self._mouse_events = mouse_events = pymouse.PyMouseEvent()
		# mouse_events.capture = False
		# # mouse_events.daemon = False
		# mouse_events.move = moved
		# mouse_events.click = clicked
		# mouse_events.scroll = scrolled

		self._mouse = models.devices.Mouse()

	def __on_tapping(self, event):
		"""Checks some conditions to finish listening thread."""
		# FIXME: exiting does not work here, hangs on and consumes CPU
		# if event.detail == self.lookup_character_keycode('Escape'):
		#     return True
		return False

	def loop(self):
		# self._keyboard_events.start()
		def run_loop():
			self._keyboard_events.start()
			# self._mouse_events.start()
			self._keyboard_events.join()
		thread = threading.Thread(target=run_loop)
		thread.start()

		try:
			while (True):
				sys.stdout.write('.'); sys.stdout.flush()  # FIXME: must be removed/commented
				try:
					time.sleep(.1)
				except KeyboardInterrupt:
					break
		finally:
			self._keyboard_events.stop()

	# """Helpers"""

	# def screen_size(self):
	#     return self._mouse.screen_size()


def run_logger():

	def _dump(*args, **kwargs):
		logging.getLogger(__name__).debug('%s, %s', args, kwargs)

	Logger(
		tapped=_dump,
		moved=_dump,
		clicked=_dump,
		scrolled=_dump,
	).loop()


def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--run-function', help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_args())  # Breaks here if something goes wrong

	globals()['run_' + (kwargs['run_function'] or 'logger')]()

if __name__ == '__main__':
	main()
