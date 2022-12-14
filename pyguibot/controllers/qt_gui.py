#!/bin/sh
# -*- coding: utf-8 -*-
# vim: set noexpandtab:
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann (gehrmann.mail@gmail.com)



__doc__ = """

Todo
----


"""

import ast
import contextlib
import datetime
import logging
import os
import pipes
import re
import signal
import subprocess
import sys
import threading
import time
try:
	import watchdog.events
	import watchdog.observers
except ImportError:
	print('', file=sys.stderr)
	print('', file=sys.stderr)
	print('  Library possibly is not found. Try to install it using:', file=sys.stderr)
	print('    # pip3 install watchdog', file=sys.stderr)
	print('', file=sys.stderr)
	print('', file=sys.stderr)
	raise

if __name__ == '__main__':
	# Sets utf-8 (instead of latin1) as default encoding for every IO
	# import importlib; importlib.reload(sys); sys.setdefaultencoding('utf-8')
	# import locale; locale.getpreferredencoding(False)
	# Runs in application's working directory
	sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + '/..')
	# os.chdir(sys.path[0])
	# Working interruption by Ctrl-C
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configures logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(logging.DEBUG)

from PyQt import QtCore, QtGui, QtWidgets, uic

from controllers.abstract import AbstractController
from helpers.caller import Caller
# from models.settings import Settings


class MainController(AbstractController):
	def __init__(self, path, verbose, geometry, autorun, autostop, autoexit, with_close_on_escape, with_screencast, with_observer, shell_command_prefix):
		super(MainController, self).__init__(path=path)
		state_model = self._state_model

		self._app = app = QtWidgets.QApplication(sys.argv)

		"""Models"""
		state_model.src_path_events_observer = None
		state_model.verbose = verbose
		state_model.process = None
		state_model.autostop = autostop
		state_model.autoexit = autoexit
		state_model.with_close_on_escape = with_close_on_escape
		state_model.with_screencast = with_screencast
		state_model.with_observer = with_observer
		state_model.shell_command_prefix = shell_command_prefix
		state_model.status = 'Click "Play" to (re)run or "Record" to add new events...'

		###
		if state_model.src_path is None and sys.stdin.isatty():
			logging.getLogger(__name__).warning('Path is not selected but console is attached')
		elif state_model.src_path is not None and not os.path.isdir(os.path.dirname(os.path.realpath(state_model.src_path))):
			logging.getLogger(__name__).warning('Path is selected but directory not exists: %s', os.path.dirname(os.path.realpath(state_model.src_path)))
			if state_model.autoexit:
				QtWidgets.QApplication.exit(1)
		else:
			if state_model.src_path is not None and not os.path.isfile(state_model.src_path):
				logging.getLogger(__name__).warning('Path is selected but file not exists: %s, will be created.', state_model.src_path)
				if state_model.autoexit:
					QtWidgets.QApplication.exit(1)
		###

		self._state_colors = dict(ready=None, current='#feb', completed='#cfc', failed='#fcc')
		self._level_separator = ''  # Can be ['???']
		self._level_passive_point = '???'  # Can be ['???']
		self._level_active_point = '???'  # Can be ['???']

		self._drag_entries = None
		self._drag_from = None
		self._drag_to = None

		# self.settings_model = settings_model = Settings()

		# Views
		self.__view = view = uic.loadUi(os.path.join(sys.path[0], 'views/main.ui'))

		if geometry is not None:
			width, height, x, y = ([int(x) for x in geometry.replace('+', ' +').replace('-', ' -').replace('x', ' ').split()] + [60] * 4)[:4]
			x = x + (0 if x >= 0 else QtWidgets.QApplication.desktop().screenGeometry(QtWidgets.QApplication.desktop().primaryScreen()).width() - width)
			y = y + (0 if y >= 0 else QtWidgets.QApplication.desktop().screenGeometry(QtWidgets.QApplication.desktop().primaryScreen()).height() - height)
			view.setGeometry(x, y, width, height)
		else:
			self.__restore_window_geometry()
		view.closeEvent = self.__on_close
		view.keyPressEvent = self.__on_key_pressed
		view.commands_tree.doubleClicked.connect(self.__on_commands_tree_double_clicked)
		# view.commands_tree.dragEvent = (lambda widget, previous_callback: (lambda event: (self.__on_commands_tree_dragping(event, widget, previous_callback))))(view.commands_tree, view.commands_tree.dragEvent)
		view.commands_tree.dragEnterEvent = (lambda widget, previous_callback: (lambda event: (self.__on_commands_tree_dragging(event, widget, previous_callback))))(view.commands_tree, view.commands_tree.dragEnterEvent)
		view.commands_tree.dropEvent = (lambda widget, previous_callback: (lambda event: (self.__on_commands_tree_dropping(event, widget, previous_callback))))(view.commands_tree, view.commands_tree.dropEvent)
		view.open_button.triggered.connect(self.__on_open_triggered)
		view.save_button.triggered.connect(self.__on_save_triggered)
		view.run_button.triggered.connect(self.__on_run_triggered)
		view.stop_button.triggered.connect(self.__on_stop_triggered)
		view.record_button.triggered.connect(self.__on_record_triggered)
		view.shift_left_button.triggered.connect(self.__on_shift_left_triggered)
		view.shift_right_button.triggered.connect(self.__on_shift_right_triggered)
		view.uncomment_button.triggered.connect(self.__on_uncomment_triggered)
		view.comment_button.triggered.connect(self.__on_comment_triggered)
		view.join_button.triggered.connect(self.__on_join_triggered)
		view.split_button.triggered.connect(self.__on_split_triggered)
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

		if autorun:
			self._run()

	"""Model's event handlers"""

	def _on_model_updated(self, model=None, previous=(None, ), current=(None, )):
		# logging.getLogger(__name__).debug('%s %s %s %s', self.__class__.__name__, model.__class__.__name__, previous and str(previous)[:80], current and str(current)[:80])
		# logging.getLogger(__name__).warning('%s %s %s %s', self.__class__.__name__, model.__class__.__name__, previous and str(previous)[:80], current and str(current)[:80])

		state_model = self._state_model
		view = self.__view

		if model is state_model:
			if current[0] is None or 'src_path' in current[0]:
				if previous[0] is not None and previous[0] != current[0]:
					with self._with_data(src_path=previous[0]['src_path'], dst_path=current[0]['src_path']):
						pass

				if state_model.src_path is not None:
					self._set_src_path_events_observer()

				view.info_label.setText('<strong>Path:</strong> <small>{state_model.src_path}</small>'.format(**locals()))

				Caller.call_once_after(0, self._fill)

			# if current[0] is None or 'src_data' in current[0]:
			#     Caller.call_once_after(0, self._fill)

			if current[0] is None or 'process' in current[0]:
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

			if current[0] is None or 'status' in current[0]:
				view.status_label.setText(state_model.status)

			if current[0] is None or 'exception' in current[0]:
				if state_model.exception:
					Caller.call_once_after(.1, self._show_exception, message='<small><pre><xmp>{}</xmp></pre></small>'.format(state_model.exception.replace('\n', '<br/>')))
					state_model.exception = ''

	"""View's event handlers"""

	def __on_close(self, event=None):
		with open('{}/.{}-geometry'.format(os.path.expanduser('~'), os.path.basename(sys.argv[0])), 'wb') as dst:
			dst.write(self.__view.saveGeometry())

		with open('{}/.{}-state'.format(os.path.expanduser('~'), os.path.basename(sys.argv[0])), 'wb') as dst:
			dst.write(self.__view.saveState())

	def __on_key_pressed(self, event):
		state_model = self._state_model

		if event.key() == QtCore.Qt.Key_Escape:
			if state_model.process is not None:
				self._stop()
			else:
				if state_model.with_close_on_escape:
					self.__view.close()
		elif event.modifiers() == (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier) and event.key() == QtCore.Qt.Key_I:
			QtCore.pyqtRemoveInputHook()
			import ipdb
			ipdb.set_trace()
		# Shortcuts {
		elif event.key() == QtCore.Qt.Key_Delete:
			self.__on_delete_pressed()
		elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_O:
			self.__on_open_triggered(event)
		elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_P:
			self.__on_run_triggered(event)
		elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_S:
			self.__on_stop_triggered(event)
		elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_R:
			self.__on_record_triggered(event)
		elif event.key() == QtCore.Qt.Key_Insert:
			self.__on_record_triggered(event)
		elif event.modifiers() & QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_Less:
			self.__on_shift_left_triggered(event)
		elif event.modifiers() & QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_Greater:
			self.__on_shift_right_triggered(event)
		elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_U:
			self.__on_uncomment_triggered(event)
		elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_C:
			self.__on_comment_triggered(event)
		elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_E:
			self.__on_split_triggered(event)
		elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_J:
			self.__on_join_triggered(event)
		elif event.modifiers() == QtCore.Qt.ControlModifier and event.key() == QtCore.Qt.Key_G:
			self.__on_open_gimp_triggered(event)
		# }
		else:
			logging.getLogger(__name__).warning(
				'Key %s%s%s%s has no handler',
				'Ctrl+' if event.modifiers() & QtCore.Qt.ControlModifier else '',
				'Alt+' if event.modifiers() & QtCore.Qt.AltModifier else '',
				'Shift+' if event.modifiers() & QtCore.Qt.ShiftModifier else '',
				next((key for key in dir(QtCore.Qt) if key.startswith('Key_') for value in [getattr(QtCore.Qt, key)] if value == event.key()), '<unknown({})>'.format(event.key())),
			)

	def __on_delete_pressed(self):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		if indices:
			count = len(indices)
			if QtWidgets.QMessageBox.question(
					self.__view,
					'Confirmation dialog',
					('{count} ' + ('entry' if count == 1 else 'entries') + ' will be removed!').format(**locals()),
					(
						0
						|QtWidgets.QMessageBox.Cancel
						|QtWidgets.QMessageBox.Ok
					),
			) == QtWidgets.QMessageBox.Ok:
				self._delete(index=min(indices), count=len(indices))

	def __on_commands_tree_double_clicked(self, index):
		state_model = self._state_model
		view = self.__view
		tree = view.commands_tree

		self._edit(index=index.row())

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

		Caller.call_once_after(.1, self._move, from_index=min(self._drag_from), to_index=min(self._drag_to), count=len(self._drag_entries))

	def __on_open_triggered(self, event):
		path = self._open()
		if path is not None:
			self._state_model.src_path = path

	def __on_save_triggered(self, event):
		path = self._save()
		if path is not None:
			self._state_model.src_path = path

	def __on_run_triggered(self, event):
		time.sleep(1.)
		self._run()

	def __on_stop_triggered(self, event):
		self._stop()

	def __on_record_triggered(self, event):
		self._record()

	def __on_shift_left_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._shift(indices, -1)

	def __on_shift_right_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._shift(indices, +1)

	def __on_uncomment_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._comment(indices, False)

	def __on_comment_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._comment(indices, True)

	def __on_join_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._join(indices)

		tree.clearSelection()

	def __on_open_gimp_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._open_gimp(indices)

		tree.clearSelection()

	def __on_split_triggered(self, event):
		view = self.__view
		tree = view.commands_tree

		indices = set([x.row() for x in tree.selectedIndexes()])
		self._split(indices)

		tree.clearSelection()

	"""Helpers"""

	def loop(self):
		try:
			return self._app.exec_()
		finally:
			self._stop()

	def __restore_window_geometry(self):
		try:
			with open('{}/.{}-geometry'.format(os.path.expanduser('~'), os.path.basename(sys.argv[0])), 'rb') as src:
				self.__view.restoreGeometry(src.read())

			# FIXME: does not work
			with open('{}/.{}-state'.format(os.path.expanduser('~'), os.path.basename(sys.argv[0])), 'rb') as src:
				self.__view.restoreState(src.read())
		except IOError:
			pass

	def _open(self):
		"""Shows dialog to open (maybe not existent) file"""
		path = None

		dialog = QtWidgets.QFileDialog(parent=self.__view)
		dialog.setWindowTitle('Select file to load')
		dialog.setNameFilter('PyGUIBot files (*.pyguibot)')
		dialog.setFileMode(dialog.AnyFile)
		dialog.setAcceptMode(dialog.AcceptOpen)
		# dialog.setOption(dialog.DontUseNativeDialog)
		if dialog.exec_() == QtWidgets.QDialog.Accepted:
			path = str(dialog.selectedFiles()[0])
			if not path.endswith('.pyguibot'):
				path += '.pyguibot'

			# Tries to open selected path
			try:
				with open(path):
					pass
			except Exception as e:
				QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, 'Error!', 'Failed to open!\n\n{}'.format(e)).exec_()
				path = None

		return path

	def _save(self):
		"""Shows dialog to save file"""
		path = None

		dialog = QtWidgets.QFileDialog(parent=self.__view)
		dialog.setWindowTitle('Select file to save')
		dialog.setNameFilter('PyGUIBot files (*.pyguibot)')
		dialog.setFileMode(dialog.AnyFile)
		dialog.setAcceptMode(dialog.AcceptSave)
		# dialog.setOption(dialog.DontUseNativeDialog)
		if dialog.exec_() == QtWidgets.QDialog.Accepted:
			path = str(dialog.selectedFiles()[0])
			if not path.endswith('.pyguibot'):
				path += '.pyguibot'

			try:
				# # Creates file (if not exists)
				# if self._state_model.src_path is not None:
				#     with open(self._state_model.src_path) as src:
				#         with open(path, 'w') as dst:
				#             dst.write(src.read())
				# else:
				#     with open(path, 'a'):
				#         pass
				with open(path, 'a'):
					pass
			except Exception as e:
				QtWidgets.QMessageBox(QtWidgets.QMessageBox.Critical, 'Error!', 'Failed to save there!\n\n{}'.format(e)).exec_()
				path = None

		return path

	def _reset_tree_entries_states(self):
		view = self.__view
		tree = view.commands_tree

		for entry in (tree.topLevelItem(index) for index in range(tree.topLevelItemCount())):
			if not entry.isFirstColumnSpanned():
				entry.setText(0, '  ')
				# entry.setBackground(0, QtGui.QBrush(QtGui.QColor(self._state_colors['ready'] or '#fff')))
				entry.setForeground(1, QtGui.QBrush(QtGui.QColor(self._state_colors['ready'] or '#999')))
				entry.setBackground(2, QtGui.QBrush(QtGui.QColor(self._state_colors['ready'] or QtCore.Qt.transparent)))
				entry.setBackground(3, QtGui.QBrush(QtGui.QColor(self._state_colors['ready'] or QtCore.Qt.transparent)))
				# entry.setSelected(False)

	def _set_src_path_events_observer(self):
		state_model = self._state_model

		if state_model.with_observer:
			def on_modified(event):
				if os.path.realpath(event.src_path) == os.path.realpath(state_model.src_path):
					Caller.call_once_after(.1, self._fill)
			handler = watchdog.events.PatternMatchingEventHandler()
			handler.on_modified = on_modified

			state_model.src_path_events_observer = thread = watchdog.observers.Observer()
			thread.schedule(handler, path=os.path.dirname(os.path.realpath(state_model.src_path)))
			thread.start()

	# def _get_entry_fingerprint(self, index):
	#     view = self.__view
	#     tree = view.commands_tree

	#     entry = tree.topLevelItem(index)
	#     # return str(index) + ':' + ''.join([''.join([xx for xx in unicode(entry.text(x)) if xx.isalnum()]) for x in range(tree.columnCount()) if x != 1])
	#     return str(index)

	def _fill(self):
		state_model = self._state_model
		view = self.__view
		tree = view.commands_tree

		selected_rows = [x.row() for x in tree.selectedIndexes()]

		logging.getLogger(__name__).info('Filling...')
		scroll_y_position = tree.verticalScrollBar().value()  # Save scroll-y position
		tree.setIconSize(QtCore.QSize(65535, 64))
		tree.clear()

		self._fill_tree_entries()
		self._reset_tree_entries_states()

		for index in range(tree.topLevelItemCount()):
			if index in selected_rows:
				entry = tree.topLevelItem(index)
				entry.setSelected(True)

		# tree.sortItems(0, QtCore.Qt.AscendingOrder)

		for index in range(tree.columnCount()):
			tree.resizeColumnToContents(index)
		tree.verticalScrollBar().setValue(scroll_y_position)  # Restore scroll-y position
		logging.getLogger(__name__).info('Filled')

	def _fill_tree_entries(self):
		"""Re-fills tree entries without clearing tree"""
		state_model = self._state_model
		view = self.__view
		tree = view.commands_tree

		with self._with_data() as lines:
			index = 0
			# Appends or updates entries
			for index, line in enumerate((x for x in lines)):
				entry = tree.topLevelItem(index)
				if entry is None:
					# Creates entry if not exists
					entry = QtWidgets.QTreeWidgetItem(tree)
					entry.setFlags(entry.flags() ^ QtCore.Qt.ItemIsDropEnabled)  # Disallow dropping inside item
					tree.addTopLevelItem(entry)

				self._fill_tree_entry(index, entry, line)

			# Removes superfluous entries
			for index in range(index + 1, tree.topLevelItemCount()):
				entry = tree.topLevelItem(index)
				tree.takeTopLevelItem(index)

	def _fill_tree_entry(self, index, entry, line):
		state_model = self._state_model
		view = self.__view
		tree = view.commands_tree

		line_number = index + 1
		text = {k: '' for k in range(tree.columnCount())}
		icons = dict()

		event = self._restore(line)

		text[0] += '{line_number}. '.format(**locals())
		if 'comments' in event:  # If line is commented
			text[0] += event['comments'].lstrip()
			entry.setFirstColumnSpanned(True)
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
			icons[2] = self.__load_pixmap(os.path.join(sys.path[0], 'images/16/{}.png'.format(filename)))
			text[2] += event['type'].replace(filename, '').strip('_')

		if 'value' in event:
			value = event['value']
			# value = re.sub('\{(\w+)\}', '{{\\1}}({env[\\1]})', value)  # Allows to see a variable name with its current value
			text[3] += (text[3] and ', ') + '"' + self._substitute_variables_with_keys_values(value, default='<none>') + '"'

		if 'timeout' in event:
			text[3] += (text[3] and ', ') + 'wait {}s'.format(event['timeout'])

		if 'message' in event:
			text[3] += (text[3] and ', ') + '"' + self._substitute_variables_with_keys_values(event['message'], default='<none>') + '"'

		if event is not None and 'patterns' in event:
			border = 1
			spacing = 2
			patterns_paths = [
				os.path.join(
					(os.path.dirname(os.path.realpath(state_model.src_path)) if state_model.src_path is not None else '.'),
					self._substitute_variables_with_values(x, default='default'),
				) for x in event['patterns']
			]
			for pattern_path in patterns_paths:
				if not os.path.exists(pattern_path):
					logging.getLogger(__name__).error('Pattern not exists: %s', pattern_path.rsplit(os.path.sep, 1)[1])
			pixmaps = [self.__load_pixmap(x if os.path.exists(x) else os.path.join(sys.path[0], 'images/16/not-found.png')) for x in patterns_paths]

			# Scales pixmaps in order to prevent it to be found on a screen-shot
			pixmaps = [x.scaled(QtCore.QSize(int(2. * x.width()), int(2. * x.height())), QtCore.Qt.IgnoreAspectRatio) for x in pixmaps]

			# Stores a combined pixmap somewhere in order to prevent its destroying
			entry._combined_pixmap = combined_pixmap = QtGui.QPixmap(
				2 * border + spacing * (len(pixmaps) + 1) + sum(x.width() for x in pixmaps),
				2 * border + 2 * spacing + max(x.height() for x in pixmaps),
			)

			combined_pixmap.fill(QtGui.QColor('#fc0'))
			painter = QtGui.QPainter(combined_pixmap)
			painter.setPen(QtGui.QColor('#fff'))
			painter.drawRect(0, 0, combined_pixmap.width() - 1, combined_pixmap.height() - 1)
			for _index, x in enumerate(pixmaps):
				painter.drawPixmap(
					border + spacing + sum((spacing + pixmaps[x].width()) for x in range(_index)),
					(combined_pixmap.height() - x.height()) // 2,
					x,
				)

			icons[3] = QtGui.QIcon(combined_pixmap)

		# self._tree_items_to_lines[view] = line
		for _index in range(tree.columnCount()):
			if _index in text:
				entry.setText(_index, text[_index])
				entry.setToolTip(_index, '#{}  {}'.format(line_number, line))
				entry.setStatusTip(_index, '#{}  {}'.format(line_number, line))
			if _index in icons:
				entry.setIcon(_index, QtGui.QIcon(icons[_index]))
				entry.setToolTip(_index, '#{}  {}'.format(line_number, line))
				entry.setStatusTip(_index, '#{}  {}'.format(line_number, line))

	@staticmethod
	def _show_exception(message):
		QtWidgets.QMessageBox(
			QtWidgets.QMessageBox.Critical,
			'Exception!',
			'<small><xmp>{}</xmp></small>'.format(message.replace('\n', '<br/>')),
		).exec_()

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

			command = [os.path.join(sys.path[0], './controllers/restore.py')]
			for index in range({logging.INFO: 1, logging.DEBUG: 2}.get(logging.getLogger(__name__).level, 0)):
				command += ['-v']
			if state_model.src_path is not None:
				command += ['--path', pipes.quote(state_model.src_path)]
			if from_line is not None:
				command += ['--from-line', from_line]
			if to_line is not None:
				command += ['--to-line', to_line]
			if state_model.with_screencast:
				command += ['--with-screencast']
			if state_model.shell_command_prefix is not None:
				command += ['--shell-command-prefix', pipes.quote(state_model.shell_command_prefix)]
			logging.getLogger(__name__).info('Running subprocess: %s', command)

			state_model.process = process = subprocess.Popen(
				cwd=os.getcwd(),
				shell=True, text=True, args=' '.join([str(x) for x in command]),
				start_new_session=True,  # Daemonizes process, the same as preexec_fn=os.setsid
				bufsize=1,
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
			)
			error_messages = []

			def read_stdout():
				try:
					for line in (x.rstrip() for x in iter(process.stdout.readline, '')):
						if not line:  # Probably process was terminated
							break
						try:
							print(datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3], '{0.f_code.co_filename}:{0.f_lineno}'.format(sys._getframe()), line, file=sys.stdout); sys.stdout.flush()
						except Exception as e:
							print('Exception in thread:', file=sys.stderr); sys.stderr.flush()
							print(e, file=sys.stderr); sys.stderr.flush()
				except ValueError:
					logging.getLogger(__name__).warning('ValueError raised, ignoring.')
				logging.getLogger(__name__).debug('Subprocess stdout loop is closed')
			stdout_thread = threading.Thread(target=read_stdout)
			stdout_thread.daemon = True
			stdout_thread.start()

			def read_stderr():
				try:
					for line in (x.rstrip() for x in iter(process.stderr.readline, '')):
						if not line:  # Probably process was terminated
							break
						try:
							if line.startswith('Status='):
								value = line.split('=', 1)[1]
								if value.startswith('{'):
									status = ast.literal_eval(value)
									entry = tree.topLevelItem(int(status['index']))
									if entry is not None:
										if status.get('code', False):
											entry.setText(0, '???' if status['code'] == 'current' else '')
											entry.setForeground(1, QtGui.QBrush(QtGui.QColor(self._state_colors[status['code']])))
											entry.setBackground(2, QtGui.QBrush(QtGui.QColor(self._state_colors[status['code']])))
											entry.setBackground(3, QtGui.QBrush(QtGui.QColor(self._state_colors[status['code']])))
										tree.scrollToItem(entry, tree.EnsureVisible)
										tree.viewport().update()  # Force update (fix for Qt5)
							elif line.startswith('Env='):
								value = line.split('=', 1)[1]
								if value.startswith('{'):
									env = ast.literal_eval(value)
									os.environ.update(env)
									Caller.call_once_after(0, self._fill_tree_entries)
							elif '[DEBUG]  ' in line:
								logging.getLogger(__name__).debug(line)
							elif '[INFO]  ' in line:
								logging.getLogger(__name__).info(line)
							elif '[WARNING]  ' in line:
								logging.getLogger(__name__).warning(line)
							else:
								logging.getLogger(__name__).error(line)
								error_messages.append(line)
						except Exception as e:
							print('Exception in thread:', file=sys.stderr); sys.stderr.flush()
							print(e, file=sys.stderr); sys.stderr.flush()
				except ValueError:
					logging.getLogger(__name__).warning('ValueError raised, ignoring.')
				logging.getLogger(__name__).debug('Subprocess stderr loop is closed')
			stderr_thread = threading.Thread(target=read_stderr)
			stderr_thread.daemon = True
			stderr_thread.start()

			def check_if_alive():
				with self._with_status('Please wait...'):
					process.wait()  # Do not use communicate() - conflicts with threads for stdout/stderr
				exit_code = process.returncode

				if exit_code:
					logging.getLogger(__name__).error('Subprocess was terminated with exit code %s', exit_code)

					stderr = '\n'.join(error_messages)
					if stderr:
						state_model.exception = stderr
				else:
					logging.getLogger(__name__).info('Subprocess was terminated')

				if state_model.autostop and exit_code:
					pass
				elif state_model.autoexit:
					# raise Exception('Subprocess was terminated with exit code %s', exit_code)
					QtWidgets.QApplication.exit(exit_code)
				state_model.process = None

			is_alive_thread = threading.Thread(target=check_if_alive)
			is_alive_thread.daemon = True
			is_alive_thread.start()

	def _stop(self):
		state_model = self._state_model

		if state_model.process is not None:
			try:
				os.killpg(os.getpgid(state_model.process.pid), signal.SIGINT)
				state_model.process.wait()
			except KeyboardInterrupt:
				pass
			state_model.process = None

	def _record(self):
		state_model = self._state_model
		view = self.__view
		tree = view.commands_tree

		if state_model.process is None:
			# Shows dialog to select path (if not selected)
			if state_model.src_path is None:
				path = self._save()
				if path is None:
					# Terminates recording if no file to save it
					return
				state_model.src_path = path

			command = [os.path.join(sys.path[0], './controllers/capture.py')]
			for index in range(state_model.verbose or 0):
				command += ['-v']
			if state_model.src_path is not None:
				command += ['--path', pipes.quote(state_model.src_path)]
			logging.getLogger(__name__).info('Running subprocess: %s', command)

			state_model.process = process = subprocess.Popen(
				cwd=os.getcwd(),
				shell=True, text=True, args=' '.join([str(x) for x in command]),
				# start_new_session=True,  # Daemonizes process, the same as preexec_fn=os.setsid
				bufsize=1,
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
			)

			def read_stdout():
				for line in (x.rstrip() for x in iter(process.stdout.readline, '')):
					try:
						print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), line, file=sys.stdout); sys.stdout.flush()
					except Exception as e:
						print('Exception in thread:', file=sys.stderr); sys.stderr.flush()
						print(e, file=sys.stderr); sys.stderr.flush()
				logging.getLogger(__name__).info('Subprocess stdout loop is closed')
			stdout_thread = threading.Thread(target=read_stdout)
			stdout_thread.daemon = True
			stdout_thread.start()

			def read_stderr():
				for line in (x.rstrip() for x in iter(process.stderr.readline, '')):
					try:
						if line.startswith('Status='):
							value = line.split('=', 1)[1]
							if value.startswith('{'):
								status = ast.literal_eval(value)
								logging.getLogger(__name__).warning('status["index"]=' + '%s', status["index"])
								entry = tree.topLevelItem(int(status['index']))
								if entry is not None:
									if status.get('code', False):
										entry.setText(0, '???' if status['code'] == 'current' else '')
										entry.setForeground(1, QtGui.QBrush(QtGui.QColor(self._state_colors[status['code']])))
										entry.setBackground(2, QtGui.QBrush(QtGui.QColor(self._state_colors[status['code']])))
										entry.setBackground(3, QtGui.QBrush(QtGui.QColor(self._state_colors[status['code']])))
									tree.scrollToItem(entry, tree.EnsureVisible)
								tree.viewport().update()  # Force update (fix for Qt5)
						elif '[DEBUG]  ' in line:
							logging.getLogger(__name__).debug(line)
						elif '[INFO]  ' in line:
							logging.getLogger(__name__).info(line)
						else:
							logging.getLogger(__name__).error(line)
					except Exception as e:
						print('Exception in thread:', file=sys.stderr); sys.stderr.flush()
						print(e, file=sys.stderr); sys.stderr.flush()
				logging.getLogger(__name__).info('Subprocess stderr loop is closed')
			stderr_thread = threading.Thread(target=read_stderr)
			stderr_thread.daemon = True
			stderr_thread.start()

			# Keeps last line index
			with self._with_data() as lines:
				previous_index = len(lines)

			def check_if_alive():
				with self._with_status('Press "Insert" or "Break" to create new event, press "Pause" to terminate event capturing.'):
					process.wait()  # Do not use communicate() - conflicts with threads for stdout/stderr
				exit_code = process.returncode
				logging.getLogger(__name__).info('Subprocess is terminated with exit code %s', exit_code)
				state_model.process = None

				# Moves new lines to selection
				indices = set([x.row() for x in tree.selectedIndexes()])
				if indices:
					to_index = max(indices)
					with self._with_data() as lines:
						new_index = len(lines)
						to_event = self._restore(lines[to_index])

					# Checks if new lines appeared
					count = new_index - previous_index
					if count > 0:
						# Shifts them as selection
						self._shift(indices=range(previous_index, new_index), count=to_event['level'])
						# Moves them after selection
						self._move(from_index=previous_index, to_index=to_index + 1, count=count)
			is_alive_thread = threading.Thread(target=check_if_alive)
			is_alive_thread.daemon = True
			is_alive_thread.start()

	@contextlib.contextmanager
	def _with_status(self, message):
		state_model = self._state_model

		state_model.status, previous_message = message, state_model.status
		yield
		state_model.status = previous_message

	def _delete(self, index, count):
		with self._with_data() as lines:
			# Removes lines
			lines[index:(index + count or None)] = []

	def _move(self, from_index, to_index, count):
		view = self.__view
		tree = view.commands_tree

		with self._with_data() as lines:
			# Relocates lines
			cut, lines[from_index:(from_index + count or None)] = lines[from_index:(from_index + count or None)], []
			lines[to_index:to_index] = cut

		entry = tree.topLevelItem(to_index)
		tree.scrollToItem(entry, tree.EnsureVisible)
		# tree.viewport().update()  # Force update (fix for Qt5)
		entry.setSelected(True)

	def _edit(self, index):
		state_model = self._state_model

		try:
			with self._with_data() as lines:
				previous_event = self._restore(lines[index])

				# Creates
				event = self._create(
					template=previous_event,
					with_exceptions=True,
				)

				lines[index] = self._dump(event)
		except subprocess.CalledProcessError:
			pass

	def _shift(self, indices, count):
		with self._with_data() as lines:
			# Shifts/unshifts lines
			for index in indices:
				line = lines[index]
				lines[index] = max(0, len(line) - len(line.lstrip()) + count) * '\t' + line.lstrip()

	def _comment(self, indices, comment=True):
		with self._with_data() as lines:
			# Comments/uncomments lines
			for index in indices:
				line = lines[index]
				if line.lstrip():
					lines[index] = max(0, len(line) - len(line.lstrip())) * '\t' + ('# ' if comment and line.lstrip()[:1] != '#' else '') + (line.lstrip() if comment or line.lstrip()[:3] != '# {' else line.lstrip().lstrip('# '))

	def _join(self, indices):
		with self._with_data() as lines:
			if indices:
				# Combines values
				dst_event = dict()
				for src_event in [self._restore(lines[index]) for index in sorted(indices)]:
					for key, value in list(src_event.items()):
						if value.__class__ == list:
							dst_event.setdefault(key, []).extend(value)
						else:
							dst_event.setdefault(key, value)

				# Replaces first line
				lines[min(indices)] = self._dump(dst_event)

				# Removes other lines
				for index in reversed(sorted(indices - set([min(indices)]))):
					del lines[index]

	def _split(self, indices):
		with self._with_data() as lines:
			if indices:
				for index in indices:
					src_event = self._restore(lines[index])

					# Splits event
					dst_events = [dict(src_event, **(dict(patterns=[x]) if x is not None else dict())) for x in src_event.get('patterns', [None])]

					# Replaces previous event with new events
					lines[index:(index + 1)] = [self._dump(x) for x in dst_events]

	def _open_gimp(self, indices):
		with self._with_data() as lines:
			if indices:
				events = [self._restore(lines[index]) for index in sorted(indices)]
				patterns = [xx for x in events for xx in x.get('patterns', [])]
				if patterns:
					command = 'gimp ' + ' '.join(pipes.quote(x) for x in patterns)
					subprocess.check_output(command, shell=True, text=True)

	@staticmethod
	def __load_pixmap(path):
		pixmap = QtGui.QPixmap()
		if not pixmap.load(path):
			raise Exception('Exception during loading pixmap from "{path}"'.format(**locals()))
		return pixmap


def run_init():
	"""Shows Qt GUI."""
	import argparse
	parser = argparse.ArgumentParser(description=__doc__)
	# parser.add_argument('-p', '--path', required=bool(sys.stdin.isatty()), help='Directory path where to load tests')
	parser.add_argument('-p', '--path', help='Directory path where to load tests')
	parser.add_argument('-v', '--verbose', action='count', help='Raises logging level')
	parser.add_argument('-g', '--geometry', help='Sets window geometry (position and size). Format: <width>x<height>[+-]<x>[+-]<y>.')
	parser.add_argument('-a', '--autorun', action='store_true', help='Starts test automatically after launch')
	parser.add_argument('-s', '--autostop', action='store_true', help='Stops automatically if test terminates with a failure, prevents exit')
	parser.add_argument('-e', '--autoexit', action='store_true', help='Exits automatically if test terminates')
	parser.add_argument('-c', '--with-close-on-escape', action='store_true', help='Allows close if ESC key pressed')
	parser.add_argument('-r', '--with-screencast', action='store_true', help='Writes a video screencast')
	parser.add_argument('-d', '--with-observer', action='store_true', default=True, help='Enables observing data for external updates and reloading them')
	parser.add_argument('--shell-command-prefix', default='', help='Adds prefix to every event named "shell_command"')
	parser.add_argument('PATH', nargs='?', help='Directory path where to load tests')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong
	kwargs['path'] = next((x for x in [kwargs['path']] + [kwargs.pop('PATH')] if x is not None), None)  # Mixes positional argument "PATH" into named argument "path"

	sys.exit(MainController(**kwargs).loop())


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
