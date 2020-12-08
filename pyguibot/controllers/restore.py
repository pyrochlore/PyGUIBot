#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann



__doc__ = """
"""

import datetime
import logging
import multiprocessing
import numpy
import numexpr
import os
import screeninfo
import shutil
import signal
import subprocess
import sys
import threading
import time
try:
	import monotonic
	time.monotonic = monotonic.monotonic
except ImportError:
	logging.getLogger(__name__).warning('Monotonic time is not imported! Attention not to change time during execution!')
	time.monotonic = time.time

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	# import importlib; importlib.reload(sys); sys.setdefaultencoding('utf-8')
	# Run in application's working directory
	sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + '/..')
	# os.chdir(sys.path[0])
	# Working interruption by Ctrl-C
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configure logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(logging.DEBUG)

from controllers.abstract import _DefaultDict, AbstractController
from helpers.timer import Timer
from models.abstract import is_numeric
from models.devices import (
	Keyboard,
	Mouse,
	Screen,
)

try:
	import cv2
except ImportError:
	print('', file=sys.stderr)
	print('', file=sys.stderr)
	print('  Library is not found. Try to install it using:', file=sys.stderr)
	print('    # pip install opencv-python', file=sys.stderr)
	print('', file=sys.stderr)
	print('', file=sys.stderr)
	raise


class Break(Exception):
	pass


class RestoreController(AbstractController):
	""""""

	def __init__(self, path, verbose=0, from_line=None, to_line=None, with_screencast=False, shell_command_prefix=''):
		super(RestoreController, self).__init__(path=path)
		state_model = self._state_model
		state_model.verbose = verbose
		state_model.from_line = from_line
		state_model.to_line = to_line
		state_model.with_screencast = with_screencast
		state_model.shell_command_prefix = shell_command_prefix

	"""Helpers"""

	def loop(self):
		state_model = self._state_model
		from_line = state_model.from_line
		to_line = state_model.to_line

		screen_record_is_running = True

		# Writes a screen record during execution
		def record_screen():
			# path = os.path.join(state_model.tmp_directory_path, 'screencast-' + datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S') + '.mkv')
			path = os.path.join(state_model.tmp_directory_path, 'screencast.mkv')
			# Removes previously saved screen record
			try:
				os.unlink(path)
			except Exception:
				pass

			screen = screeninfo.get_monitors()[0]
			logging.getLogger(__name__).warning('screen=' + '%s', screen)

			# Runs new screen record (binary "avconv" from package "libav-tools")
			# With audio:
			# command = "avconv -f alsa -ac 2 -i {audio_device} -f x11grab -r 15 -s {width}x{height} -i {display}+{x},{y} {audio_codec_options} {video_codec_options} -threads {threads} \"{path}\""
			# Without audio:
			# command = "avconv -loglevel error -f x11grab -r 15 -s {width}x{height} -i {display}+{x},{y} {video_codec_options} -threads {threads} \"{path}\""
			# command = "avconv -loglevel error -f x11grab -r 15 -s {screen.width}x{screen.height} -i {display}+{x},{y} {video_codec_options} -threads {threads} \"{path}\""
			# ffmpeg -video_size 1280x748 -framerate 25 -f x11grab -i :0.0+64,20 output.mp4
			# ffmpeg -video_size 1280x748 -framerate 25 -f x11grab -i :0.0+64,20
			x_shift = 64
			command = "ffmpeg -video_size {width}x{height} -framerate 15 -f x11grab -i {display}+{x},{y} \"{path}\" 2>&1".format(
				# display=':0.0', x=0, y=0,
				display=':0.0', x=x_shift, y=0,  # Does not work well with y-shift
				width=screen.width - x_shift, height=screen.height - 0,
				# audio_device='pulse',
				# audio_codec_options='-an',  # Disables audio (was '-acodec libvorbis -ab 320k')
				# video_codec_options='-vcodec libx264 -preset ultrafast -g 15 -crf 0 -pix_fmt yuv444p',
				# threads=multiprocessing.cpu_count(),
				**locals()
			)
			logging.getLogger(__name__).warning('command=' + '%s', command)
			logging.getLogger(__name__).info('Screen is recording into "%s"', path)
			# logging.getLogger(__name__).debug('Command: %s', command)
			# process = subprocess.Popen(command, shell=True, text=True, preexec_fn=os.setsid, stdout=open(os.devnull, 'w'), stderr=open(os.devnull, 'w'))
			process = subprocess.Popen(command, shell=True, text=True, preexec_fn=os.setsid, stdout=open(os.devnull, 'w'), stderr=sys.stderr)

			# Waits for a stop
			while screen_record_is_running:
				time.sleep(1.)
			logging.getLogger(__name__).info('Screen record is saved to %s', path)
			os.killpg(os.getpgid(process.pid), signal.SIGINT)
			process.wait()

		if state_model.with_screencast:
			record_screen_thread = threading.Thread(target=record_screen)
			record_screen_thread.setDaemon(False)  # Keeps a thread alive if an exception in main thread occurred
			record_screen_thread.start()

		try:
			with self._with_data() as lines:
				# for index, line in enumerate(lines):
				index, next_index, skip_level = -1, None, None
				while True:
					if next_index is None:
						next_index = index + 1

					index, next_index = next_index, None

					if index >= len(lines):
						break

					line = lines[index]

					# Skips if outside selected lines
					if from_line is not None and index < from_line or to_line is not None and to_line < index:
						continue

					event = self._restore(line)

					# Skips empty lines and comments
					if 'comments' in event:  # If line is commented
						print('Status={}'.format(dict(index=index, code='')), file=sys.stderr); sys.stderr.flush()
						continue

					# Skips level with exception occurred
					logging.getLogger(__name__).debug('level: %s', event['level'])
					if skip_level is not None:
						logging.getLogger(__name__).debug('skip_level: %s', skip_level)
						if event['level'] >= skip_level:
							print('Status={}'.format(dict(index=index, code='')), file=sys.stderr); sys.stderr.flush()
							continue
						else:
							skip_level = None

					try:
						print('Status={}'.format(dict(index=index, code='current')), file=sys.stderr); sys.stderr.flush()
						print('Doing step #{line_number}'.format(line_number=(index + 1))); sys.stdout.flush()
						time.sleep(.1)  # Gives time to update status to "current" (GUI-side)

						event_x, event_y = Mouse.position()

						if 'patterns' in event:
							# Delays before screen-shot
							waiting_before_screenshot_time = 2.
							logging.getLogger(__name__).debug('Waiting %ss before looking for patterns', waiting_before_screenshot_time)
							time.sleep(waiting_before_screenshot_time)

							# Looks for image patterns on the screen
							try:
								patterns_paths = [
									os.path.join(
										state_model.dst_directory_path,
										self._substitute_variables_with_values(x)
									)
									for x in event['patterns']
								]
								event_x, event_y = self._locate_image_patterns(
									paths=patterns_paths,
									timeout=float(event.get('timeout', 5.)),
									delay=float(event.get('delay', 2.)),
									threshold=dict(dict(
										TM_CCOEFF_NORMED=.963,
										TM_CCORR_NORMED=.999,
									), **{
										method: float(event[key])
										for key in event if key.endswith('_threshold') for method in [key[:-len('_threshold')].upper()]
									}),
								)
							except Exception as e:
								# raise e.__class__(e.__class__(str(e) + ' [DEBUG: {}]'.format(locals()))).with_traceback(sys.exc_info()[2])
								raise

						# Shifts coordinates if 'x' or 'y' found in event
						event_x, event_y = [
							(x if xx[:1] in '+-' else 0) + int(xx)
							for x, xx in zip(
									(event_x, event_y),
									(event.get('x', '+0'), event.get('y', '+0')),
							)
						]

						logging.getLogger(__name__).debug('Making event %s', event['type'])

						if event['type'] == 'goto':
							value = self._substitute_variables_with_values(event['value'])
							if is_numeric(value):
								# Is number
								next_index = (index + int(value)) if value.startswith('+') or value.startswith('-') else int(value)
							else:
								# Is label
								_iterator = enumerate(lines)
								if value.startswith('+'):
									# Looks for label downward from current
									value, _filter = value[1:], lambda i, index: (i > index)
								elif value.startswith('-'):
									# Looks for label upward from current in reversed order
									value, _iterator, _filter = value[1:], zip(range(len(lines) - 1, -1, -1), lines[::-1]), lambda i, index: (i < index)
								else:
									# Looks for label downward from the beginning
									_filter = lambda i, index: (True)
								next_index = next((i for i, x in _iterator if _filter(i, index) for xx in [self._restore(x)] if xx.get('type', '') == 'label' and xx.get('value', '') == value), None)
								if index is None:
									raise Break('Label "{value}" not found'.format(**locals()))
							from_line, to_line = None, None  # Re-sets selected range (because no sense to go up/down only inside it)
						elif event['type'] == 'label':
							pass
						elif event['type'] == 'delay':
							value = self._substitute_variables_with_values(event['value'])
							time.sleep(float(value))
						elif event['type'] in ('jump', 'break'):
							value = self._substitute_variables_with_values(event['value'])
							if str(value)[:1] in '-+':
								event['level'] += 1 + int(value)
							else:
								event['level'] = int(value)
							raise Break(
								'{type}ing to {event[level]}'.format(
									type=event['type'].title(),
									**locals()
								) + (
									(' with message "' + self._substitute_variables_with_keys_values(event['message'], default='<none>') + '"') if 'message' in event else ''
								)
							)
						elif event['type'] == 'equation':
							key, equation = [x.strip() for x in event['value'].split('=', 1)]
							equation = self._substitute_variables_with_values(equation, env=_DefaultDict(
								os.environ,
								default=lambda k: (None),  # Allows to write "X = {X} or 0" in order to initiate variable X
							))
							value = str(numexpr.evaluate(equation))
							os.environ[key] = value
							print('Env={}'.format({key: value}), file=sys.stderr); sys.stderr.flush()
						elif event['type'] == 'condition':
							condition = self._substitute_variables_with_values(event['value'])
							value = bool(numexpr.evaluate(condition))
							if not value:
								raise Break('Condition not satisfied, breaking with{message}.'.format(
									message=' message "{event[message]}"'.format(**locals()) if 'message' in event else ' no message',
									**locals()
								))
						elif event['type'] == 'shell_command':
							shell_command = state_model.shell_command_prefix + self._substitute_variables_with_values(event['value'])
							logging.getLogger(__name__).debug('Command: %s', shell_command)
							process = subprocess.Popen(
								shell_command,
								shell=True, text=True,
								stdout=sys.stdout,
								stderr=sys.stderr,
								env=dict(os.environ, **dict(UPLOAD_PATH=state_model.tmp_directory_path)),
							)
							if event.get('wait', True):
								# logging.getLogger(__name__).warning('<shell command output>')
								exit_code = process.wait()
								# logging.getLogger(__name__).warning('</shell command output>')
								if exit_code:
									raise Break('Command was terminated with exit code {exit_code}.'.format(**locals()))
						elif event['type'] == 'keyboard_press':
							self._tap(self._substitute_variables_with_values(event['value']), delay=.08)
						elif event['type'] == 'keyboard_release':
							self._tap(self._substitute_variables_with_values(event['value']), delay=.08)
						elif event['type'] == 'keyboard_tap':
							self._tap(self._substitute_variables_with_values(event['value']), delay=.08)
						elif event['type'] == 'keyboard_type':
							value = self._substitute_variables_with_values(event['value'])
							Keyboard.type(value, interval=.15)
							# for character in self._substitute_variables_with_values(event['value']):
							#     Keyboard.press(character)
							#     time.sleep(.25)
							#     Keyboard.release(character)
						elif event['type'] == 'mouse_move':
							Mouse.slide(event_x, event_y)
						elif event['type'] == 'mouse_press':
							Mouse.slide(event_x, event_y)
							time.sleep(.2)  # Waits till reaction is shown
							Mouse.press(event_x, event_y)
						elif event['type'] == 'mouse_release':
							Mouse.slide(event_x, event_y)
							time.sleep(.2)  # Waits till reaction is shown
							Mouse.release(event_x, event_y)
						elif event['type'] == 'mouse_click':
							Mouse.slide(event_x, event_y)
							time.sleep(.2)  # Waits till reaction is shown
							Mouse.click(event_x, event_y, button=1, count=1)
						elif event['type'] == 'mouse_double_click':
							Mouse.slide(event_x, event_y)
							time.sleep(.2)  # Waits till reaction is shown
							Mouse.click(event_x, event_y, button=1, count=1)  # Fix: clicks once at first
							time.sleep(.8)  # Waits till reaction is shown
							Mouse.click(event_x, event_y, button=1, count=2)
						elif event['type'] == 'mouse_right_click':
							Mouse.slide(event_x, event_y)
							time.sleep(.2)  # Waits till reaction is shown
							Mouse.click(event_x, event_y, button=2, count=1)
						elif event['type'] == 'mouse_scroll':
							Mouse.scroll(horizontal=event_x, vertical=event_y)

						print('Status={}'.format(dict(index=index, code='completed')), file=sys.stderr); sys.stderr.flush()
						time.sleep(.2)  # Waits till reaction to event is shown and gives time to update status (GUI-side)

					except Break as e:
						# Updates status (GUI-side)
						if event['type'] in ('jump', 'condition'):
							print('Status={}'.format(dict(index=index, code=('completed'))), file=sys.stderr); sys.stderr.flush()
						else:
							print('Status={}'.format(dict(index=index, code=('failed'))), file=sys.stderr); sys.stderr.flush()

						if event['level'] > 0:
							logging.getLogger(__name__).debug('Skipping level %s for %s', event['level'], event)
							skip_level = event['level']
						elif event['type'] == 'jump':
							print(repr(e)); sys.stdout.flush()
							break
						else:
							# raise e.__class__, e.__class__(unicode(e) + ' [DEBUG: {}]'.format(dict(line=index, event=event))), sys.exc_info()[2]
							# print(repr(e), file=sys.stderr); sys.stderr.flush()
							print(str(e), file=sys.stderr); sys.stderr.flush()
							sys.exit(1)

		except KeyboardInterrupt:
			pass

		finally:
			if state_model.with_screencast:
				# Stops screen record thread and saves a screen record
				screen_record_is_running = False
				record_screen_thread.join()

	def _tap(self, keys, delay=.08):
		for key in keys.split(','):
			if key:
				try:
					if key[0] in '+-':
						getattr(Keyboard, {'+': 'press', '-': 'release'}[key[0]])(key[1:])
						time.sleep(delay)
					else:
						getattr(Keyboard, 'press')(key)
						time.sleep(delay)
						getattr(Keyboard, 'release')(key)
						time.sleep(delay)
				except KeyError as e:
					raise Break('Wrong key {key}'.format(**locals()))

	def _locate_image_patterns(self, paths, timeout, delay, threshold):
		"""Looks for image patterns on the screen, returns centered position or None"""
		state_model = self._state_model

		logging.getLogger(__name__).debug('Looking for patterns "%s"...', paths)

		patterns = [self._load_array(x) for x in paths]
		_timeout = timeout

		while True:
			t1 = time.monotonic()

			# Removes previous temporary images
			_path, _directories, _files = next(os.walk(state_model.tmp_directory_path))
			for _subpath in [x for x in _files if x.startswith('pattern-') and x.endswith('.png')]:
				os.unlink(os.path.join(_path, _subpath))

			# Makes screen shot
			logging.getLogger(__name__).debug('Capturing screen shot...')
			with Timer('capturing screenshot'):
				screenshot = Screen.get_screenshot()

			# Converts PIL image to numpy array
			# with Timer('converting screenshot to numpy-array'):
			screenshot_array = self._convert_image_to_array(screenshot)

			patterns_correlations = []
			for pattern_index, (path, pattern) in enumerate(zip(paths, patterns), start=1):
				if pattern is None:
					logging.getLogger(__name__).warning('Pattern #%s is None, path: %s, ignoring...', pattern_index, path)
				else:
					# Looks for an image pattern
					height, width = pattern.shape[:2]
					methods = list(threshold.keys())
					# with Timer('finding correlations'):
					correlations = [
						dict([['method', method]] + list(zip(
							('min_correlation', 'max_correlation', 'min_location', 'max_location'),
							cv2.minMaxLoc(cv2.matchTemplate(screenshot_array, pattern, getattr(cv2, method))),  # ~0.7s for each call of "cv2.matchTemplate"
						)))
						for method in methods
					]
					patterns_correlations += [correlations]

					# Prints out and saves found parts into files
					if any(x['max_correlation'] >= (.8 * threshold[x['method']]) for x in correlations):
						print('Correlation:', ', '.join([
							'{max_correlation:.1%} for {method} {max_location}'.format(**x) for x in sorted(correlations, key=lambda x: (x['method']))
						])); sys.stdout.flush()
						for correlation in correlations:
							if correlation['max_correlation'] >= (.8 * threshold[correlation['method']]):
								self._save_array(
									screenshot_array[
										correlation['max_location'][1]:correlation['max_location'][1] + height,
										correlation['max_location'][0]:correlation['max_location'][0] + width,
									],
									os.path.join(state_model.tmp_directory_path, 'pattern-{0}-{1[method]}-{1[max_correlation]:.1%}.png'.format(pattern_index, correlation)),
								)

					for correlation in correlations:
						if correlation['max_correlation'] >= threshold[correlation['method']]:
							logging.getLogger(__name__).debug('Pattern "%s" is found', path)
							x, y = correlation['max_location']
							return x + width // 2, y + height // 2
							# cv2.rectangle(screenshot_array, (x, y), (x + width, y + height), (0, 0, 255), 1)
			# else:
			# Prints out correlation values in order to calculate threshold value precisely
			# if any(xx['max_correlation'] >= (.8 * threshold[xx['method']]) for x in patterns_correlations for xx in x):
			#     print >>sys.stderr, 'Correlation:', ', '.join(['{max_correlation:.1%} for {method} {max_location}'.format(**xx) for x in patterns_correlations for xx in x]); sys.stderr.flush()
			#     for method, location, correlation in [(x['method'], x['max_location']) for x in patterns_correlations for xx in x]:
			#         print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'screenshot_array.__class__=', screenshot_array.__class__; sys.stderr.flush()  # FIXME: must be removed/commented
			#         # self._save_array(screenshot_array[location], os.path.join(state_model.tmp_directory_path, 'found_{}_{}_().png'.format(pattern_index, method, )))  # Comment it in production

			# Checks if timeout reached
			_delay = delay - (
				max(0, min(10, (  # If monotonic package is not installed then try to avoid negative time jumps and positive time jumps more than 10s
					time.monotonic() - t1  # Attention! NTP sync follows to wrong time interval! Disable it!
				)))
			)
			if _delay > 0:
				time.sleep(_delay)
			else:
				logging.getLogger(__name__).warning('Screenshot overtime %s', -_delay)
			t2 = time.monotonic()
			_timeout -= (
				max(0, min(10, (  # If monotonic package is not installed then try to avoid negative time jumps and positive time jumps more than 10s
					t2 - t1  # Attention! NTP sync follows to wrong time interval! Disable it!
				)))
			)
			if _timeout <= 0:
				# if logging.getLevelName(logging.getLogger(__name__).getEffectiveLevel()) in ('DEBUG', 'INFO'):
				if True:
					# Stores failed patterns
					for index, path in enumerate(paths, start=1):
						shutil.copyfile(path, os.path.join(state_model.tmp_directory_path, 'pattern-{}.png'.format(index)))

					# Stores current screenshot
					self._save_array(screenshot_array, os.path.join(state_model.tmp_directory_path, 'screenshot.png'))  # Comment it in production

					# # Shows diff image on the screen
					# window_title = 'Difference image'
					# cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
					# cv2.moveWindow(window_title, 80, 20)
					# cv2.resizeWindow(window_title, screenshot_array.shape[1] // 2, screenshot_array.shape[0] // 2)
					# cv2.imshow(window_title, result)
					# cv2.waitKey(0)
					# cv2.destroyAllWindows()
				# raise Break('Timeout is reached ({}). Patterns "{}" are not found.'.format(timeout, paths))
				raise Break('Timeout is reached ({}), patterns ("{}") not found.'.format(
					timeout,
					'", "'.join([os.path.splitext(os.path.basename(x))[0] for x in paths]),
				))
			continue

	@staticmethod
	def _load_array(path):
		mode = getattr(cv2, 'CV_LOAD_IMAGE_UNCHANGED', cv2.IMREAD_UNCHANGED)
		# mode = getattr(cv2, 'CV_LOAD_IMAGE_GRAYSCALE', cv2.IMREAD_GRAYSCALE)
		# mode = getattr(cv2, 'CV_LOAD_IMAGE_COLOR', cv2.IMREAD_COLOR)
		image = cv2.imread(path, mode)
		if image is None:
			if not os.path.exists(path):
				raise Exception('Path "{}" not exists'.format(path))
			raise Exception('Unknown error: cv2.imread("{}") returns None'.format(path))
		return image

	@staticmethod
	def _save_array(array, path):
		cv2.imwrite(path, array)

	@staticmethod
	def _convert_image_to_array(image):
		"""Converts PIL image to numpy array, returns array"""
		array = numpy.array(image)  # Convert to numpy array
		# array = numpy.array(image, dtype='uint8')  # Convert to numpy array
		array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)  # Revert color order: RGB -> BGR
		return array


def run_find_template():
	"""Only for developing purposes"""
	src_path = 'data/scenario.pyguibot'
	template = RestoreController._load_array(os.path.join(os.path.dirname(os.path.realpath(src_path)), '.pattern.png'))
	screenshot = RestoreController._load_array(os.path.join(os.path.dirname(os.path.realpath(src_path)), '.screenshot.png'))
	threshold = .8

	# template = template.astype(numpy.uint8)
	# screenshot = screenshot.astype(numpy.uint8)
	height, width = template.shape[:2]

	result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
	location = numpy.where(result >= threshold)
	for x, y in zip(*location[::-1]):
		cv2.rectangle(screenshot, (x, y), (x + width, y + height), (0, 0, 255), 1)

	# Shows result
	window_title = 'Difference image'
	cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
	cv2.moveWindow(window_title, 80, 20)
	cv2.resizeWindow(window_title, screenshot.shape[1] // 2, screenshot.shape[0] // 2)
	cv2.imshow(window_title, result)
	cv2.waitKey(0)
	cv2.destroyAllWindows()


def run_init():
	"""Runs command-line tests."""
	import argparse
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('-p', '--path', required=bool(sys.stdin.isatty()), help='Directory path where to load tests')
	parser.add_argument('-f', '--from-line', type=int, help='Line to begin from')
	parser.add_argument('-t', '--to-line', type=int, help='Line to end to')
	parser.add_argument('-s', '--with-screencast', action='store_true', help='Writes a video screencast')
	parser.add_argument('--shell-command-prefix', default='', help='Adds prefix to every event named "shell_command"')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	try:
		RestoreController(**kwargs).loop()
	except KeyboardInterrupt:
		pass


def main():
	import argparse
	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument('-r', '--run-function', default='init', choices=[k[len('run_'):] for k in globals() if k.startswith('run_')], help='Function to run (without "run_"-prefix)')
	parser.add_argument('-v', '--verbose', action='count', help='Raises logging level')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	# Raises verbosity level for script (through arguments -v and -vv)
	logging.getLogger(__name__).setLevel((logging.WARNING, logging.INFO, logging.DEBUG)[min(kwargs['verbose'] or 0, 2)])

	globals()['run_' + kwargs['run_function']]()

if __name__ == '__main__':
	main()
