#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division
import ast
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


from models.devices import (
	Keyboard,
	Mouse,
	Screen,
)

__doc__ = """"""


class RestoreController(object):
	""""""

	def __init__(self, path, from_line, to_line, with_screencast):
		self._src_path = src_path = path

		screen_record_is_running = True

		# Writes a screen record during execution
		def record_screen():
			path = os.path.join(src_path if src_path is not None else '.', '.screen_record' + datetime.datetime.now().strftime('-%Y-%m-%d-%H:%M:%S') + '.mkv')
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
			# Runs new screen record
			# With audio:
			# command = "avconv -f alsa -ac 2 -i {audio_device} -f x11grab -r {fps} -s {width}x{height} -i {display}+{x},{y} {audio_codec_options} {video_codec_options} -threads {threads} \"{path}\""
			# Without audio:
			command = "avconv -f x11grab -r {fps} -s {width}x{height} -i {display}+{x},{y} {video_codec_options} -threads {threads} \"{path}\""
			command = command.format(
				display=':0.0', x=0, y=0, width=screen_width, height=screen_height,
				audio_device='pulse',
				audio_codec_options='-acodec libvorbis -ab 320k',
				video_codec_options='-vcodec libx264 -preset ultrafast -g 15 -crf 0 -pix_fmt yuv444p',
				threads=multiprocessing.cpu_count(), fps=15,
				path=path,
			)
			logging.getLogger(__name__).info('Screen is recording into "%s"', path)
			# logging.getLogger(__name__).debug('Command: %s', command)
			process = subprocess.Popen(command, shell=True, preexec_fn=os.setsid, stdout=open(os.devnull, 'w'), stderr=open(os.devnull, 'w'))

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
			with open(os.path.join(src_path, 'events.log')) if src_path is not None else sys.stdin as src:
				pattern_x, pattern_y = 0, 0
				skip_level = None

				for index, line in enumerate(x.rstrip() for x in src):

					# Skips if outside selected lines
					if from_line is not None and index < from_line or to_line is not None and to_line < index:
						continue

					# Skips empty lines and comments
					if not line or line.lstrip().startswith('#'):
						continue

					level = len(line) - len(line.lstrip())

					# Skips level with exception occurred
					if skip_level is not None:
						if level >= skip_level:
							continue
						else:
							skip_level = None

					event = ast.literal_eval(line.lstrip())

					try:
						logging.getLogger(__name__).info('Status=%s', dict(index=index, code='current'))
						if 'patterns' in event:
							# Delays before screen-shot
							waiting_before_screenshot_time = 2.
							logging.getLogger(__name__).info('Waiting %ss before looking for patterns', waiting_before_screenshot_time)
							time.sleep(waiting_before_screenshot_time)

							# Looks for image patterns on the screen
							pattern_x, pattern_y = self._locate_image_patterns(
								paths=[os.path.join(self._src_path if self._src_path is not None else '.', x) for x in event['patterns']],
								timeout=float(event.get('timeout', 10.)),
								delay=float(event.get('delay', 2.)),
								threshold=float(event.get('threshold', .95)),
							)

						logging.getLogger(__name__).info('Making event %s', event['type'])

						if event['type'] == 'delay':
							time.sleep(float(event['value']))
						elif event['type'] == 'jump':
							level += 1 + int(event['value'])
							raise LookupError()
						elif event['type'] == 'shell_command':
							result = subprocess.check_output(event['value'], shell=True)
							logging.getLogger(__name__).info('Result: %s', result.rstrip())
						elif event['type'] == 'keyboard_press':
							self._tap(event['value'], delay=.08)
						elif event['type'] == 'keyboard_release':
							self._tap(event['value'], delay=.08)
						elif event['type'] == 'keyboard_tap':
							self._tap(event['value'], delay=.08)
						elif event['type'] == 'keyboard_type':
							Keyboard.type(event['value'], interval=.08)
						elif event['type'] == 'mouse_move':
							Mouse.slide(pattern_x, pattern_y)
						elif event['type'] == 'mouse_press':
							Mouse.slide(pattern_x, pattern_y)
							time.sleep(.2)
							Mouse.press(pattern_x, pattern_y)
						elif event['type'] == 'mouse_release':
							Mouse.slide(pattern_x, pattern_y)
							time.sleep(.2)
							Mouse.release(pattern_x, pattern_y)
						elif event['type'] == 'mouse_click':
							Mouse.slide(pattern_x, pattern_y)
							time.sleep(.2)
							Mouse.click(pattern_x, pattern_y, button=1, count=1)
						elif event['type'] == 'mouse_double_click':
							Mouse.slide(pattern_x, pattern_y)
							time.sleep(.2)
							Mouse.click(pattern_x, pattern_y, button=1, count=2)
						elif event['type'] == 'mouse_scroll':
							Mouse.slide(pattern_x, pattern_y)
							time.sleep(.2)
							Mouse.scroll(pattern_x, pattern_y)
						logging.getLogger(__name__).info('Status=%s', dict(index=index, code='completed'))

					except LookupError as e:
						logging.getLogger(__name__).info('Status=%s', dict(index=index, code=(
							'completed' if event['type'] == 'jump' else 'failed'
						)))
						if level > 0:
							logging.getLogger(__name__).info('Skipping level %s for %s', level, event)
							skip_level = level
						else:
							raise
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
		logging.getLogger(__name__).info('Looking for patterns "%s"...', paths)

		patterns = [self._load_array(x) for x in paths]

		while True:
			t1 = time.time()

			sys.stderr.write('.'); sys.stderr.flush()  # FIXME: must be removed/commented

			# Makes screen shot
			screenshot = Screen.get_screenshot()

			# Converts PIL image to numpy array
			screenshot_array = self._convert_image_to_array(screenshot)

			for path, pattern in zip(paths, patterns):
				# Looks for an image pattern
				result = cv2.matchTemplate(screenshot_array, pattern, cv2.TM_CCOEFF_NORMED)  # ~0.7s

				location = numpy.where(result >= threshold)
				for x, y in zip(*location[::-1]):
					logging.getLogger(__name__).info('Pattern "%s" is found', path)
					height, width = pattern.shape[:2]
					return x + width // 2, y + height // 2
					# cv2.rectangle(screenshot_array, (x, y), (x + width, y + height), (0, 0, 255), 1)

			# Checks if timeout reached
			_delay = delay - (time.time() - t1)
			if _delay > 0:
				time.sleep(_delay)
			else:
				logging.getLogger(__name__).info('Screenshot overtime %s', -_delay)
			t2 = time.time()
			timeout -= t2 - t1
			if timeout <= 0:
				if logging.getLevelName(logging.getLogger(__name__).getEffectiveLevel()) in ('DEBUG', 'INFO'):
					# Stores failed patterns
					for index, path in enumerate(paths):
						shutil.copyfile(path, os.path.join(self._src_path if self._src_path is not None else '.', '.pattern_{}.png'.format(index)))

					# Stores current screenshot
					self._save_array(screenshot_array, os.path.join(self._src_path if self._src_path is not None else '.', '.screenshot.png'))  # Comment it in production

					# # Shows diff image on the screen
					# window_title = 'Difference image'
					# cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
					# cv2.moveWindow(window_title, 80, 20)
					# cv2.resizeWindow(window_title, screenshot_array.shape[1] // 2, screenshot_array.shape[0] // 2)
					# cv2.imshow(window_title, result)
					# cv2.waitKey(0)
					# cv2.destroyAllWindows()
				raise LookupError('Timeout is reached. Patterns "{}" are not found.'.format(paths))
			continue

	@staticmethod
	def _load_array(path):
		mode = cv2.CV_LOAD_IMAGE_UNCHANGED
		# mode = cv2.CV_LOAD_IMAGE_GRAYSCALE
		# mode = cv2.CV_LOAD_IMAGE_COLOR
		return cv2.imread(path, mode)

	@staticmethod
	def _save_array(array, path):
		cv2.imwrite(path, array)

	@staticmethod
	def _convert_image_to_array(image):
		"""Converts PIL image to numpy array, returns array"""
		array = numpy.array(image)  # Convert to numpy array
		array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)  # Revert color order: RGB -> BGR
		return array


def run_find_template():
	"""Only for developing purposes"""
	src_path = 'data/'
	template = RestoreController._load_array(os.path.join(src_path, '.pattern.png'))
	screenshot = RestoreController._load_array(os.path.join(src_path, '.screenshot.png'))
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
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	RestoreController(**kwargs)
	print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'DONE'; sys.stderr.flush()  # FIXME: must be removed/commented


def main():
	import argparse
	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument('-r', '--run-function', default='init', choices=[k[len('run_'):] for k in globals() if k.startswith('run_')], help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	globals()['run_' + kwargs['run_function']]()

if __name__ == '__main__':
	main()
