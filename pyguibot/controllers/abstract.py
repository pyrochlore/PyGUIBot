#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann

import ast
import datetime
import logging
import numpy
import os
import signal
import subprocess
import sys
import textwrap
import time

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	# import importlib; importlib.reload(sys); sys.setdefaultencoding('utf-8')
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

	def _dump(self, event):
		"""Dumps event to string"""
		_event = event.copy()
		comments = _event.pop('comments', '')
		level = _event.pop('level')
		return '\t' * level + (str(_event) if _event else '') + ('  ' if _event and comments else '') + comments

	def _restore(self, data):
		"""Parses raw data, returns a dict-like object"""
		event = ast.literal_eval(data.lstrip()) if data.lstrip().startswith('{') else dict(comments=data.lstrip())
		event['level'] = (len(data) - len(data.lstrip()))
		return event

	def _create(self, dst_path, dst, with_exceptions=False, filename_type='datetime', previous_event=None):
		if filename_type == 'incremental':
			pattern_filename = self._generate_incremental_filename(os.path.dirname(os.path.realpath(dst_path)))
		elif filename_type == 'datetime':
			pattern_filename = self._generate_datetime_filename(os.path.dirname(os.path.realpath(dst_path)))
		pattern_filename += '.png'

		pattern_path = os.path.join(os.path.dirname(os.path.realpath(dst_path)), pattern_filename)

		try:
			try:
				# Asks for event type
				event_type = self._interactive_select_event_type()
				event = dict(previous_event or dict(level=0), **dict(type=event_type))

				if event_type == 'delay':
					event['value'] = self._interactive_input_value(message='Enter delay (in s.)')

				elif event_type in ('jump', 'break'):
					event['value'] = self._interactive_input_value(message='Enter number of shifts to {event[type]} (-+ for relative)'.format(**locals()))
					event['message'] = self._interactive_input_value(message='Enter message')

				elif event_type == 'keyboard_type':
					event['value'] = self._interactive_input_value(message='Enter string to type')

				elif event_type == 'shell_command':
					event['value'] = self._interactive_input_value(message='Enter shell command')

				elif event_type in ('keyboard_tap', 'keyboard_press', 'keyboard_release'):
					# If self-object does not listen to keyboard events
					if not hasattr(self, '_key_sequence'):
						event['value'] = self._interactive_input_value(message='Enter key sequence ("+" for key press, "-" for key release, comma-separated)', value=event['value'])
					else:
						self._key_sequence[:] = []
						self._capture_keys = True

						try:
							# Waits for a confirmation that a whole key sequence is tapped
							self._interactive_confirm_key_sequence()

							# # Removes a Return-key if it was tapped in order to close confirmation dialog
							# # (short time between tapping and closing of a confirmation dialog)
							# if self._key_sequence[-2:] == ['+Return', '-Return'] and time.time() - self._latest_key_triggered_timestamp < .1:
							#     self._key_sequence[-2:] = []

							event['value'] = ','.join([x for x in self._key_sequence if any((
								(event_type == 'keyboard_tap'),
								(event_type == 'keyboard_press' and x.startswith('+')),
								(event_type == 'keyboard_release' and x.startswith('-')),
							))])
						finally:
							self._capture_keys = False
							self._key_sequence[:] = []

				elif event_type.startswith('mouse_'):
					# Waits some seconds (to allow user to invoke menu or something else)
					time.sleep(2.)

					# Makes screen shot
					Screen.make_screenshot(pattern_path)

					# Crops screen shot
					self._interactive_crop_image(pattern_path)

					event['patterns'] = [pattern_filename]

					# Asks for wait timeout
					event['timeout'] = float(0.0)
					# timeout = self._interactive_input_value(message="Enter wait timeout")
					# if timeout:
					#     try:
					#         event['timeout'] = float(timeout)
					#     except ValueError:
					#         pass

				# Saves event
				logging.getLogger(__name__).info(repr(event))
				print(self._dump(event), file=dst)
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
			'break',
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
			'mouse_right_click',
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
		result = subprocess.check_output(command, shell=True, text=True)
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
		result = subprocess.check_output(command, shell=True, text=True)
		result = result.rstrip()  # Removes trailing newline

		return result

	@staticmethod
	def _interactive_input_value(message=None, value=None):
		command = textwrap.dedent("""
			zenity
				--entry
				--text "{}"
				--entry-text "{}"
			""".format(
				message or 'Enter value',
				value or '',
			)
		).replace('\n', ' \\\n')
		result = subprocess.check_output(command, shell=True, text=True)
		result = result.rstrip('\r\n')  # Removes trailing newline

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
		subprocess.check_output(command, shell=True, text=True)
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
		result = subprocess.check_output(command, shell=True, text=True)


class _DefaultDict(dict):
	"""Dict that calls default function and returns its result if no key found"""
	def __init__(self, items, default):
		self._default = default
		super(_DefaultDict, self).__init__(items)

	def __missing__(self, key):
		return self._default(key)


def run_show_event_types_selector():
	"""Only for developing purposes"""
	AbstractController._interactive_select_event_type()


def run_show_confirmation():
	"""Only for developing purposes"""
	result = AbstractController._interactive_confirm('Test confirmation?')
	print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'result=', result, file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented


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
