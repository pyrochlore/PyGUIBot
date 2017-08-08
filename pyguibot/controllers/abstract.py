#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division
import datetime
import logging
import numpy
import os
import signal
import subprocess
import sys
import textwrap
import time

import cv2

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')
	# Run in application's working directory
	sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + '/..')
	os.chdir(sys.path[0])
	# Working interruption by Ctrl-C
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configure logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
	logging.getLogger(__name__).setLevel(logging.DEBUG)

from models.devices import (
	Screen,
)

__doc__ = """"""


class AbstractController(object):
	"""Abstract class for every controller"""

	def _create(self, dst_path, dst, with_exceptions=False, filename_type='datetime'):
		if filename_type == 'incremental':
			pattern_filename = self._generate_incremental_filename(dst_path)
		elif filename_type == 'datetime':
			pattern_filename = self._generate_datetime_filename(dst_path)
		pattern_filename += '.png'

		pattern_path = os.path.join(dst_path, pattern_filename)

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
						if self._key_sequence[-2:] == ['+Return', '-Return'] and time.time() - self._latest_key_triggered_timestamp < .1:
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
					Screen.get_screenshot().save(pattern_path)

					# Crops screen shot
					self._interactive_crop_image(pattern_path)

					event['patterns'] = [pattern_filename]

					# Asks for wait timeout
					timeout = self._interactive_input_value(message="Enter wait timeout")
					if timeout:
						try:
							event['timeout'] = float(timeout)
						except ValueError:
							pass

				# Saves event
				logging.getLogger(__name__).info(repr(event))
				print >>dst, repr(event)
				dst.flush()

			except:
				# Removes unused screenshot
				if os.path.exists(pattern_path):
					os.unlink(pattern_path)
				raise

		except subprocess.CalledProcessError:
			if with_exceptions:
				raise

	def _generate_incremental_filename(self, path):
		"""Returns next free incremental filename for directory"""
		pattern_index = max([0] + [
			int(filename.lstrip('0')) for filename, extension in [
				os.path.splitext(entry) for entry in os.listdir(path)
			] if filename.isdigit() and extension == '.png'
		]) + 1
		return '{:04d}'.format(pattern_index)

	def _generate_datetime_filename(self, path):
		"""Returns filename named by current datetime"""
		return datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S.%f')[:-3]

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
	def _interactive_confirm(message):
		command = textwrap.dedent("""
			zenity
				--question
				--text '""" + message + """'
			"""
		).replace('\n', ' \\\n')
		result = subprocess.check_output(command, shell=True)
		result = result.rstrip()  # Removes trailing newline

		return result

	@staticmethod
	def _interactive_input_value(message=None):
		command = textwrap.dedent("""
			zenity
				--entry
				--text "{}"
				--entry-text ""
			""".format(message if message is not None else "Enter value")
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
			{application_path}/interactive-crop
				--title "Select a region and press Enter"
				--screen-offset {offset}
				"{path}"
			"""
		).replace('\n', '\\\n').format(application_path=sys.path[0], path=path, offset=50)
		result = subprocess.check_output(command, shell=True)


def run_show_event_types_selector():
	"""Only for developing purposes"""
	AbstractController._interactive_select_event_type()


def run_show_confirmation():
	"""Only for developing purposes"""
	result = AbstractController._interactive_confirm('Test confirmation?')
	print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'result=', result; sys.stderr.flush()  # FIXME: must be removed/commented


def run_show_key_sequence_confirmation():
	"""Only for developing purposes"""
	AbstractController._interactive_confirm_key_sequence()


def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--run-function', help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_args())  # Breaks here if something goes wrong

	globals()['run_' + (kwargs['run_function'] or 'abstract_controller')]()

if __name__ == '__main__':
	main()