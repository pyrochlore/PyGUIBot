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
import textwrap
import time

import cv2
import pyscreenshot

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')
	# Run in application's working directory
	os.chdir((os.path.dirname(__file__) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))
	# Working interruption by Ctrl-C (immediately, try..finally wont work)
	# signal.signal(signal.SIGINT, signal.SIG_DFL)
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configure logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(logging.DEBUG)

import models.logger

__doc__ = """"""


class CaptureController(object):
	"""
	Test example for doctest
	>>> x = 5
	>>> x
	6
	"""

	def __init__(self, path):
		self._dst_path = dst_path = path

		self._capture_keys = False
		self._key_sequence = []  # Storage for pressed/released keys for some event types
		self._latest_key_tapped = time.time()

		self._log_event_thread = None

		if not os.path.exists(dst_path):
			os.mkdir(dst_path)

		# print pyscreenshot.backends()

		self._logger = models.logger.Logger(
			tapped=self.__on_tap,
		)

	"""Model's event handlers"""

	def __on_tap(self, code, key, press):
		"""

		Example:
		>>> CaptureController.__on_tap(asdfasdf)
		123

		"""
		logging.getLogger(__name__).debug('Key %s%s', '+' if press else '-', key)

		if key == 'Pause' or key == 'Break':
			if press:
				if key == 'Break':
					pass

				# Only one running thread is allowed. Skips if it is already running.
				if self._log_event_thread is not None and self._log_event_thread.isAlive():
					pass
				else:
					self._log_event_thread = thread = threading.Thread(target=self._create_event)
					thread.setDaemon(True)
					thread.start()

		else:
			if self._capture_keys:
				self._key_sequence.append(('+' if press else '-') + key)
				self._latest_key_tapped = time.time()

	"""Helpers"""

	def loop(self):
		with open(os.path.join(self._dst_path, 'events.log'), 'a') as self._dst:
			self._logger.loop()

	def _create_event(self):
		# Calculates next free pattern index
		pattern_index = max([0] + [
			int(filename.lstrip('0')) for filename, extension in [
				os.path.splitext(entry) for entry in os.listdir(self._dst_path)
			] if filename.isdigit() and extension == '.png'
		]) + 1
		pattern_filename = '{:04d}.png'.format(pattern_index)
		pattern_path = os.path.join(self._dst_path, pattern_filename)

		try:
			try:
				# Asks for event type
				event_type = self._interactive_select_event_type()
				event = dict(type=event_type)

				if event_type in ('delay', 'keyboard_type', 'shell_command'):
					event['value'] = self._interactive_input_value()

				elif event_type in ('keyboard_tap', 'keyboard_press', 'keyboard_release'):
					self._key_sequence[:] = []
					self._capture_keys = True

					try:
						# Waits for a confirmation that a whole key sequence is tapped
						self._interactive_confirm_key_sequence()

						# Removes a Return-key if it was tapped in order to close confirmation dialog
						# (short time between tapping and closing of a confirmation dialog)
						if self._key_sequence[-2:] == ['+Return', '-Return'] and time.time() - self._latest_key_tapped < .1:
							self._key_sequence[-2:] = []

						event['value'] = ','.join([x for x in self._key_sequence if any((
							(event_type == 'keyboard_tap'),
							(event_type == 'keyboard_press' and x.startswith('+')),
							(event_type == 'keyboard_release' and x.startswith('-')),
						))])
					finally:
						self._capture_keys = False
						self._key_sequence[:] = []

				elif event_type.startswith('mouse_'):
					# Makes screen shot
					pyscreenshot.grab().save(pattern_path)

					# Crops screen shot
					self._interactive_crop_image(pattern_path)

					event['patterns'] = [pattern_filename]

				# Saves event
				logging.getLogger(__name__).info(repr(event))
				print >>self._dst, repr(event)
				self._dst.flush()

			except:
				# Removes unused screenshot
				if os.path.exists(pattern_path):
					os.unlink(pattern_path)
				raise

		except subprocess.CalledProcessError:
			pass

	@staticmethod
	def _interactive_select_event_type():
		event_types = (
			'delay',
			'jump',
			'shell_command',
			'keyboard_tap',
			'keyboard_press',
			'keyboard_release',
			'keyboard_type',
			'mouse_move',
			'mouse_press',
			'mouse_release',
			'mouse_click',
			'mouse_double_click',
			'mouse_scroll',
		)

		command = textwrap.dedent("""
			zenity
				--width """ + str(20 + 9 * max(len(x) for x in event_types)) + """
				--height """ + str(140 + 21 * len(event_types)) + """
				--list
				--text "Select event type"
				--ok-label "Create"
				--cancel-label "Cancel"
				--column "Event"
				""" + ' '.join(['"{}"'.format(x) for x in event_types]) + """
			"""
		).replace('\n', ' \\\n')
		result = subprocess.check_output(command, shell=True)
		result = result.rstrip()  # Removes trailing newline

		return result

	@staticmethod
	def _interactive_input_value():
		command = textwrap.dedent("""
			zenity
				--entry
				--text "Enter value"
				--entry-text ""
			"""
		).replace('\n', ' \\\n')
		result = subprocess.check_output(command, shell=True)
		result = result.rstrip()  # Removes trailing newline

		return result

	@staticmethod
	def _interactive_confirm_key_sequence():
		command = textwrap.dedent("""
			zenity
				--question
				--ellipsize
				--icon-name "info"
				--text "Enter key sequence, confirm it with mouse."
			"""
		).replace('\n', ' \\\n')
		subprocess.check_output(command, shell=True)
		return

	@staticmethod
	def _interactive_crop_image(path):
		command = textwrap.dedent("""
			./interactive-crop
				--title "Select a region and press Enter"
				--screen-offset {offset}
				"{path}"
			"""
		).replace('\n', '\\\n').format(path=path, offset=50)
		result = subprocess.check_output(command, shell=True)


def test_capture_controller():
	value = CaptureController()
	assert value == 5

	asdfsafd()
	assert anderes_wert == 10


def run_capture_controller():
	import argparse
	parser = argparse.ArgumentParser(description='Captures mouse and keyboard events and appends them to storage.')
	parser.add_argument('path', nargs='?', default='data', help='Directory path where to store the data (default "data")')
	kwargs = vars(parser.parse_args())  # Breaks here if something goes wrong

	CaptureController(**kwargs).loop()


def run_interactive_select_event_type():
	CaptureController._interactive_select_event_type()


def run_interactive_confirm_key_sequence():
	CaptureController._interactive_confirm_key_sequence()


def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--run-function', help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	globals()['run_' + (kwargs['run_function'] or 'capture_controller')]()


if __name__ == '__main__':
	main()
