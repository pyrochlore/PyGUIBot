#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann (gehrmann.mail@gmail.com)

from __future__ import division, unicode_literals
import ast
import contextlib
import logging
import os
import signal
import subprocess
import sys
import threading
import watchdog.events
import watchdog.observers

if __name__ == '__main__':
	# Sets utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')
	# Runs in application's working directory
	os.chdir((os.path.dirname(__file__) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))
	# Working interruption by Ctrl-C
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configures logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(logging.DEBUG)

from PyQt import QtCore, QtGui, QtWidgets, uic

from helpers.caller import Caller
from models.abstract import AttrDict, ObservableAttrDict
# from models.settings import Settings


class _State(ObservableAttrDict):
	pass


class QtGuiController(object):
	def __init__(self, path):
		self._app = app = QtWidgets.QApplication(sys.argv)

		# Models
		self._state_model = state_model = _State()
		state_model.src_path = path
		state_model.src_path_events_observer = None
		# state_model.src_data = []
		state_model.process = None
		# state_model.plugins = set(controllers.plugins.__all__)
		# state_model.status = 'Press "Start" to (re)run collecting...'
		# state_model.log = ObservableList()
		# state_model.log.changed.bind(lambda model=None, previous=None, current=None: (state_model.changed(state_model, previous={'log': previous}, current={'log': current})))  # invoke parent's changed-event if is changed
		# state_model.exception = None

		self._state_colors = dict(ready=None, current='#fc0', completed='#6c6', failed='#f00')
		self._level_separator = '⎯'
		self._level_passive_point = '◯'
		self._level_active_point = '⬤'

		self._drag_entries = None
		self._drag_from = None
		self._drag_to = None

		# self.settings_model = settings_model = Settings()

		# Views
		self.__view = view = uic.loadUi('views/main.ui')

		self.__restore_window_geometry()
		view.closeEvent = self.__on_close
		view.keyPressEvent = self.__on_key_pressed
		# view.commands_tree.dragEvent = (lambda widget, previous_callback: (lambda event: (self.__on_commands_tree_dragping(event, widget, previous_callback))))(view.commands_tree, view.commands_tree.dragEvent)
		view.commands_tree.dragEnterEvent = (lambda widget, previous_callback: (lambda event: (self.__on_commands_tree_dragging(event, widget, previous_callback))))(view.commands_tree, view.commands_tree.dragEnterEvent)
		view.commands_tree.dropEvent = (lambda widget, previous_callback: (lambda event: (self.__on_commands_tree_dropping(event, widget, previous_callback))))(view.commands_tree, view.commands_tree.dropEvent)
		view.run_button.triggered.connect(self.__on_run_triggered)
		view.stop_button.triggered.connect(self.__on_stop_triggered)
		view.record_button.triggered.connect(self.__on_record_triggered)
		view.move_left_button.triggered.connect(self.__on_move_left_triggered)
		view.move_right_button.triggered.connect(self.__on_move_right_triggered)
		view.uncomment_button.triggered.connect(self.__on_uncomment_triggered)
		view.comment_button.triggered.connect(self.__on_comment_triggered)
		# view.plugins_tree.itemChanged.connect(self.__on_plugins_tree_item_changed)
		# view.dst_path_button.clicked.connect(self.__on_dst_path_button_clicked)
		# view.delay_widget.timeChanged.connect(self.__on_delay_widget_time_changed)
		# view.txt_format_checkbox.stateChanged.connect(self.__on_txt_format_checkbox_changed)
		# view.csv_format_checkbox.stateChanged.connect(self.__on_csv_format_checkbox_changed)
		# view.autostart_checkbox.stateChanged.connect(self.__on_autostart_checkbox_changed)
		# view.verbose_checkbox.stateChanged.connect(self.__on_verbose_checkbox_changed)
		# view.simulate_response_checkbox.stateChanged.connect(self.__on_simulate_response_checkbox_changed)
		# view.start_button.clicked.connect(self.__on_start_button_clicked)
		# view.clear_button.clicked.connect(self.__on_clear_button_clicked)

		view.show()

		"""Observe models by view"""
		state_model.changed.bind(self._on_model_updated)

		"""Fill blank view by models"""
		self._on_model_updated(state_model)

	"""Model's event handlers"""

	def _on_model_updated(self, model=None, previous=None, current=None):
		# logging.getLogger(__name__).debug(self.__class__, object.__repr__(model), previous and str(previous)[:80], current and str(current)[:80])

		state_model = self._state_model
		view = self.__view

		if model is state_model:
			if current is None or 'src_path' in current:
				self._set_src_path_events_observer()
				Caller.call_once_after(0, self._fill)

			# if current is None or 'src_data' in current:
			#     Caller.call_once_after(0, self._fill)

			if current is None or 'process' in current:
				# Toggles run and stop buttons
				view.run_button.setEnabled(state_model.process is None)
				view.stop_button.setEnabled(state_model.process is not None)
				view.record_button.setEnabled(state_model.process is None)
				view.uncomment_button.setEnabled(state_model.process is None)
				view.comment_button.setEnabled(state_model.process is None)

				# view.commands_tree.setAutoFillBackground(QtGui.QColor('#fcc'))
				# palette = QtWidgets.QPalette()
				# palette.setColor(QtWidgets.QPalette.Base, QtGui.QColor('#f00' if state_model.process else '#fff'))
				# view.commands_tree.setPalette(palette)
				view.commands_tree.setEnabled(False if state_model.process else True)

	"""View's event handlers"""

	def __on_close(self, event=None):
		with open('.geometry', 'w') as storage:
			print >>storage, self.__view.saveGeometry()

		with open('.state', 'w') as storage:
			print >>storage, self.__view.saveState()

	def __on_key_pressed(self, event):
		if event.key() == QtCore.Qt.Key_Escape:
			self.__view.close()

	def __on_commands_tree_dragging(self, event, widget, previous_callback):
		state_model = self._state_model
		view = self.__view
		tree = view.commands_tree

		self._drag_entries = [tree.topLevelItem(x.row()) for x in tree.selectedIndexes()]
		self._drag_from = [x.row() for x in tree.selectedIndexes()]

		previous_callback(event)

	def __on_commands_tree_dropping(self, event, widget, previous_callback):
		view = self.__view
		tree = view.commands_tree

		previous_callback(event)

		self._drag_to = [index for index in range(tree.topLevelItemCount()) if tree.topLevelItem(index) in self._drag_entries]

		Caller.call_once_after(.1, self._apply_drag)

	def __on_run_triggered(self, event):
		self._run()

	def __on_stop_triggered(self, event):
		self._stop()

	def __on_record_triggered(self, event):
		self._record()

	def __on_move_left_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._apply_move(indices, -1)

	def __on_move_right_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._apply_move(indices, +1)

	def __on_uncomment_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._apply_comment(indices, False)

	def __on_comment_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._apply_comment(indices, True)

	"""Helpers"""

	def loop(self):
		sys.exit(self._app.exec_())

	def __restore_window_geometry(self):
		try:
			with open('.geometry') as storage:
				self.__view.restoreGeometry(storage.read())

			# FIXME: does not work
			with open('.state') as storage:
				self.__view.restoreState(storage.read())
		except IOError:
			pass

	def _reset_tree_entries_states(self):
		state_model = self._state_model
		view = self.__view
		tree = view.commands_tree

		for entry in (tree.topLevelItem(index) for index in range(tree.topLevelItemCount())):
			if not entry.isFirstColumnSpanned():
				entry.setText(0, '  ')
				# entry.setBackground(0, QtGui.QBrush(QtGui.QColor(self._state_colors['ready'] or '#fff')))
				entry.setForeground(1, QtGui.QBrush(QtGui.QColor(self._state_colors['ready'] or '#999')))
				entry.setBackground(2, QtGui.QBrush(QtGui.QColor(self._state_colors['ready'] or QtCore.Qt.transparent)))
				entry.setBackground(3, QtGui.QBrush(QtGui.QColor(self._state_colors['ready'] or QtCore.Qt.transparent)))
				entry.setSelected(False)

	def _set_src_path_events_observer(self):
		state_model = self._state_model

		def on_modified(event):
			if event.src_path == os.path.join(state_model.src_path, 'events.log'):
				Caller.call_once_after(.1, self._fill)
		handler = watchdog.events.PatternMatchingEventHandler()
		handler.on_modified = on_modified

		state_model.src_path_events_observer = thread = watchdog.observers.Observer()
		thread.schedule(handler, path=state_model.src_path)
		thread.start()

	def _fill(self):
		state_model = self._state_model
		view = self.__view
		tree = view.commands_tree

		src_path = os.path.join(state_model.src_path, 'events.log')
		logging.getLogger(__name__).info('Filling...')
		max_level = 0
		tree.setIconSize(QtCore.QSize(65535, 64))
		tree.clear()
		with open(src_path) as src:
			for line in (x.rstrip() for x in src):

				level = (len(line) - len(line.lstrip()))
				max_level = max(max_level, level)

				event = ast.literal_eval(line.lstrip()) if line.lstrip().startswith('{') else dict(comments=line)

				entry = QtWidgets.QTreeWidgetItem(tree)
				entry.setFlags(entry.flags() ^ QtCore.Qt.ItemIsDropEnabled)  # Disallow dropping inside item

				text = {k: '' for k in range(tree.columnCount())}
				icons = dict()

				if 'comments' in event:  # If line is commented
					entry.setFirstColumnSpanned(True)
					text[0] += event['comments'].lstrip()
					entry.setForeground(0, QtGui.QBrush(QtGui.QColor('#666')))

				if 'type' in event:
					filename = 'unknown'
					if event['type'].startswith('keyboard_'):
						filename = 'keyboard'
					elif event['type'].startswith('mouse_'):
						filename = 'mouse'
					elif event['type'].endswith('_command'):
						filename = 'command'

					text[1] += '' + (self._level_separator + self._level_passive_point) * (len(line) - len(line.lstrip())) + self._level_separator + self._level_active_point + ' '
					icons[2] = QtGui.QPixmap('images/16/{}.png'.format(filename))
					text[2] += event['type'].replace(filename, '').strip('_')

				if 'value' in event:
					text[3] += '"' + event['value'] + '"'

				if event is not None and 'patterns' in event:
					border = 1
					spacing = 2
					pixmaps = [QtGui.QPixmap(os.path.join(os.path.dirname(src_path), x)) for x in event['patterns']]

					# Scales pixmaps in order to prevent it to be found on a screen-shot
					pixmaps = [x.scaled(QtCore.QSize(1.25 * x.width(), 1.25 * x.height()), QtCore.Qt.IgnoreAspectRatio) for x in pixmaps]

					# Stores a combined pixmap somewhere in order to prevent its destroying
					entry._combined_pixmap = combined_pixmap = QtGui.QPixmap(
						2 * border + spacing * (len(pixmaps) + 1) + sum(x.width() for x in pixmaps),
						2 * border + 2 * spacing + max(x.height() for x in pixmaps),
					)

					combined_pixmap.fill(QtGui.QColor('#fc0'))
					painter = QtGui.QPainter(combined_pixmap)
					painter.setPen(QtGui.QColor('#fff'))
					painter.drawRect(0, 0, combined_pixmap.width() - 1, combined_pixmap.height() - 1)
					for index, x in enumerate(pixmaps):
						painter.drawPixmap(
							border + spacing + sum((spacing + pixmaps[x].width()) for x in range(index)),
							(combined_pixmap.height() - x.height()) // 2,
							x,
						)

					icons[3] = QtGui.QIcon(combined_pixmap)

				# self._tree_items_to_lines[view] = line
				for index in range(tree.columnCount()):
					if index in text:
						entry.setText(index, text[index])
					if index in icons:
						entry.setIcon(index, QtGui.QIcon(icons[index]))
				tree.addTopLevelItem(entry)

		self._reset_tree_entries_states()

		# tree.sortItems(0, QtCore.Qt.AscendingOrder)

		for index in range(tree.columnCount()):
			tree.resizeColumnToContents(index)
		logging.getLogger(__name__).info('Filled')

	def _run(self):
		state_model = self._state_model
		view = self.__view
		tree = view.commands_tree

		if state_model.process is None:
			# Gets selected from and to lines
			selected_indices = set(x.row() for x in tree.selectedIndexes())
			from_line, to_line = min(selected_indices or [None]), max(selected_indices or [None])
			to_line = None if from_line == to_line else to_line

			# Resets icons
			self._reset_tree_entries_states()

			command = ['./controllers/restore.py', state_model.src_path]
			if from_line is not None:
				command += ['--from-line', from_line]
			if to_line is not None:
				command += ['--to-line', to_line]
			logging.getLogger(__name__).info('Running subprocess: %s', command)

			state_model.process = process = subprocess.Popen(
				cwd=os.getcwd(),
				shell=True, preexec_fn=os.setsid, args=' '.join([str(x) for x in command]),
				bufsize=1,
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
			)

			def read_stdout():
				while not process.stdout.closed and process.returncode is None:
					line = process.stdout.readline().rstrip()
					logging.getLogger(__name__).debug('STDOUT: %s', line)
				logging.getLogger(__name__).info('Subprocess stdout loop is closed')
			stdout_thread = threading.Thread(target=read_stdout)
			stdout_thread.daemon = True
			stdout_thread.start()

			def read_stderr():
				while not process.stderr.closed and process.returncode is None:
					line = process.stderr.readline().rstrip()
					logging.getLogger(__name__).debug('STDERR: %s', line)
					if '[INFO]  Status=' in line:
						value = line.split('=', 1)[1]
						if value.startswith('{'):
							status = ast.literal_eval(value)
							entry = tree.topLevelItem(int(status['index']))
							entry.setText(0, '' if status['code'] == 'current' else '')
							entry.setForeground(1, QtGui.QBrush(QtGui.QColor(self._state_colors[status['code']])))
							entry.setBackground(2, QtGui.QBrush(QtGui.QColor(self._state_colors[status['code']])))
							entry.setBackground(3, QtGui.QBrush(QtGui.QColor(self._state_colors[status['code']])))
							tree.scrollToItem(entry, tree.EnsureVisible)
							tree.viewport().update()  # Force update (fix for Qt5)
				logging.getLogger(__name__).info('Subprocess stderr loop is closed')
			stderr_thread = threading.Thread(target=read_stderr)
			stderr_thread.daemon = True
			stderr_thread.start()

			def check_if_alive():
				process.wait()
				exit_code = process.returncode
				logging.getLogger(__name__).info('Subprocess is terminated with exit code %s', exit_code)
				state_model.process = None
			is_alive_thread = threading.Thread(target=check_if_alive)
			is_alive_thread.daemon = True
			is_alive_thread.start()

	def _stop(self):
		state_model = self._state_model

		if state_model.process is not None:
			os.killpg(os.getpgid(state_model.process.pid), signal.SIGINT)
			state_model.process.wait()

	def _record(self):
		state_model = self._state_model

		if state_model.process is None:
			command = ['./controllers/capture.py', state_model.src_path]
			logging.getLogger(__name__).info('Running subprocess: %s', command)

			state_model.process = process = subprocess.Popen(
				cwd=os.getcwd(),
				shell=True, preexec_fn=os.setsid, args=' '.join([str(x) for x in command]),
				bufsize=1,
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
			)

			def read_stdout():
				while not process.stdout.closed and process.returncode is None:
					line = process.stdout.readline().rstrip()
					# logging.getLogger(__name__).debug('STDOUT: %s', line)
				logging.getLogger(__name__).info('Subprocess stdout loop is closed')
			stdout_thread = threading.Thread(target=read_stdout)
			stdout_thread.daemon = True
			stdout_thread.start()

			def read_stderr():
				while not process.stderr.closed and process.returncode is None:
					line = process.stderr.readline().rstrip()
					logging.getLogger(__name__).debug('STDERR: %s', line)
				logging.getLogger(__name__).info('Subprocess stderr loop is closed')
			stderr_thread = threading.Thread(target=read_stderr)
			stderr_thread.daemon = True
			stderr_thread.start()

			def check_if_alive():
				process.wait()
				exit_code = process.returncode
				logging.getLogger(__name__).info('Subprocess is terminated with exit code %s', exit_code)
				state_model.process = None
			is_alive_thread = threading.Thread(target=check_if_alive)
			is_alive_thread.daemon = True
			is_alive_thread.start()

	@contextlib.contextmanager
	def _with_data(self):
		# Loads lines
		src_path = os.path.join(self._state_model.src_path, 'events.log')
		with open(src_path) as src:
			lines = src.readlines()

		yield lines

		# Saves lines
		with open(src_path, 'w') as dst:
			print >>dst, ''.join(lines),

	def _apply_drag(self):
		with self._with_data() as lines:
			# Relocates lines
			from_index, to_index, count = min(self._drag_from), min(self._drag_to), len(self._drag_entries)
			cut, lines[from_index:from_index + count] = lines[from_index:from_index + count], []
			lines[min(self._drag_to):min(self._drag_to)] = cut

	def _apply_move(self, indices, count):
		with self._with_data() as lines:
			# Shifts/unshifts lines
			for index in indices:
				line = lines[index]
				lines[index] = max(0, len(line) - len(line.lstrip()) + count) * '\t' + line.lstrip()

	def _apply_comment(self, indices, comment=True):
		with self._with_data() as lines:
			# Comments/uncomments lines
			for index in indices:
				line = lines[index]
				lines[index] = max(0, len(line) - len(line.lstrip())) * '\t' + ('# ' if comment and line.lstrip()[:1] != '#' else '') + (line.lstrip() if comment or line.lstrip()[:3] != '# {' else line.lstrip().lstrip('# '))


def run_qt_gui_controller():
	import argparse
	parser = argparse.ArgumentParser(description='Restores mouse and keyboard events from storage.')
	parser.add_argument('path', nargs='?', default='data', help='Directory path where to load the data (default "data")')
	kwargs = vars(parser.parse_args())  # Breaks here if something goes wrong

	QtGuiController(**kwargs).loop()


def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--run-function', help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	globals()['run_' + (kwargs['run_function'] or 'qt_gui_controller')]()

if __name__ == '__main__':
	main()

if __name__ == '__main__':
	main()
