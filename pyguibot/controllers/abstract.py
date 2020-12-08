#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann

import ast
import contextlib
import datetime
import logging
import numpy
import os
import re
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

from models.abstract import ObservableAttrDict, ObservableList
from models.devices import (
	Screen,
)

__doc__ = """"""


class _State(ObservableAttrDict):
	pass


class AbstractController(object):
	"""Abstract class for every controller"""

	def __init__(self, path):
		"""Models"""
		self._state_model = state_model = _State()
		state_model.src_path = path
		state_model.dst_directory_path = dst_directory_path = (lambda x: (x if os.path.isdir(x) else os.path.dirname(x)))(os.path.realpath(path or '.'))
		# TODO: move temporary directory to /tmp
		state_model.tmp_directory_path = tmp_directory_path = os.path.join(dst_directory_path, '.tmp.pyguibot')
		state_model.exception = ''

		if not os.path.exists(tmp_directory_path):
			os.makedirs(tmp_directory_path)

	"""Helpers"""

	@contextlib.contextmanager
	def _with_data(self, src_path=None, dst_path=None):
		state_model = self._state_model

		# Loads lines
		if True:
			if src_path is None:
				src_path = state_model.src_path

			with (
					open(src_path)
					if src_path is not None and os.path.exists(src_path) else
					contextlib.nullcontext(enter_result=(None if sys.stdin.isatty() else sys.stdin))  # From stdin or nowhere
			) as src:
				lines = ObservableList(src.readlines() if src is not None else [])

			# Monitors if list was changed
			state = dict(changed=False)
			def on_updated(model=None, previous=(None, ), current=(None, )):
				if previous[0] != current[0]:
					state['changed'] = True
			lines.changed.bind(on_updated)

		yield lines

		# Saves lines
		if True:
			if dst_path is None:
				dst_path = state_model.src_path

			if state['changed'] or dst_path != src_path:
				if not dst_path:
					dst_path = self._save()

				if dst_path:
					with open(dst_path, 'w') as dst:
						print(''.join(lines), end='', file=dst)

	def _dump(self, event):
		"""Dumps event to string with a trailing newline"""
		_event = event.copy()
		comments = _event.pop('comments', '')
		level = _event.pop('level')
		return '\t' * level + (str(_event) if _event else '') + ('  ' if _event and comments else '') + comments + os.linesep

	def _restore(self, data):
		"""Parses raw string with a trailing newline, returns a dict-like object"""
		state_model = self._state_model

		data = data.rstrip(os.linesep)
		try:
			event = ast.literal_eval(data.lstrip()) if data.lstrip().startswith('{') else dict(comments=data.lstrip())
		except SyntaxError as e:
			state_model.exception = 'Can not parse data:<br/><pre>{data}</pre>'.format(**locals())
			raise
		event['level'] = (len(data) - len(data.lstrip()))
		return event

	def _create(self, template={}, with_exceptions=False, filename_type='datetime'):
		"""Creates and returns new event"""
		state_model = self._state_model

		try:
			event = dict(
				level=template.get('level', 0),
			)

			event['type'] = event_type = self._interactive_select_event_type()

			if event_type == 'goto':
				event['value'] = self._interactive_input_value(message='Enter line number')

			elif event_type == 'delay':
				event['value'] = self._interactive_input_value(message='Enter delay (in s.)')

			elif event_type in ('jump', 'break'):
				event['value'] = self._interactive_input_value(
					message='Enter number of shifts to {event[type]} (-+ for relative)'.format(**locals()),
					value=template.get('value', None),
				)
				event['message'] = self._interactive_input_value(
					message='Enter message',
					value=template.get('message', None),
				)

			elif event_type == 'equation':
				event['value'] = self._interactive_input_value(
					message='Enter equation (for example, X = {X} + 1)',
					value=template.get('value', None),
				)

			elif event_type == 'condition':
				event['value'] = self._interactive_input_value(
					message='Enter condition (for example, {X} == 5)',
					value=template.get('value', None),
				)

			elif event_type == 'shell_command':
				event['value'] = self._interactive_input_value(
					message='Enter shell command',
					value=template.get('value', None),
				)

			elif event_type == 'keyboard_type':
				event['value'] = self._interactive_input_value(
					message='Enter string to type',
					value=template.get('value', None),
				)

			elif event_type in ('keyboard_tap', 'keyboard_press', 'keyboard_release'):
				value = None

				# If self-object listens to keyboard events (capture.py)
				if hasattr(state_model, 'key_sequence'):
					state_model.key_sequence[:] = []
					state_model.capture_keys = True

					try:
						# Waits for a confirmation that a whole key sequence is tapped
						self._interactive_confirm_key_sequence()

						value = ','.join([x for x in state_model.key_sequence if any((
							(event_type == 'keyboard_tap'),
							(event_type == 'keyboard_press' and x.startswith('+')),
							(event_type == 'keyboard_release' and x.startswith('-')),
						))])
					finally:
						# Removes -Return from the beginning because tapped in order to select event type entry
						if value.startswith('-Return'):
							value = value.replace('-Return', '', 1).lstrip(',')
						# Removes +Return,-Return if tapped in order to close dialog
						if value.endswith('+Return,-Return') and time.time() - state_model.latest_key_triggered_timestamp < .1:
							value = value.rsplit('+', 1)[0].rstrip(',')
						# Replaces +<key>,-<key> with <key> in order to reduce string length
						for key in value.replace('+', '').replace('-', '').split(','):
							value = value.replace('+{0},-{0}'.format(key), key).replace(',,', ',')

						state_model.capture_keys = False
						state_model.key_sequence[:] = []

				value = self._interactive_input_value(
					message='Enter key sequence ("+" - press, "-" - release, comma-separated, for example +Return,-Return,+Left,-Left)',
					value=(value or template.get('value', None)),
				)

				event['value'] = value

			elif event_type.startswith('mouse_'):
				tmp_pattern_path = os.path.join(state_model.tmp_directory_path, '.screenshot.png')

				try:
					# Waits some seconds (to allow user to invoke menu or something else)
					time.sleep(2.)

					# Makes screen shot
					Screen.make_screenshot(tmp_pattern_path)

					# Crops screen shot
					self._interactive_crop_image(tmp_pattern_path)

					# Asks for a filename
					# TODO: rewrite for better logic for same patterns, maybe with a "select file or create new" dialog
					logging.getLogger(__name__).warning('')
					if filename_type == 'incremental':
						pattern_basename = self._generate_incremental_filename(state_model.dst_directory_path)
					elif filename_type == 'datetime':
						pattern_basename = self._generate_datetime_filename(state_model.dst_directory_path)
					try:
						pattern_basename = self._interactive_input_value(
							message='Enter pattern name (default: "{pattern_basename}")'.format(**locals()),
						)
					except subprocess.CalledProcessError:
						raise
					pattern_filename = pattern_basename + '.png'
					pattern_path = os.path.join(state_model.dst_directory_path, pattern_filename)
					os.rename(tmp_pattern_path, pattern_path)
					time.sleep(1.0)  # Waits till images will be moved

					event['patterns'] = [pattern_filename]

					# Asks for wait timeout
					event['timeout'] = float(0.0)
					# timeout = self._interactive_input_value(message="Enter wait timeout")
					# if timeout:
					#     try:
					#         event['timeout'] = float(timeout)
					#     except ValueError:
					#         pass

				except Exception:
					# Removes unused screenshot
					if os.path.exists(tmp_pattern_path):
						os.unlink(tmp_pattern_path)
					raise

			logging.getLogger(__name__).info(repr(event))
			return event

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
	def _substitute_variables_with_values(value, env=None, default=None):
		"""Replaces every {key} (or {env[key]}) with its environment variable"""
		value = re.sub('\{(\w+)\}', '{env[\\1]}', value)  # Allows to write {X} instead of {env[X]}
		env = os.environ if env is None else env
		if default is not None:
			env = _DefaultDict(
				env,
				default=(lambda x: (lambda k: (x)))(default),  # Allows to see default value if not set)
			)
		value = value.format(env=env)
		return value

	@staticmethod
	def _substitute_variables_with_keys_values(value, env=None, default=None):
		"""Replaces every {key} (or {env[key]}) with {key}(value|default)"""
		# value = re.sub('\{(\w+)\}', '{{\\1}}({env[\\1]})', value)  # Allows to see a variable name with its current value
		value = re.sub('\{(\w+)\}', '\\1[{env[\\1]}]', value)  # Allows to see a variable name with its current value
		env = os.environ if env is None else env
		if default is not None:
			env = _DefaultDict(
				env,
				default=(lambda x: (lambda k: (x)))(default),  # Allows to see default value if not set)
			)
		value = value.format(env=env)
		return value

	@staticmethod
	def _interactive_select_event_type():
		event_types = (
			'goto',
			'delay',
			'jump',
			'break',
			'equation',
			'condition',
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
				--width=""" + str(20 + 9 * max(len(x) for x in event_types)) + """
				--height=""" + str(140 + 21 * len(event_types)) + """
				--list
				--text="Select event type"
				--ok-label="Create"
				--cancel-label="Cancel"
				--column="Event"
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
				--text='""" + message + """'
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
				--text="{}"
				--entry-text="{}"
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
				--icon-name="info"
				--text="Enter key sequence and confirm it with mouse."
				--ok-label="Done"
				--cancel-label="Cancel"
			"""
		).replace('\n', ' \\\n')
		subprocess.check_output(command, shell=True, text=True)
		return

	@staticmethod
	def _interactive_crop_image(path):
		command = textwrap.dedent("""
			{application_path}/interactive-crop
				--title="Select a region and press Enter"
				--screen-offset={offset}
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
