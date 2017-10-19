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

# import pyautogui.screenshotUtil
import pykeyboard
import pymouse
# import pyscreenshot

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')
	# Run in application's working directory
	os.chdir((os.path.dirname(os.path.realpath(__file__)) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))
	# Working interruption by Ctrl-C
	import signal; signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configure logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
	logging.getLogger(__name__).setLevel(logging.DEBUG)

__doc__ = """"""


# # Detects if wxWidgets are installed
# if 'wx' not in pyscreenshot.backends():
#     logging.getLogger(__name__).warning('WX not found in pyscreenshot.backends(). Install it please, because it is the fastest one!')


class Screen(object):
	@classmethod
	def get_screenshot(cls):
		"""Makes screenshot, returns PIL-image"""
		# screenshot = pyscreenshot.grab()  # ~1.1s
		# screenshot = PIL.ImageGrab.grab()
		# screenshot = pyautogui.screenshotUtil.screenshot()
		# screenshot = pyscreenshot.grab(
		#     backend='wx',  # Fastest backend, can be [ 'wx' | 'pygtk' | 'pyqt' | 'scrot' | 'imagemagick' | ... ]
		#     childprocess=False,  # Allows not to re-initialize wx.App
		# )

		import wx
		from PIL import Image as PIL_Image
		if not hasattr(cls, '_wx_application'):
			cls._wx_application = wx.App()
		screen = wx.ScreenDC()
		size = screen.GetSize()
		_bitmap = wx.EmptyBitmap(size[0], size[1])
		_memory = wx.MemoryDC(_bitmap)
		_memory.Blit(0, 0, size[0], size[1], screen, 0, 0)
		del _memory
		_wx_image = wx.ImageFromBitmap(_bitmap)
		screenshot = PIL_Image.new('RGB', (_wx_image.GetWidth(), _wx_image.GetHeight()))
		if hasattr(PIL_Image, 'frombytes'):
			# for Pillow
			screenshot.frombytes(_wx_image.GetData())
		else:
			# for PIL
			screenshot.fromstring(_wx_image.GetData())

		return screenshot

	# def _print_backends():
	#     """Prints out availables backends"""
	#     print pyscreenshot.backends()


class Keyboard(pykeyboard.PyKeyboard):
	""""""

	@classmethod
	def _get_instance(cls, _state=dict(instance=None)):
		if _state['instance'] is None:
			_state['instance'] = cls()
		return _state['instance']

	@classmethod
	def press(cls, key):
		self = cls._get_instance()
		super(Keyboard, self).press_key(key)

	@classmethod
	def release(cls, key):
		self = cls._get_instance()
		super(Keyboard, self).release_key(key)

	@classmethod
	def type(cls, keys, interval):
		"""Types keys"""
		self = cls._get_instance()
		super(Keyboard, self).type_string(keys, interval)


def run_keyboard():
	Keyboard.press_key('H')
	Keyboard.release_key('H')
	Keyboard.tap_key('e')  # press + release
	Keyboard.tap_key('l', n=2, interval=1)
	Keyboard.type_string('o World!')


class Mouse(pymouse.PyMouse):
	""""""

	@classmethod
	def _get_instance(cls, _state=dict(instance=None)):
		if _state['instance'] is None:
			_state['instance'] = cls()
		return _state['instance']

	def __init__(self, velocity=1000, delay=.01):
		super(Mouse, self).__init__()
		self._velocity = velocity
		self._delay = delay

	@classmethod
	def press(cls, x, y, button=1):
		self = cls._get_instance()
		super(Mouse, self).press(x, y, button)

	@classmethod
	def release(cls, x, y, button=1):
		self = cls._get_instance()
		super(Mouse, self).release(x, y, button)

	@classmethod
	def click(cls, x, y, button=1, count=1):
		self = cls._get_instance()
		super(Mouse, self).click(x, y, button=button, n=count)

	@classmethod
	def scroll(cls, x, y):
		self = cls._get_instance()
		super(Mouse, self).scroll(x, y)

	@classmethod
	def slide(cls, x, y):
		self = cls._get_instance()

		src_x, src_y = self.position()

		length_x = (x - src_x)
		length_y = (y - src_y)
		length = math.sqrt(length_x**2 + length_y**2)

		steps = length / (self._velocity * self._delay)
		if steps:
			dx = length_x / steps
			dy = length_y / steps
			for step in range(int(steps)):
				_x = src_x + dx * step
				_y = src_y + dy * step

				time.sleep(self._delay)
				super(Mouse, self).move(_x, _y)

			time.sleep(self._delay)
		super(Mouse, self).move(x, y)


def run_slide_mouse():
	"""Moves mouse cursor in a sequence of some points"""
	for x, y in (
			(500, 100),
			(600, 400),
			(700, 200),
	):
		Mouse.slide(x, y)
		time.sleep(1)


def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--run-function', help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_args())  # Breaks here if something goes wrong

	globals()['run_' + (kwargs['run_function'] or 'keyboard')]()

if __name__ == '__main__':
	main()
