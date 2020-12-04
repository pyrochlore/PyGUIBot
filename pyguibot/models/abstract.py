#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python3" "-B" "$0" "$@"
# (c) gehrmann



__doc__ = """
This module provides some basic abstract models
"""

import ast
from collections import defaultdict
from colorama import (
	Fore as FG,
	Back as BG,
	Style as ST,
)
import datetime
import logging
import os
import re
import signal
import sys
import time
import weakref

if __name__ == '__main__':
	# Sets utf-8 (instead of latin1) as default encoding for every IO
	# import importlib; importlib.reload(sys); sys.setdefaultencoding('utf-8')
	# Runs in application's working directory
	os.chdir((os.path.dirname(os.path.realpath(__file__)) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))
	# Working interruption by Ctrl-C
	signal.signal(signal.SIGINT, signal.default_int_handler)
	# Configures logging
	logging.basicConfig(
		level=logging.WARN, datefmt='%H:%M:%S',
		format='%(asctime)s.%(msecs)03d %(pathname)s:%(lineno)d [%(levelname)s]  %(message)s',
	)
logging.getLogger(__name__).setLevel(getattr(logging, os.environ.get('LOGGING_' + __name__.replace('.', '_').upper(), 'WARNING')))

from helpers.observable import Observable


class AttrDict(dict):
	"""Same as the dict, but values are through "." (as attributes) accessible"""

	__getattr__ = dict.__getitem__
	__setattr__ = dict.__setitem__
	__delattr__ = dict.__delitem__

	def __getstate__(self):
		return self.__dict__

	# def __missing__(self, key):
	#     import sys; print >>sys.stderr, "key:", key; sys.stdout.flush()  # FIXME: must be removed
	#     setattr(self, key, AttrDict())
	#     return getattr(self, key)


class _NestedObservablesMixin(object):
	def __init__(self):
		self.__dict__['_items_to_callbacks_to_unbind'] = {}  # Hides from repr and __setattr__/__setitem__

	def _unbind_changed(self, values):
		"""Unbinds changed-event if values-item is instance of Observable*, returns values.

		Needed to unbind bound changed-events of item (from values) if it is being removed from item-holder (self).
		"""
		for value in (list(values.values()) if isinstance(self, ObservableAttrDict) else values):
			if isinstance(value, (ObservableAttrDict, ObservableList, ObservableSet)):
				value.changed.unbind(self._items_to_callbacks_to_unbind.pop(id(value)))
		return values

	def __repr__(self):
		return object.__repr__(self)


class ObservableAttrDict(AttrDict, _NestedObservablesMixin):
	"""AttrDict, which implements pattern Observer-Observable"""

	@Observable
	@classmethod
	def changed(cls, item=None, previous=(None, ), current=(None, )):
		"""Bind to it to receive 'changed'-events: (object.changed.bind(handler)), call it to send 'changed'-event"""

	def __init__(self, *args, **kwargs):
		_NestedObservablesMixin.__init__(self)
		super(ObservableAttrDict, self).__init__(*args, **kwargs)

		previous, current = (self._unbind_changed({k: None for k in kwargs}), ), (self._bind_changed({k: v for k, v in list(kwargs.items())}), )
		self.changed(self, previous=previous, current=current)

	def __hash__(self):
		return id(self)
		# return hash(frozenset((repr(x) for x in self.items())))

	def __setitem__(self, key, value):
		# Checks if there is a property with the same name -> calls it's setter
		if key.__class__ == str and hasattr(self.__class__, key) and getattr(self.__class__, key).__class__ is property:
			previous = (self._unbind_changed({key: getattr(self.__class__, key).fget(self)}), )
			getattr(self.__class__, key).fset(self, value)  # Call property's setter
			current = (self._bind_changed({key: getattr(self.__class__, key).fget(self)}), )
			self.changed(self, previous=previous, current=current)

		elif key not in self or self[key] != value:
			previous, current = (self._unbind_changed({key: self.get(key, None)}), ), (self._bind_changed({key: value}), )
			super(ObservableAttrDict, self).__setitem__(key, value)
			self.changed(self, previous=previous, current=current)

	__setattr__ = __setitem__

	def __delitem__(self, key):
		previous, current = (self._unbind_changed({key: self.get(key, None)}), ), (self._bind_changed({key: None}), )
		super(ObservableAttrDict, self).__delitem__(key)
		self.changed(self, previous=previous, current=current)

	__delattr__ = __delitem__

	def clear(self):
		previous, current = (self._unbind_changed({k: v for k, v in list(self.items())}), ), (self._bind_changed({k: None for k in self}), )
		super(ObservableAttrDict, self).clear()
		if current:
			self.changed(self, previous=previous, current=current)

	def pop(self, key, *args):
		previous, current = (self._unbind_changed({key: self.get(key, None)}), ), (self._bind_changed({key: None}), )
		value = super(ObservableAttrDict, self).pop(key, *args)
		if previous != current:
			self.changed(self, previous=previous, current=current)
		return value

	def popitem(self):
		key, value = item = super(ObservableAttrDict, self).popitem()
		previous, current = (self._unbind_changed({key: value}), ), (self._bind_changed({key: None}), )
		self.changed(self, previous=previous, current=current)
		return item

	def setdefault(self, key, *args):
		"""Dict.setdefault with lazy-calculated default value"""

		previous = (self._unbind_changed({key: self.get(key, None)}), )
		value = super(ObservableAttrDict, self).setdefault(key, *([x() for x in args] if key not in self and len(args) > 0 and callable(args[0]) else args))
		current = (self._bind_changed({key: value}), )
		if previous != current:
			self.changed(self, previous=previous, current=current)
		return value

	def update(self, items, **kwargs):
		kwargs.update(dict(items))

		updated_keys = {k for k, v in list(kwargs.items()) if k not in self or self[k] != v}
		if updated_keys:
			previous = (self._unbind_changed({k: self.get(k, None) for k in updated_keys}), )
			super(ObservableAttrDict, self).update(kwargs)
			current = (self._bind_changed({k: self[k] for k in updated_keys}), )
			self.changed(self, previous=previous, current=current)

	"""Helpers"""

	def _bind_changed(self, values):
		"""Binds changed-event if values-item is instance of Observable*, returns values.

		Needed to provide changed-events of item (from values) up to item-holder (self).
		"""
		for key, value in list(values.items()):
			if isinstance(value, (ObservableAttrDict, ObservableList, ObservableSet)):
				value.changed.bind(self._items_to_callbacks_to_unbind.setdefault(id(value), (lambda key, value: lambda model=None, previous=(None, ), current=(None, ): (
					self.changed(self, previous=({key: value}, ) + previous, current=({key: value}, ) + current)
				))(key, value)))  # invoke parent's changed-event if is changed
				# def _get_callback(key, value):
				#     def _callback(model=None, previous=(None, ), current=(None, )):
				#         return self.changed(self, previous=({key: value}, ) + previous, current=({key: value}, ) + current)
				#     return _callback
				# value.changed.bind(self._items_to_callbacks_to_unbind.setdefault(id(value), _get_callback(key, value)))  # invoke parent's changed-event if is changed

		return values


class ObservableList(list, _NestedObservablesMixin):
	"""List, which implements pattern Observer-Observable"""

	@Observable
	@classmethod
	def changed(cls, item=None, previous=(None, ), current=(None, )):
		"""Bind to it to receive 'changed'-events: (object.changed.bind(handler)), call it to send 'changed'-event"""

	def __init__(self, *args):
		_NestedObservablesMixin.__init__(self)
		super(ObservableList, self).__init__(*args)
		if super(ObservableList, self).__len__():  # Prevents from calling reloaded method
			previous, current = (self._unbind_changed({(0, 0): []}), ), (self._bind_changed({(0, len(self)): list(self)}), )
			self.changed(self, previous=previous, current=current)

	def __hash__(self):
		return id(self)
		# return hash(repr(self))

	def __setitem__(self, index, value):
		if len(self) <= index or self[index] != value:
			previous = (self._unbind_changed({(index, index + 1): [self[index]]}), )
			super(ObservableList, self).__setitem__(index, value)
			current = (self._bind_changed({(index, index + 1): [self[index]]}), )
			self.changed(self, previous=previous, current=current)

	def __delitem__(self, index):
		previous = (self._unbind_changed({(index, index + 1): [self[index]]}), )
		super(ObservableList, self).__delitem__(index)
		current = (self._bind_changed({(index, index): []}), )
		self.changed(self, previous=previous, current=current)

	def __setslice__(self, from_index, to_index, values):
		to_index = min(to_index, len(self))  # to_index for [:] is a very big number
		previous = (self._unbind_changed({(from_index, to_index): self[from_index:to_index]}), )
		super(ObservableList, self).__setslice__(from_index, to_index, values)
		current = (self._bind_changed({(from_index, from_index + len(values)): values}), )
		self.changed(self, previous=previous, current=current)

	def __delslice__(self, from_index, to_index):
		previous = (self._unbind_changed({(from_index, to_index): self[from_index:to_index]}), )
		super(ObservableList, self).__delslice__(from_index, to_index)
		current = (self._bind_changed({(from_index, from_index): []}), )
		self.changed(self, previous=previous, current=current)

	def __iadd__(self, values):
		previous, current = (self._unbind_changed({(len(self), len(self)): []}), ), (self._bind_changed({(len(self), len(self) + len(values)): values}), )
		super(ObservableList, self).__iadd__(values)
		self.changed(self, previous=previous, current=current)
		return self

	def __imul__(self, count):
		if count != 1:
			if count < 1:
				previous, current = (self._unbind_changed({(0, len(self)): self[:]}), ), (self._bind_changed({(0, 0): []}), )
			else:
				previous, current = (self._unbind_changed({(len(self), len(self)): []}), ), (self._bind_changed({(len(self), len(self) * (count)): self[:] * (count - 1)}), )
			super(ObservableList, self).__imul__(count)
			self.changed(self, previous=previous, current=current)
		return self

	def append(self, value):
		super(ObservableList, self).append(value)
		previous, current = (self._unbind_changed({(len(self) - 1, len(self) - 1): []}), ), (self._bind_changed({(len(self) - 1, len(self)): [value]}), )
		self.changed(self, previous=previous, current=current)

	def insert(self, index, value):
		super(ObservableList, self).insert(index, value)
		index = min(index, len(self) - 1)
		previous, current = (self._unbind_changed({(index, index): []}), ), (self._bind_changed({(index, index + 1): [value]}), )
		self.changed(self, previous=previous, current=current)

	def extend(self, values):
		previous, current = (self._unbind_changed({(len(self), len(self)): []}), ), (self._bind_changed({(len(self), len(self) + len(values)): values}), )
		super(ObservableList, self).extend(values)
		self.changed(self, previous=previous, current=current)

	def pop(self, index=None):
		if index is None:
			index = len(self) - 1
		value = super(ObservableList, self).pop(index)
		previous, current = (self._unbind_changed({(index, index + 1): [value]}), ), (self._bind_changed({(index, index): []}), )
		self.changed(self, previous=previous, current=current)
		return value

	def remove(self, value):
		index = self.index(value)
		super(ObservableList, self).remove(value)
		previous, current = (self._unbind_changed({(index, index + 1): [value]}), ), (self._bind_changed({(index, index): []}), )
		self.changed(self, previous=previous, current=current)

	def reverse(self):
		previous = {(0, len(self)): self[:]}
		super(ObservableList, self).reverse()
		current = {(0, len(self)): self[:]}
		if previous != current:
			self.changed(self, current=current, previous=previous)

	def sort(self):
		previous = {(0, len(self)): self[:]}
		super(ObservableList, self).sort()
		current = {(0, len(self)): self[:]}
		if previous != current:
			self.changed(self, current=current, previous=previous)

	"""Helpers"""

	def _bind_changed(self, values):
		"""Binds changed-event if values-item is instance of Observable*, returns values.

		Needed to provide changed-events of item (from values) up to item-holder (self).
		"""
		for value in values:
			if isinstance(value, (ObservableAttrDict, ObservableList, ObservableSet)):
				value.changed.bind(self._items_to_callbacks_to_unbind.setdefault(id(value), (lambda value: lambda model=None, previous=(None, ), current=(None, ): (
					self.changed(self, previous=({(self.index(value), self.index(value)): (value, )}, ) + previous, current=({(self.index(value), self.index(value)): (value, )}, ) + current)
				))(value)))  # invoke parent's changed-event if is changed
				# def _get_callback(value):
				#     def _callback(model=None, previous=(None, ), current=(None, )):
				#         return self.changed(self, previous=({(self.index(value), self.index(value)): (value, )}, ) + previous, current=({(self.index(value), self.index(value)): (value, )}, ) + current)
				#     return _callback
				# value.changed.bind(self._items_to_callbacks_to_unbind.setdefault(id(value), _get_callback(value)))  # invoke parent's changed-event if is changed

		return values


class ObservableSet(set, _NestedObservablesMixin):
	"""Set, which implements pattern Observer-Observable"""

	@Observable
	@classmethod
	def changed(cls, item=None, previous=(None, ), current=(None, )):
		"""Bind to it to receive 'changed'-events: (object.changed.bind(handler)), call it to send 'changed'-event"""

	def __init__(self, *args):
		_NestedObservablesMixin.__init__(self)
		super(ObservableSet, self).__init__(*args)
		values = set(*args)
		previous, current = (self._unbind_changed({}), ), (self._bind_changed(set(*args)), )
		self.changed(self, previous=previous, current=current)

	def __repr__(self):
		return 'set([{1}])'.format(self, ', '.join([repr(x) for x in self]))

	def __hash__(self):
		return id(self)
		# return hash(frozenset(self))

	def __iand__(self, values):
		previous = (self._unbind_changed(set(self - values)), )
		if previous:
			super(ObservableSet, self).__iand__(values)
			current = (self._bind_changed(set()), )
			self.changed(self, previous=previous, current=current)
		return self

	def __ior__(self, values):
		values = values.difference(self)
		if values:
			super(ObservableSet, self).__ior__(values)
			previous, current = (self._unbind_changed(set()), ), (self._bind_changed(values), )
			self.changed(self, previous=previous, current=current)
		return self

	def __isub__(self, values):
		values = values & self
		if values:
			super(ObservableSet, self).__isub__(values)
			previous, current = (self._unbind_changed(values), ), (self._bind_changed(set()), )
			self.changed(self, previous=previous, current=current)
		return self

	def __ixor__(self, values):
		previous, current = (self._unbind_changed(values & self), ), (self._bind_changed(values.difference(self)), )
		super(ObservableSet, self).__ixor__(values)
		self.changed(self, previous=previous, current=current)
		return self

	def add(self, value):
		if value not in self:
			super(ObservableSet, self).add(value)
			previous, current = (self._unbind_changed(set()), ), (self._bind_changed(set([value])), )
			self.changed(self, previous=previous, current=current)

	def clear(self):
		previous, current = (self._unbind_changed(set(self)), ), (self._bind_changed(set()), )
		if previous:
			super(ObservableSet, self).clear()
			self.changed(self, previous=previous, current=current)

	def difference_update(self, values):
		previous, current = (self._unbind_changed(values & self), ), (self._bind_changed(set()), )
		if previous:
			super(ObservableSet, self).difference_update(values)
			self.changed(self, previous=previous, current=current)

	def discard(self, value):
		if value in self:
			super(ObservableSet, self).discard(value)
			previous, current = (self._unbind_changed(set([value])), ), (self._bind_changed(set()), )
			self.changed(self, previous=previous, current=current)

	def intersection_update(self, values):
		previous, current = (self._unbind_changed(set(self - values)), ), (self._bind_changed(set()), )
		if previous:
			super(ObservableSet, self).intersection_update(values)
			self.changed(self, previous=previous, current=current)

	def pop(self):
		value = super(ObservableSet, self).pop()
		previous, current = (self._unbind_changed(set([value])), ), (self._bind_changed(set()), )
		self.changed(self, previous=previous, current=current)
		return value

	def remove(self, value):
		super(ObservableSet, self).remove(value)
		previous, current = (self._unbind_changed(set([value])), ), (self._bind_changed(set()), )
		self.changed(self, previous=previous, current=current)

	def symmetric_difference_update(self, values):
		previous, current = (self._unbind_changed(values & self), ), (self._bind_changed(values - self), )
		super(ObservableSet, self).symmetric_difference_update(values)
		self.changed(self, previous=previous, current=current)

	def update(self, values):
		if values:
			previous, current = (self._unbind_changed(set()), ), (self._bind_changed(values - self), )
			value = super(ObservableSet, self).update(values)
			self.changed(self, previous=previous, current=current)

	"""Helpers"""

	def _bind_changed(self, values):
		"""Binds changed-event if values-item is instance of Observable*, returns values.

		Needed to provide changed-events of item (from values) up to item-holder (self).
		"""
		for value in values:
			if isinstance(value, (ObservableAttrDict, ObservableList, ObservableSet)):
				value.changed.bind(self._items_to_callbacks_to_unbind.setdefault(id(value), (lambda value: lambda model=None, previous=(None, ), current=(None, ): (
					self.changed(self, previous=(value, ) + previous, current=(value, ) + current)
				))(value)))  # invoke parent's changed-event if is changed
				# def _get_callback(value):
				#     def _callback(model=None, previous=(None, ), current=(None, )):
				#         return self.changed(self, previous=(value, ) + previous, current=(value, ) + current)
				#     return _callback
				# value.changed.bind(self._items_to_callbacks_to_unbind.setdefault(id(value), _get_callback(value)))  # invoke parent's changed-event if is changed

		return values


class Memento(object):
	"""Implements pattern Memento (saves/restores object into/from an external storage)"""

	def __init__(self, path):
		self._path = path

	@property
	def path(self):
		return self._path

	@path.setter
	def path(self, value):
		if self._path != value:
			try:
				# If None -> path: create
				if self._path is None and value is not None:
					with open(value, 'w') as f:
						pass
				# If path -> None: remove
				elif self._path is not None and value is None:
					os.unlink(self._path)
				# If path -> path: rename
				else:
					os.rename(self._path, value)
			except OSError as e:
				import errno
				if e.errno == errno.ENOENT:  # No such file or directory
					pass
				else:
					raise
			self._path = value

	def restore(self, parse_values=False):
		values = []
		try:
			# values = [(re.split('\t+', line.decode('UTF-8').strip('\r\n')) + ['', ''])[:2] for line in open(self._path) if line and len(line) > 2 and not line.startswith('# ')]
			if os.path.isfile(self._path) and os.path.getsize(self._path) > 0:  # Skip opening if empty
				with open(self._path) as src:
					for line in src:
						try:
							if line and len(line) > 2 and not line.startswith('# '):
								values.append((re.split('\t+', line.decode('UTF-8').strip('\r\n')) + ['', ''])[:2])
						except UnicodeDecodeError:
							pass
		except IOError:
			pass

		if parse_values and values:
			values = [[k, (
				int(v) if v.isdigit() else (
					(v == 'True') if v in ('True', 'False') else (
						_literal_eval(v, dict=ObservableAttrDict, list=ObservableList, set=ObservableSet) if v.startswith('{') and v.endswith('}') else (
							_literal_eval(v, dict=ObservableAttrDict, list=ObservableList, set=ObservableSet) if v.startswith('[') and v.endswith(']') else (
								# _literal_eval(v[4:-1], dict=ObservableAttrDict, list=ObservableList, set=ObservableSet) if v.startswith('set([') and v.endswith('])') else (
								_literal_eval(v, dict=ObservableAttrDict, list=ObservableList, set=ObservableSet) if v.startswith('set([') and v.endswith('])') else (
									v
								)
							)
						)
					)
				)
			)] for k, v in values]

		return values

	def save(self, model, *args, **kwargs):
		with open(self._path, 'w') as f:
			filename = os.path.split(self._path)[-1]
			# try:
			items = [[str(item[0]), str(item[1])] for item in (list(model.items()) if isinstance(model, dict) else model) if item[1] is not None and item[1] is not self]  # Ignore Nones and Mementos
			# except:
			#     print >>sys.stderr, "model,", model; sys.stderr.flush()  # FIXME: must be removed
			#     print >>sys.stderr, "isinstance(model, dict),", isinstance(model, dict); sys.stderr.flush()  # FIXME: must be removed
			#     sys.exit()  # FIXME: must be removed

			max_tabs_count = max([len(x[0]) for x in items] or [0]) // 4 + 2  # Calculate max align for left_field
			for index, item in enumerate(items):
				# if index % 20 == 0:
				#     yield 'Saving {}:\n{} of {}'.format(filename, index, len(items))
				print(item[0] + '\t' * (max_tabs_count - len(item[0]) // 4) + item[1], file=f)


class UndoRedo(object):
	"""Saves/restores model's states in order to implement Undo/Redo-operations"""

	def __init__(self, model, skip_first=False):
		self._model = model
		self._states = []
		if not skip_first:
			self._states[:] = [list(model.items())]
		self._index = len(self._states) - 1

	def save(self):
		self._index += 1
		self._states = self._states[:self._index] + [list(self._model.items())]
		# print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'UNDO REDO SAVE:', self._states[self._index]; sys.stderr.flush()  # FIXME: must be removed/commented
		# raise Exception()

	def _restore(self):
		state = self._states[self._index]
		# print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'CURR STATE:', self._states[self._index + 1]; sys.stderr.flush()  # FIXME: must be removed/commented
		# print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'PREV STATE:', self._states[self._index]; sys.stderr.flush()  # FIXME: must be removed/commented
		for key, value in self._states[self._index]:
			setattr(self._model, key, value)

	def undo(self):
		if self._index > 0:
			self._index += -1
			self._restore()

	def redo(self):
		if self._index < len(self._states) - 1:
			self._index += 1
			self._restore()


class DiffUndoRedo(object):
	"""Saves/restores diffs between model's states in order to implement Undo/Redo-operations"""

	def __init__(self, model):
		self._model = model
		self._logs = []
		self._index = len(self._logs)
		self._log = []
		self._allow_events = True
		model.changed.bind((lambda ref: (lambda *args, **kwargs: (ref() and ref()._allow_events and ref()._on_model_updated(*args, **kwargs))))(weakref.ref(self)))  # FIXME: the handler remains after the deletion
		# def _get_callback(ref):
		#     def _callback(*args, **kwargs):
		#         return ref() and ref()._allow_events and ref()._on_model_updated(*args, **kwargs)
		#     return _callback
		# model.changed.bind(_get_callback(weakref.ref(self)))  # invoke parent's changed-event if is changed

	def _on_model_updated(self, model=None, previous=(None, ), current=(None, )):
		# print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), self.__class__, object.__repr__(model), previous and previous, current and current; sys.stderr.flush()  # FIXME: must be removed

		self._log.append((previous, current))  # Register changes of model

	def save(self):
		if self._log:
			self._logs = self._logs[:self._index] + [self._log]
			self._index += 1
			self._log = []

	def _restore(self, reverse=False):
		model = self._model
		log = self._logs[self._index]

		def _apply_removing(model, record):
			for key, subrecord in record.items():
				if key.__class__ is tuple and len(key) == 2:
					from_index, to_index = key
					if model[from_index:to_index] != subrecord:
						raise ValueError('Can not apply, values are different: {} and {}'.format(model[from_index:to_index], subrecord))
					del model[from_index:to_index]
				else:
					_apply_removing(model[key], subrecord)

		def _apply_insertion(model, record):
			for key, subrecord in record.items():
				if key.__class__ is tuple and len(key) == 2:
					from_index, to_index = key
					model[from_index:from_index] = subrecord  # Unique Indices are not faulty. It will be [from_index:to_index] after insertion.
				else:
					_apply_insertion(model[key], subrecord)

		self._allow_events = False
		for record in (reversed(log) if reverse else log):
			to_remove, to_insert = (reversed(record) if reverse else record)
			_apply_removing(model, to_remove)
			_apply_insertion(model, to_insert)
		self._allow_events = True

	def undo(self):
		if self._index > 0:
			self._index += -1
			self._restore(reverse=True)

	def redo(self):
		if self._index < len(self._logs):
			self._restore()
			self._index += 1


class IterationMixture(object):
	"""Deprecated"""

	def __iter__(self):
		for item in self.models:
			yield item


def _literal_eval(node_or_string, tuple=tuple, list=list, dict=dict, set=set):
	"""Customized literal_eval from ast.py"""
	_safe_names = {'None': None, 'True': True, 'False': False}
	if isinstance(node_or_string, str):
		node_or_string = ast.parse(node_or_string, mode='eval')
	if isinstance(node_or_string, ast.Expression):
		node_or_string = node_or_string.body

	def _convert(node):
		if isinstance(node, ast.Str):
			return node.s
		elif isinstance(node, ast.Num):
			return node.n
		elif isinstance(node, ast.Tuple):
			return tuple(map(_convert, node.elts))
		elif isinstance(node, ast.List):
			return list(map(_convert, node.elts))
		elif isinstance(node, ast.Dict):
			return dict((_convert(k), _convert(v)) for k, v in zip(node.keys, node.values))
		elif isinstance(node, ast.Call):
			if node.func.id == 'set': # and isinstance(node.args, ast.List):
				# print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'node.args=', node.args; sys.stderr.flush()  # FIXME: must be removed/commented
				# print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'node.starargs=', node.starargs; sys.stderr.flush()  # FIXME: must be removed/commented
				# values = [_convert(v) for v in node.args]
				# print >>sys.stderr, '{0.f_code.co_filename}:{0.f_lineno}:'.format(sys._getframe()), 'values=', values; sys.stderr.flush()  # FIXME: must be removed/commented
				# sys.exit()  # FIXME: must be removed/commented
				return set(*(_convert(v) for v in node.args))
		elif isinstance(node, ast.Name):
			if node.id in _safe_names:
				return _safe_names[node.id]
		elif \
			isinstance(node, ast.BinOp) and \
			isinstance(node.op, (ast.Add, ast.Sub)) and \
			isinstance(node.right, ast.Num) and \
			isinstance(node.right.n, complex) and \
			isinstance(node.left, ast.Num) and \
			isinstance(node.left.n, (int, float)):
			left = node.left.n
			right = node.right.n
			if isinstance(node.op, ast.Add):
				return left + right
			else:
				return left - right
		from helpers import my_trace; print('node = ', end=' ') ; my_trace.dump_object(node, depth=2)  # FIXME: must be removed/commented
		raise ValueError('Malformed string: {}, {}, {}'.format(node.__class__, node, node.id))
	return _convert(node_or_string)


def run_observable_attr_dict():
	logging.getLogger(__name__).setLevel(logging.INFO)

	class Test(ObservableAttrDict):
		pass

	def print_message_on_changed(item=None, previous=(None, ), current=(None, )):
		print("print_message_on_changed():", "    {}    << {}    >> {}    <> ".format(item, previous, current), file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed

	logging.getLogger(__name__).info('Binding callback to class...')
	Test.changed.bind(print_message_on_changed)
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Creating object and filling it with 3 subobjects...')
	a, b, c = ObservableAttrDict(x=1), ObservableList([2]), ObservableSet([3])
	test = Test(a=a, b=b, c=c)
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Binding callback to object...')
	test.changed.bind(print_message_on_changed)
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Calling changed-event manually...')
	test.changed(test)
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Changing existing subitem "a.x"...')
	a.x = 1.1
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Adding new item "d" (as attribute)...')
	test.d = ObservableAttrDict(x=4)
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Setting subitem "d.y"...')
	test.d.y = 4.1
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Replacing existing item "d" (as attribute)...')
	test.d = ObservableAttrDict(x=5)
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Changing existing subitem "d.y"...')
	test.d.y = 5.1
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Adding new item "e" (as item)...')
	test['e'] = ObservableAttrDict(x=6)
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Replacing existing item "e" (as item)...')
	test['e'] = ObservableAttrDict(x=7)
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Updating object with three new items "c", "d", "e"...')
	test.update(dict(c=ObservableAttrDict(x=3), d=ObservableAttrDict(x=4)), e=ObservableAttrDict(x=5))
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Updating object with three existing items "c", "d", "e"...')
	test.update(dict(c=ObservableAttrDict(x=3), d=ObservableAttrDict(x=4)), e=ObservableAttrDict(x=5))
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Removing item "e" (as attribute)')
	del test.e
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Removing item "d" (as item)')
	del test['d']
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Setting item "d" if not exists (not exists)...')
	test.setdefault('d', ObservableAttrDict(x=4))
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Setting item "d" if not exists (exists)...')
	test.setdefault('d', ObservableAttrDict(x=5))
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Popping item "d" (exists)...')
	test.pop('d')
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Popping item "d" (not exists)...')
	test.pop('d', False)
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Popping some item ("c"?)...')
	test.popitem()
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Clearing object...')
	test.clear()
	logging.getLogger(__name__).info('----------------------------------------')

	logging.getLogger(__name__).info('Clearing object (empty)...')
	test.clear()
	logging.getLogger(__name__).info('----------------------------------------')


def run_observable_list():
	class Test(ObservableList):
		pass

	def print_message_on_changed(item=None, previous=(None, ), current=(None, )):
		print("print_message_on_changed():", "{}, << {}, >> {}".format(item, previous, current), file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed

	Test.changed.bind(print_message_on_changed)
	test = Test([ObservableAttrDict(x=-1)])
	test.changed.bind(print_message_on_changed)
	test[0] = ObservableAttrDict(x=1)
	test[0] = ObservableAttrDict(x=1)
	test.append(ObservableAttrDict(x=2))
	test.insert(10, ObservableAttrDict(x=3))
	test.changed(test)
	test[1:3] = [ObservableAttrDict(x=4), ObservableAttrDict(x=5), ObservableAttrDict(x=6), ObservableAttrDict(x=7), ObservableAttrDict(x=8), ObservableAttrDict(x=9)]
	del test[2]
	del test[1:3]
	test.pop()
	test.pop(0)
	test.extend([ObservableAttrDict(x=2), ObservableAttrDict(x=1), ObservableAttrDict(x=5), ObservableAttrDict(x=4), ObservableAttrDict(x=3), ObservableAttrDict(x=6)])
	test.remove(ObservableAttrDict(x=8))
	test.reverse()
	test.sort()
	test += [ObservableAttrDict(x=8), ObservableAttrDict(x=9)]
	test *= 0
	test += [ObservableAttrDict(x=8), ObservableAttrDict(x=9)]
	test *= 3


def run_observable_set():
	class Test(ObservableSet):
		pass

	def print_message_on_changed(item=None, previous=(None, ), current=(None, )):
		print("print_message_on_changed():", "item={}, previous={}, current={}".format(item, previous, current), file=sys.stderr); sys.stderr.flush()  # FIXME: must be removed

	Test.changed.bind(print_message_on_changed)
	x1 = ObservableAttrDict(x=1)
	test = Test([x1, ObservableAttrDict(x=2), ObservableAttrDict(x=3)])
	test.changed.bind(print_message_on_changed)
	test &= set([x1, ObservableAttrDict(x=2), ObservableAttrDict(x=3)])

	x1.x = 1.1

	test &= set([ObservableAttrDict(x=2), ObservableAttrDict(x=3), ObservableAttrDict(x=4)])
	test |= set([ObservableAttrDict(x=3), ObservableAttrDict(x=4), ObservableAttrDict(x=5), ObservableAttrDict(x=6)])
	test |= set([ObservableAttrDict(x=3), ObservableAttrDict(x=4), ObservableAttrDict(x=5), ObservableAttrDict(x=6)])
	test -= set([ObservableAttrDict(x=6)])
	test -= set([ObservableAttrDict(x=6)])
	test ^= set([ObservableAttrDict(x=1), ObservableAttrDict(x=4), ObservableAttrDict(x=5), ObservableAttrDict(x=6)])
	test ^= set([ObservableAttrDict(x=4), ObservableAttrDict(x=5), ObservableAttrDict(x=6)])
	test.add(ObservableAttrDict(x=6))
	test.add(ObservableAttrDict(x=6))
	test.difference_update(set([ObservableAttrDict(x=6), ObservableAttrDict(x=7)]))
	test.difference_update(set([ObservableAttrDict(x=6), ObservableAttrDict(x=7)]))
	test.intersection_update(set([ObservableAttrDict(x=2), ObservableAttrDict(x=3), ObservableAttrDict(x=4), ObservableAttrDict(x=5), ObservableAttrDict(x=6)]))
	test.intersection_update(set([ObservableAttrDict(x=2), ObservableAttrDict(x=3), ObservableAttrDict(x=4), ObservableAttrDict(x=5), ObservableAttrDict(x=6)]))
	test.symmetric_difference_update(set([ObservableAttrDict(x=4), ObservableAttrDict(x=5), ObservableAttrDict(x=6), ObservableAttrDict(x=7)]))
	x6 = ObservableAttrDict(x=6)
	test.update(set([ObservableAttrDict(x=4), ObservableAttrDict(x=5), x6, ObservableAttrDict(x=7)]))
	test.discard(ObservableAttrDict(x=7))
	test.discard(ObservableAttrDict(x=7))
	test.remove(x6)
	try:
		test.remove(x6)
	except KeyError:
		pass
	test.pop()
	test.pop()
	test.clear()
	test.clear()


def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('-r', '--run-function', required=True, choices=[k[len('run_'):] for k in globals() if k.startswith('run_')], help='Function to run (without "run_"-prefix)')
	kwargs = vars(parser.parse_known_args()[0])  # Breaks here if something goes wrong

	globals()['run_' + kwargs['run_function']]()

if __name__ == '__main__':
	main()
