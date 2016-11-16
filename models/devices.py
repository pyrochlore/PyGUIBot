#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division
import logging
import math
import os
import sys
import time

import pykeyboard
import pymouse

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')
	# Run in application's working directory
	os.chdir((os.path.dirname(__file__) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))
	# Working interruption by Ctrl-C
	import signal; signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configure logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
	logging.getLogger(__name__).setLevel(logging.DEBUG)

__doc__ = """"""


class Keyboard(pykeyboard.PyKeyboard):
	""""""

	def tap(self, keys):
		"""Does press and release of keys

		Sign '+' unites keys
		"""
		for key in keys.split('+'):
			keyboard.press_key(key)
		for key in reversed(keys.split('+')):
			keyboard.release_key(key)


def test_keyboard():
	Keyboard()


def run_keyboard():
	keyboard = Keyboard()
	keyboard.press_key('H')
	keyboard.release_key('H')
	keyboard.tap_key('e')  # press + release
	keyboard.tap_key('l', n=2, interval=1)
	keyboard.type_string('o World!')


class Mouse(pymouse.PyMouse):
	""""""

	def __init__(self, velocity=200, delay=.01):
		super(Mouse, self).__init__()
		self._velocity = velocity
		self._delay = delay

	def slide(self, x, y):
		src_x, src_y = self.position()

		length_x = (x - src_x)
		length_y = (y - src_y)
		length = math.sqrt(length_x**2 + length_y**2)

		steps = length / (self._velocity * self._delay)
		if steps:
			dx = length_x / steps
			dy = length_y / steps
			for step in range(int(steps)):
				x = src_x + dx * step
				y = src_y + dy * step

				time.sleep(self._delay)

				self.move(x, y)


def test_mouse():
	Mouse()


def run_slide_mouse():
	"""Moves mouse cursor in a sequence of some points"""
	mouse = Mouse()
	for x, y in (
			(500, 100),
			(600, 400),
			(700, 200),
	):
		mouse.slide(x, y)
		time.sleep(1)


def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--run-function', help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_args())  # Breaks here if something goes wrong

	globals()['run_' + (kwargs['run_function'] or 'keyboard')]()

if __name__ == '__main__':
	main()
