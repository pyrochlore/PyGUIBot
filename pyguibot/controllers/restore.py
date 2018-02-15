#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division

__doc__ = """
"""

import datetime
import logging
import multiprocessing
import numpy
import os
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

import cv2

if __name__ == '__main__':
	# Set utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')
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

from controllers.abstract import AbstractController
from helpers.timer import Timer
from models.devices import (
	Keyboard,
	Mouse,
	Screen,
)


class RestoreController(AbstractController):
	""""""

	def __init__(self, path, verbose=0, from_line=None, to_line=None, with_screencast=False, shell_command_prefix=''):
		self._src_path = src_path = path
		self._tmp_path = tmp_path = os.path.join(os.path.realpath(os.path.dirname(src_path)) if src_path is not None else '.', '.tmp')

		# Creates temporary directory
		if not os.path.exists(tmp_path):
			os.makedirs(tmp_path)

		screen_record_is_running = True

		# Writes a screen record during execution
		def record_screen():
			# path = os.path.join(self._tmp_path, 'screencast-' + datetime.datetime.now().strftime('%Y-%m-%d-%H:%M:%S') + '.mkv')
			path = os.path.join(self._tmp_path, 'screencast.mkv')
			# Removes previously saved screen record
			try:
				os.unlink(path)
			except Exception:
				pass

			command = 'xdpyinfo'
			result = subprocess.check_output(command)
			for line in (x.strip() for x in result.splitlines()):
				if line.startswith('dimensions:'):
					screen_width, screen_height = [x for x in line.split(' ') if x][1].split('x')
					break
			else:
				raise Exception('Can not detect screen resolution.')
			# Runs new screen record (binary "avconv" from package "libav-tools")
			# With audio:
			# command = "avconv -f alsa -ac 2 -i {audio_device} -f x11grab -r {fps} -s {width}x{height} -i {display}+{x},{y} {audio_codec_options} {video_codec_options} -threads {threads} \"{path}\""
			# Without audio:
			command = "avconv -loglevel error -f x11grab -r {fps} -s {width}x{height} -i {display}+{x},{y} {video_codec_options} -threads {threads} \"{path}\""
			command = command.format(
				display=':0.0', x=0, y=0, width=screen_width, height=screen_height,
				audio_device='pulse',
				audio_codec_options='-an',  # Disables audio (was '-acodec libvorbis -ab 320k')
				video_codec_options='-vcodec libx264 -preset ultrafast -g 15 -crf 0 -pix_fmt yuv444p',
				threads=multiprocessing.cpu_count(), fps=15,
				path=path,
			)
			logging.getLogger(__name__).info('Screen is recording into "%s"', path)
			# logging.getLogger(__name__).debug('Command: %s', command)
			# process = subprocess.Popen(command, shell=True, preexec_fn=os.setsid, stdout=open(os.devnull, 'w'), stderr=open(os.devnull, 'w'))
			process = subprocess.Popen(command, shell=True, preexec_fn=os.setsid, stdout=open(os.devnull, 'w'), stderr=sys.stderr)

			# Waits for a stop
			while screen_record_is_running:
				time.sleep(1.)
			logging.getLogger(__name__).info('Screen record is saved to %s', path)
			os.killpg(os.getpgid(process.pid), signal.SIGINT)
			process.wait()

		if with_screencast:
			record_screen_thread = threading.Thread(target=record_screen)
			record_screen_thread.setDaemon(False)  # Keeps a thread alive if an exception in main thread occurred
			record_screen_thread.start()

		try:
			with open(src_path) if src_path is not None else sys.stdin as src:
				skip_level = None

				for index, line in enumerate(x.rstrip() for x in src):

					# Skips if outside selected lines
					if from_line is not None and index < from_line or to_line is not None and to_line < index:
						continue

					event = self._restore(line.rstrip('\n'))

					# Skips empty lines and comments
					if 'comments' in event:  # If line is commented
						print >>sys.stderr, 'Status={}'.format(dict(index=index, code='')); sys.stderr.flush()
						continue

					# Skips level with exception occurred
					logging.getLogger(__name__).debug('level: %s', event['level'])
					if skip_level is not None:
						logging.getLogger(__name__).debug('skip_level: %s', skip_level)
						if event['level'] >= skip_level:
							print >>sys.stderr, 'Status={}'.format(dict(index=index, code='')); sys.stderr.flush()
							continue
						else:
							skip_level = None

					try:
						print >>sys.stderr, 'Status={}'.format(dict(index=index, code='current')); sys.stderr.flush()
						print 'Doing step #{line_number}'.format(line_number=(index + 1)); sys.stdout.flush()

						event_x, event_y = Mouse.position()

						if 'patterns' in event:
							# Delays before screen-shot
							waiting_before_screenshot_time = 2.
							logging.getLogger(__name__).debug('Waiting %ss before looking for patterns', waiting_before_screenshot_time)
							time.sleep(waiting_before_screenshot_time)

							# Looks for image patterns on the screen
							try:
								patterns_paths = [os.path.join(os.path.dirname(os.path.realpath(self._src_path)) if self._src_path is not None else '.', x.format(**os.environ)) for x in event['patterns']]
								event_x, event_y = self._locate_image_patterns(
									paths=patterns_paths,
									timeout=float(event.get('timeout', 10.)),
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
								raise e.__class__, e.__class__(unicode(e) + ' [DEBUG: {}]'.format(dict(patterns_paths=patterns_paths))), sys.exc_info()[2]

						# Shifts coordinates if 'x' or 'y' found in event
						event_x, event_y = [
							(x if xx[:1] in '+-' else 0) + int(xx)
							for x, xx in zip(
									(event_x, event_y),
									(event.get('x', '+0'), event.get('y', '+0')),
							)
						]

						logging.getLogger(__name__).debug('Making event %s', event['type'])

						if event['type'] == 'delay':
							time.sleep(float(event['value']))
						elif event['type'] in ('jump', 'break'):
							time.sleep(.2)
							if str(event['value'])[:1] in '-+':
								event['level'] += 1 + int(event['value'])
							else:
								event['level'] = int(event['value'])
							raise LookupError('{type}ing to {event[level]} {message}.'.format(
								type=event['type'].title(),
								message='with message "{event[message]}"'.format(**locals()) if 'message' in event else 'with no message',
								**locals()
							))
						elif event['type'] == 'shell_command':
							shell_command = shell_command_prefix + event['value'].format(**os.environ)
							logging.getLogger(__name__).debug('Command: %s', shell_command)
							process = subprocess.Popen(
								shell_command,
								shell=True,
								stdout=sys.stdout,
								stderr=sys.stderr,
								env=dict(os.environ, **dict(UPLOAD_PATH=self._tmp_path)),
							)
							if event.get('wait', True):
								exit_code = process.wait()
								if exit_code:
									raise LookupError('Command was terminated with exit code {exit_code}.'.format(**locals()))
						elif event['type'] == 'keyboard_press':
							time.sleep(.2)
							self._tap(event['value'], delay=.08)
						elif event['type'] == 'keyboard_release':
							time.sleep(.2)
							self._tap(event['value'], delay=.08)
						elif event['type'] == 'keyboard_tap':
							time.sleep(.2)
							self._tap(event['value'], delay=.08)
						elif event['type'] == 'keyboard_type':
							time.sleep(.2)
							Keyboard.type(event['value'].format(**os.environ), interval=.15)
							# print >>sys.stderr, 'event["value"]=', event["value"]; sys.stderr.flush()  # FIXME: must be removed/commented
							# for character in event['value']:
							#     Keyboard.press(character)
							#     print >>sys.stderr, '{} pressed'.format(character); sys.stderr.flush()  # FIXME: must be removed/commented
							#     time.sleep(.25)
							#     Keyboard.release(character)
							#     print >>sys.stderr, '{} released'.format(character); sys.stderr.flush()  # FIXME: must be removed/commented
							#     time.sleep(.25)
						elif event['type'] == 'mouse_move':
							time.sleep(.2)
							Mouse.slide(event_x, event_y)
							time.sleep(.2)
						elif event['type'] == 'mouse_press':
							time.sleep(.2)
							Mouse.slide(event_x, event_y)
							time.sleep(.2)
							Mouse.press(event_x, event_y)
							time.sleep(.2)  # Waits till reaction is shown
						elif event['type'] == 'mouse_release':
							time.sleep(.2)
							Mouse.slide(event_x, event_y)
							time.sleep(.2)
							Mouse.release(event_x, event_y)
							time.sleep(.2)  # Waits till reaction is shown
						elif event['type'] == 'mouse_click':
							time.sleep(.2)
							Mouse.slide(event_x, event_y)
							time.sleep(.5)
							Mouse.click(event_x, event_y, button=1, count=1)
							time.sleep(.2)  # Waits till reaction is shown
						elif event['type'] == 'mouse_double_click':
							Mouse.slide(event_x, event_y)
							time.sleep(.2)
							Mouse.click(event_x, event_y, button=1, count=1)
							time.sleep(1.)
							Mouse.click(event_x, event_y, button=1, count=2)
							time.sleep(.2)  # Waits till reaction is shown
						elif event['type'] == 'mouse_right_click':
							Mouse.slide(event_x, event_y)
							time.sleep(.2)
							Mouse.click(event_x, event_y, button=2, count=1)
							time.sleep(.2)  # Waits till reaction is shown
						elif event['type'] == 'mouse_scroll':
							Mouse.slide(event_x, event_y)
							time.sleep(.2)
							Mouse.scroll(event_x, event_y)
							time.sleep(.2)  # Waits till reaction is shown

						print >>sys.stderr, 'Status={}'.format(dict(index=index, code='completed')); sys.stderr.flush()

					except LookupError as e:
						print >>sys.stderr, 'Status={}'.format(dict(index=index, code=(
							'completed' if event['type'] == 'jump' else 'failed'
						))); sys.stderr.flush()
						if event['level'] > 0:
							logging.getLogger(__name__).debug('Skipping level %s for %s', event['level'], event)
							skip_level = event['level']
						elif event['type'] == 'jump':
							print repr(e); sys.stdout.flush()
							break
						else:
							# raise e.__class__, e.__class__(unicode(e) + ' [DEBUG: {}]'.format(dict(line=index, event=event))), sys.exc_info()[2]
							print >>sys.stderr, repr(e); sys.stderr.flush()
							sys.exit(1)

		except KeyboardInterrupt:
			pass

		finally:
			if with_screencast:
				# Stops screen record thread and saves a screen record
				screen_record_is_running = False
				record_screen_thread.join()

	"""Helpers"""

	def _tap(self, keys, delay=.08):
		for key in keys.split(','):
			if key and key[0] in '+-':
				try:
					getattr(Keyboard, {'+': 'press', '-': 'release'}[key[0]])(key[1:])
				except KeyError as e:
					logging.getLogger(__name__).warn('Wrong key %s', key)
				time.sleep(delay)

	def _locate_image_patterns(self, paths, timeout, delay, threshold):
		"""Looks for image patterns on the screen, returns centered position or None"""
		logging.getLogger(__name__).debug('Looking for patterns "%s"...', paths)

		patterns = [self._load_array(x) for x in paths]
		_timeout = timeout

		while True:
			t1 = time.monotonic()

			# Removes previous temporary images
			_path, _directories, _files = next(os.walk(self._tmp_path))
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
				# Looks for an image pattern
				height, width = pattern.shape[:2]
				methods = threshold.keys()
				# with Timer('finding correlations'):
				correlations = [
					dict([['method', method]] + zip(
						('min_correlation', 'max_correlation', 'min_location', 'max_location'),
						cv2.minMaxLoc(cv2.matchTemplate(screenshot_array, pattern, getattr(cv2, method))),  # ~0.7s for each call of "cv2.matchTemplate"
					))
					for method in methods
				]
				patterns_correlations += [correlations]

				# Prints out and saves found parts into files
				if any(x['max_correlation'] >= (.8 * threshold[x['method']]) for x in correlations):
					print 'Correlation:', ', '.join([
						'{max_correlation:.1%} for {method} {max_location}'.format(**x) for x in sorted(correlations, key=lambda x: (x['method']))
					]); sys.stdout.flush()
					for correlation in correlations:
						if correlation['max_correlation'] >= (.8 * threshold[correlation['method']]):
							self._save_array(
								screenshot_array[
									correlation['max_location'][1]:correlation['max_location'][1] + height,
									correlation['max_location'][0]:correlation['max_location'][0] + width,
								],
								os.path.join(self._tmp_path, 'pattern-{0}-{1[method]}-{1[max_correlation]:.1%}.png'.format(pattern_index, correlation)),
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
			#         # self._save_array(screenshot_array[location], os.path.join(self._tmp_path, 'found_{}_{}_().png'.format(pattern_index, method, )))  # Comment it in production

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
						shutil.copyfile(path, os.path.join(self._tmp_path, 'pattern-{}.png'.format(index)))

					# Stores current screenshot
					self._save_array(screenshot_array, os.path.join(self._tmp_path, 'screenshot.png'))  # Comment it in production

					# # Shows diff image on the screen
					# window_title = 'Difference image'
					# cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
					# cv2.moveWindow(window_title, 80, 20)
					# cv2.resizeWindow(window_title, screenshot_array.shape[1] // 2, screenshot_array.shape[0] // 2)
					# cv2.imshow(window_title, result)
					# cv2.waitKey(0)
					# cv2.destroyAllWindows()
				raise LookupError('Timeout is reached ({}). Patterns "{}" are not found.'.format(timeout, paths))
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
	src_path = 'data/events.pyguibot'
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

	RestoreController(**kwargs)


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
