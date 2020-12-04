#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann


import ast
import logging
import os
import signal
import subprocess
import sys
import threading
import watchdog.events
import watchdog.observers

import wx
import wx.lib.agw.hypertreelist
import wx.lib.mixins.inspection

if __name__ == '__main__':
	# Sets utf-8 (instead of latin1) as default encoding for every IO
	# import importlib; importlib.reload(sys); sys.setdefaultencoding('utf-8')
	# Runs in application's working directory
	sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)) + '/..')
	os.chdir(sys.path[0])
	# Working interruption by Ctrl-C
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configures logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(logging.DEBUG)

from helpers.caller import Caller
from models.abstract import ObservableAttrDict

__doc__ = """"""


class _TreeItemImage(wx.StaticBitmap):
	def __init__(self, parent, item, path, scale=None):
		# self._parent = parent
		# self._tree_item = item
		image = wx.Image(path, wx.BITMAP_TYPE_ANY)
		if scale is not None:
			image = image.Scale(image.GetWidth() * scale[0], image.GetHeight() * scale[1], wx.IMAGE_QUALITY_HIGH)
		bitmap = image.ConvertToBitmap()

		wx.StaticBitmap.__init__(self, parent, bitmap=bitmap)

		# self.Bind(wx.EVT_PAINT, self.__on_painting)

	def __del__(self):
		sys.stderr.write('.'); sys.stderr.flush()  # FIXME: must be removed/commented

	# def __on_painting(self, event):
	#     is_visible = self._parent.IsItemVisible(self._tree_item)
	#     print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), is_visible, self._tree_item.GetText(0); sys.stderr.flush()  # FIXME: must be removed/commented
	#     # if is_visible:
	#     if 1:
	#         dc = wx.PaintDC(self)

	#         # dc.SetClippingRegion(0, 0, 40, 40)

	#         dc.SetBackground(wx.Brush('WHITE'))
	#         dc.Clear()
	#         dc.DrawBitmap(self._bitmap, x=0, y=0, useMask=False)

	#         # dc.DestroyClippingRegion()

	# def GetPosition(self):
	#     pos = super(_TreeItemImage, self).GetPosition()
	#     pos = (400, 200)
	#     return pos


class _TreeItemImages(wx.StaticBitmap):
	def __init__(self, parent, item, paths, scale=None, border=0, border_color='RED', background_color='BLACK'):
		bitmaps = []
		for path in paths:
			image = wx.Image(path, wx.BITMAP_TYPE_ANY)
			if scale is not None:
				image = image.Scale(image.GetWidth() * scale[0], image.GetHeight() * scale[1], wx.IMAGE_QUALITY_HIGH)
			bitmap = image.ConvertToBitmap()
			bitmaps.append(bitmap)

		width, height = sum(x.GetWidth() + (1 + len(bitmaps)) * border for x in bitmaps), max(x.GetHeight() + 2 * border for x in bitmaps)
		canvas_bitmap = wx.EmptyBitmap(width, height)
		dc = wx.MemoryDC()
		dc.SelectObject(canvas_bitmap)

		if border:
			dc.SetPen(wx.Pen('WHITE', style=wx.TRANSPARENT))
			dc.SetBrush(wx.Brush(border_color))
			dc.DrawRectangle(0, 0, width, height)
			dc.SetBrush(wx.Brush(background_color))
			dc.DrawRectangle(border, border, width - 2 * border, height - 2 * border)

		x_offset, y_offset = border, border
		for bitmap in bitmaps:
			dc.DrawBitmap(bitmap, x_offset, y_offset, False)
			x_offset += bitmap.GetWidth() + border
		dc.SelectObject(wx.NullBitmap)

		wx.StaticBitmap.__init__(self, parent, bitmap=canvas_bitmap)

	def __del__(self):
		sys.stderr.write('.'); sys.stderr.flush()  # FIXME: must be removed/commented


class _State(ObservableAttrDict):
	pass


class WxGuiController(object):
	""""""

	def __init__(self, path):
		# self._cwd = './'

		# Models
		""" Current-State-Model for selected view's data"""
		# self._settings_model = settings_model

		self._state_model = state_model = _State()
		state_model.src_path = path
		state_model.process = None
		state_model.src_path_events_observer = None

		self._tree_items_to_lines = dict()

		# Creates testable window (shortcut is Ctrl+Alt+I)
		self._app = app = wx.lib.mixins.inspection.InspectableApp()

		self._window = window = wx.Dialog(
			parent=None,
			title="PyGUIBot",
			pos=((wx.Display().GetGeometry().width - 350), 23),
			size=(350, wx.Display().GetGeometry().height - 23),
			style=(
				wx.RESIZE_BORDER |
				0
			),
		)
		window.SetSizer(wx.BoxSizer(wx.VERTICAL))
		app.SetTopWindow(window)

		if True:  # Extra indent for sub-widgets
			frame = wx.Panel(window)
			frame.SetSizer(wx.BoxSizer(wx.VERTICAL))
			window.GetSizer().Add(frame, proportion=1, flag=wx.LEFT | wx.TOP | wx.RIGHT | wx.EXPAND, border=5)

			if True:  # Extra indent for sub-widgets
				self._tree = tree = wx.lib.agw.hypertreelist.HyperTreeList(parent=frame, agwStyle=(
					# wx.lib.agw.hypertreelist.TR_NO_BUTTONS |  # For convenience to document that no buttons are to be drawn.
					# wx.lib.agw.hypertreelist.TR_SINGLE |  # For convenience to document that only one item may be selected at a time. Selecting another item causes the current selection, if any, to be deselected. This is the default.
					# wx.lib.agw.hypertreelist.TR_HAS_BUTTONS |  # Use this style to show + and - buttons to the left of parent items.
					# wx.lib.agw.hypertreelist.TR_NO_LINES |  # Use this style to hide vertical level connectors.
					# wx.lib.agw.hypertreelist.TR_LINES_AT_ROOT |  # Use this style to show lines between root nodes. Only applicable if TR_HIDE_ROOT is set and TR_NO_LINES is not set.
					# wx.TR_DEFAULT_STYLE |  # The set of flags that are closest to the defaults for the native control for a particular toolkit.
					# wx.lib.agw.hypertreelist.TR_TWIST_BUTTONS |  # Use old Mac-twist style buttons.
					wx.lib.agw.hypertreelist.TR_MULTIPLE |  # Use this style to allow a range of items to be selected. If a second range is selected, the current range, if any, is deselected.
					# wx.lib.agw.hypertreelist.TR_EXTENDED |  # Use this style to allow disjoint items to be selected. (Only partially implemented; may not work in all cases).
					wx.lib.agw.hypertreelist.TR_HAS_VARIABLE_ROW_HEIGHT |  # Use this style to cause row heights to be just big enough to fit the content. If not set, all rows use the largest row height. The default is that this flag is unset.
					# wx.lib.agw.hypertreelist.TR_EDIT_LABELS |  # Use this style if you wish the user to be able to edit labels in the tree control.
					wx.lib.agw.hypertreelist.TR_ROW_LINES |  # Use this style to draw a contrasting border between displayed rows.
					wx.lib.agw.hypertreelist.TR_HIDE_ROOT |  # Use this style to suppress the display of the root node, effectively causing the first-level nodes to appear as a series of root nodes.
					wx.lib.agw.hypertreelist.TR_COLUMN_LINES |  # Use this style to draw a contrasting border between displayed columns.
					wx.lib.agw.hypertreelist.TR_FULL_ROW_HIGHLIGHT |  # Use this style to have the background colour and the selection highlight extend  over the entire horizontal row of the tree control window.
					# wx.lib.agw.hypertreelist.TR_AUTO_CHECK_CHILD |  # Only meaningful foe checkbox-type items: when a parent item is checked/unchecked its children are checked/unchecked as well.
					# wx.lib.agw.hypertreelist.TR_AUTO_TOGGLE_CHILD |  # Only meaningful foe checkbox-type items: when a parent item is checked/unchecked its children are toggled accordingly.
					# wx.lib.agw.hypertreelist.TR_AUTO_CHECK_PARENT |  # Only meaningful foe checkbox-type items: when a child item is checked/unchecked its parent item is checked/unchecked as well.
					wx.lib.agw.hypertreelist.TR_ALIGN_WINDOWS |  # Flag used to align windows (in items with windows) at the same horizontal position.
					wx.lib.agw.hypertreelist.TR_NO_HEADER |  # Use this style to hide the columns header.
					# wx.lib.agw.hypertreelist.TR_ELLIPSIZE_LONG_ITEMS |  # Flag used to ellipsize long items when the horizontal space for :class:`HyperTreeList` columns is low.
					# wx.lib.agw.hypertreelist.TR_VIRTUAL |  # :class:`HyperTreeList` will have virtual behaviour.
					0
				))
				tree.AddColumn(text='State', width=200)
				tree.AddColumn(text='Event', width=200)
				tree.AddColumn(text='Options', width=200)
				tree.SetMainColumn(0)
				# tree.SetFocusIgnoringChildren()
				self._tree_root = tree.AddRoot('Root entry')
				self._dragging_item = None
				# tree.Bind(wx.EVT_TREE_BEGIN_DRAG, self.__on_tree_dragging)
				# tree.Bind(wx.EVT_TREE_END_DRAG, self.__on_tree_dragged)
				frame.GetSizer().Add(tree, 1, wx.LEFT | wx.TOP | wx.RIGHT | wx.EXPAND, 5)

				# Loads icons
				self._tree_icons, _images = dict(), wx.ImageList(16, 16)
				for index, (name, path) in enumerate([(os.path.splitext(x)[0], os.path.join('images/16', x)) for x in os.listdir('images/16') if x.endswith('.png')]):
					self._tree_icons[name] = index
					image = wx.Image(path, wx.BITMAP_TYPE_ANY)
					image_bitmap = image.ConvertToBitmap()
					_images.Add(image_bitmap)
				tree.AssignImageList(_images)

			self._toolbar = toolbar = wx.ToolBar(parent=window, style=(
				# wx.TB_TEXT |  #
				0
			))
			toolbar.SetToolBitmapSize((32, 32))

			window.GetSizer().Add(toolbar, proportion=0, flag=wx.LEFT | wx.TOP | wx.RIGHT | wx.EXPAND, border=5)
			self._toolbar_tools = dict()
			if True:  # Extra indent for sub-widgets
				for index, kwargs in enumerate((
					dict(
						key='run', image='images/32/run.png',
						entry=dict(label="Run", shortHelp="Runs execution", longHelp=""),
						on_clicked=self.__on_toolbar_run_clicked,
					),
					dict(
						key='stop', image='images/32/stop.png',
						entry=dict(label="Stop", shortHelp="Stops execution", longHelp=""),
						on_clicked=self.__on_toolbar_stop_clicked,
					),
					dict(
						key='record', image='images/32/record.png',
						entry=dict(label="Record", shortHelp="Records execution", longHelp=""),
						on_clicked=self.__on_toolbar_record_clicked,
					),
					dict(
						key='move_up', image='images/32/active.png',
						entry=dict(label="Move up", shortHelp="Moves item up", longHelp=""),
						on_clicked=self.__on_toolbar_move_up_clicked,
					),
					dict(
						key='move_down', image='images/32/active.png',
						entry=dict(label="Move down", shortHelp="Moves item down", longHelp=""),
						on_clicked=self.__on_toolbar_move_down_clicked,
					),
					dict(
						key='move_left', image='images/32/active.png',
						entry=dict(label="Move left", shortHelp="Moves item left", longHelp=""),
						on_clicked=self.__on_toolbar_move_left_clicked,
					),
					dict(
						key='move_right', image='images/32/active.png',
						entry=dict(label="Move right", shortHelp="Moves item right", longHelp=""),
						on_clicked=self.__on_toolbar_move_right_clicked,
					),
				)):
					self._toolbar_tools[kwargs['key']] = index
					toolbar.AddLabelTool(id=index, bitmap=self._load_bitmap(path=kwargs['image']), **kwargs['entry'])
					toolbar.Bind(wx.EVT_TOOL, kwargs['on_clicked'], id=index)
					# toolbar.Bind(wx.EVT_TOOL_RCLICKED, kwargs['on_clicked'], id=index)

			modal_buttons_frame = wx.Panel(parent=window)
			modal_buttons_frame.SetSizer(wx.BoxSizer(wx.HORIZONTAL))
			window.GetSizer().Add(modal_buttons_frame, proportion=0, flag=wx.ALL | wx.EXPAND, border=5)
			if True:  # Extra indent for sub-widgets
				modal_buttons_frame.GetSizer().AddSpacer((0, 0), 1, wx.EXPAND, 0)

				button = wx.Button(parent=modal_buttons_frame, id=wx.ID_CANCEL)
				modal_buttons_frame.GetSizer().Add(button, proportion=0, flag=wx.LEFT, border=5)

				button = wx.Button(parent=modal_buttons_frame, id=wx.ID_OK)
				modal_buttons_frame.GetSizer().Add(button, proportion=0, flag=wx.LEFT, border=5)
				button.SetDefault()

		# frame.Layout()

		""" Observe models by view """
		# settings_model.changed.bind(self._on_model_updated)
		state_model.changed.bind(self._on_model_updated)

		""" Fill blank view by models """
		# self._on_model_updated(settings_model)
		self._on_model_updated(state_model)

	""" Model's event handlers """

	def _on_model_updated(self, model=None, previous=None, current=None):
		# logging.getLogger(__name__).debug(self.__class__, object.__repr__(model), previous and str(previous)[:80], current and str(current)[:80])

		# settings_model = self._settings_model
		state_model = self._state_model

		# if model is settings_model:
		#     if current is None or 'cards_vertical_rows_count' in current:
		#         if settings_model.cards_vertical_columns_count * settings_model.cards_vertical_rows_count != len(self.fields):
		#             Caller.call_once_after(0, self._fill)

		if model is state_model:
			if current is None or 'src_path' in current:
				Caller.call_once_after(0, self._fill, './{}/events.log'.format(state_model.src_path))

			if current is None or 'process' in current:
				# Toggles run and stop buttons
				self._toolbar.EnableTool(id=self._toolbar_tools['run'], enable=(state_model.process is None))
				self._toolbar.EnableTool(id=self._toolbar_tools['stop'], enable=(state_model.process is not None))
				self._toolbar.EnableTool(id=self._toolbar_tools['record'], enable=(state_model.process is None))

	"""View's event handlers"""

	# def __on_tree_dragging(self, event):
	#     if self._dragging_item is None:
	#         self._dragging_item = event.event_item
	#         event.Allow()
	#         print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'event=', event; sys.stderr.flush()  # FIXME: must be removed/commented

	# def __on_tree_dragged(self, event):
	#     print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'event=', event; sys.stderr.flush()  # FIXME: must be removed/commented

	def __on_toolbar_run_clicked(self, event):
		self._run()

	def __on_toolbar_stop_clicked(self, event):
		self._stop()

	def __on_toolbar_record_clicked(self, event):
		self._record()

	def __on_toolbar_move_up_clicked(self, event):
		self._move_selected('up')

	def __on_toolbar_move_down_clicked(self, event):
		self._move_selected('down')

	def __on_toolbar_move_left_clicked(self, event):
		self._move_selected('left')

	def __on_toolbar_move_right_clicked(self, event):
		self._move_selected('right')

	"""Helpers"""

	def loop(self):
		self._window.ShowModal()
		# self._app.MainLoop()

	def _load_bitmap(self, id=None, path=None):
		"""Loads image from wx-ID or path, returns bitmap"""
		if id is not None:
			bitmap = wx.ArtProvider.GetBitmap(id, wx.ART_TOOLBAR, toolbar.GetToolBitmapSize())
		elif path is not None:
			bitmap = wx.Image(path, wx.BITMAP_TYPE_ANY).ConvertToBitmap()
		return bitmap

	def _move_selected(self, direction):
		tree = self._tree
		tree_root = self._tree_root

		selected_indices = [tree_root.GetChildren().index(x) for x in tree.GetSelections()]
		print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'selected_indices=', selected_indices, file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented
		print('{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'direction=', direction, file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed/commented
		# # from_line, to_line = min(selected_indices or [None]), max(selected_indices or [None])

	def _fill(self, src_path):
		state_model = self._state_model
		tree = self._tree
		tree_root = self._tree_root

		max_level = 0

		self._tree_items_to_lines.clear()

		tree.Freeze()
		tree.DeleteChildren(tree_root)
		with open(src_path) as src:
			for line in (x.rstrip() for x in src):
				level = (len(line) - len(line.lstrip()))
				max_level = max(max_level, level)

				event = ast.literal_eval(line.lstrip()) if line.lstrip().startswith('{') else dict(comments=line)

				view = tree.AppendItem(parentId=tree_root, text='')

				tree.SetItemText(item=view, column=0, text='')
				tree.SetItemText(item=view, column=1, text='')
				if 'type' not in event:  # If line is commented
					tree.SetItemText(item=view, column=1, text='\t' * level + event.get('type', ''))
				else:
					if event['type'].startswith('keyboard_'):
						filename = 'keyboard'
					elif event['type'].startswith('mouse_'):
						filename = 'mouse'
					elif event['type'].endswith('_command'):
						filename = 'command'
					else:
						filename = 'unknown'

					tree.SetItemText(item=view, column=0, text='\t' * (len(line) - len(line.lstrip())))

					path = os.path.join('images/16', filename + '.png')
					view_widget = _TreeItemImage(parent=tree, item=view, path=path)
					tree.SetItemWindow(item=view, window=view_widget, column=0)

					tree.SetItemText(item=view, column=1, text=event['type'].replace(filename, '').strip('_'))

				tree.SetItemText(item=view, column=2, text='')
				if 'value' in event:
					tree.SetItemText(item=view, column=2, text=('"' + event['value'] + '"'))

				if 'comments' in event:
					tree.SetItemText(item=view, column=2, text=view.GetText(2) + (view.GetText(2) and ', ') + event['comments'])

				if event is not None and 'patterns' in event:
					tree.SetItemText(item=view, column=2, text=view.GetText(2) + (view.GetText(2) and ', '))

					paths = [os.path.join(os.path.dirname(src_path), x) for x in event['patterns']]
					view_widget = _TreeItemImages(parent=tree, item=view, paths=paths, scale=(.75, 1.), border=1, background_color='GRAY')
					tree.SetItemWindow(item=view, window=view_widget, column=2)

				self._tree_items_to_lines[view] = line

		self._reset_tree_icons()

		# Auto-resizes columns to content
		tree.SetColumnWidth(0, tree.GetMainWindow().GetBestColumnWidth(0))
		tree.SetColumnWidth(1, tree.GetMainWindow().GetBestColumnWidth(1))
		tree.SetColumnWidth(2, tree.GetMainWindow().GetBestColumnWidth(2))

		# Updates widget (items positions, etc)
		tree.GetMainWindow().OnInternalIdle()
		# tree.GetMainWindow().CalculatePositions()
		# self.Refresh()
		# self.AdjustMyScrollbars()

		tree.Thaw()

		# Handles filesystem events in data directory
		if state_model.src_path_events_observer is not None:
			state_model.src_path_events_observer.stop()

		state_model.src_path_events_observer = observer_thread = watchdog.observers.Observer()
		handler = watchdog.events.PatternMatchingEventHandler()

		def on_modified(event):
			if event.src_path == src_path:
				Caller.call_once_after(.1, self._fill, src_path)
		handler.on_modified = on_modified
		observer_thread.schedule(handler, path=os.path.dirname(src_path))
		observer_thread.start()

	def _reset_tree_icons(self):
		tree = self._tree
		tree_icons = self._tree_icons

		for line_view in self._tree_root.GetChildren():
			line = self._tree_items_to_lines[line_view]
			line = line.lstrip()
			tree.SetItemImage(item=line_view, image=tree_icons['commented' if not line or line.startswith('#') else 'pending'])

	def _run(self):
		state_model = self._state_model

		if state_model.process is None:
			tree = self._tree
			tree_root = self._tree_root

			# Gets selected from and to lines
			selected_indices = [tree_root.GetChildren().index(x) for x in tree.GetSelections()]
			from_line, to_line = min(selected_indices or [None]), max(selected_indices or [None])
			to_line = None if from_line == to_line else to_line

			# Resets icons
			self._reset_tree_icons()

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
							line_view = tree_root.GetChildren()[int(status['index'])]
							tree.SetItemImage(
								item=line_view,
								image=self._tree_icons[status['code']],
							)
							tree.EnsureVisible(line_view)
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
					if '[INFO]  Status=' in line:
						status = ast.literal_eval(line.split('=', 1)[1])
						line_view = tree_root.GetChildren()[status['index']]
						tree.SetItemImage(
							item=line_view,
							image=self._tree_icons[status['code']],
						)
						tree.EnsureVisible(line_view)
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


def test_wx_gui_controller():
	WxGuiController()


def run_wx_gui_controller():
	import argparse
	parser = argparse.ArgumentParser(description='Restores mouse and keyboard events from storage.')
	parser.add_argument('path', nargs='?', default='data', help='Directory path where to load the data (default "data")')
	kwargs = vars(parser.parse_args())  # Breaks here if something goes wrong

	WxGuiController(**kwargs).loop()


def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--run-function', help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	globals()['run_' + (kwargs['run_function'] or 'wx_gui_controller')]()

if __name__ == '__main__':
	main()
