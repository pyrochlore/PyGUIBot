#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division, unicode_literals

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
import os
import re
import sys
import time
import weakref

if __name__ == '__main__':
	reload(sys); sys.setdefaultencoding('utf-8')
	os.chdir((os.path.dirname(__file__) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))

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


class ObservableAttrDict(AttrDict):
	"""AttrDict, which implements pattern Observer-Observable"""

	@Observable
	@classmethod
	def changed(cls, item=None, previous=None, current=None):
		"""Bind to it to receive 'changed'-events: (object.changed.bind(handler)), call it to send 'changed'-event"""

	def __init__(self, **kwargs):
		super(ObservableAttrDict, self).__init__(**kwargs)
		self.changed(self, current=self)

	def __hash__(self):
		return id(self)

	def __setitem__(self, key, value):

		# Check if there is a property with the same name -> call it's setter
		if key.__class__ in (str, unicode) and hasattr(self.__class__, key) and getattr(self.__class__, key).__class__ is property:
			previous = {key: getattr(self.__class__, key).fget(self)}
			getattr(self.__class__, key).fset(self, value)  # Call property's setter
			current = {key: getattr(self.__class__, key).fget(self)}
			self.changed(self, previous=previous, current=current)

		elif key not in self or self[key] != value:
			previous, current = {key: self.get(key, None)}, {key: value}
			super(ObservableAttrDict, self).__setitem__(key, value)
			self.changed(self, previous=previous, current=current)

	__setattr__ = __setitem__

	def __delitem__(self, key):
		previous, current = {key: self.get(key, None)}, {key: None}
		super(ObservableAttrDict, self).__delitem__(key)
		self.changed(self, previous=previous, current=current)

	__delattr__ = __delitem__

	def clear(self):
		previous, current = self.copy(), self.fromkeys(self)
		super(ObservableAttrDict, self).clear()
		if current:
			self.changed(self, previous=previous, current=current)

	def pop(self, key, *args):
		previous = {key: self.get(key, None)}
		current = {key: None}
		value = super(ObservableAttrDict, self).pop(key, *args)
		if previous != current:
			self.changed(self, previous=previous, current=current)
		return value

	def popitem(self):
		key, value = item = super(ObservableAttrDict, self).popitem()
		self.changed(self, previous={key: value}, current={key: None})
		return item

	def setdefault(self, key, *args):
		"""Dict.setdefault with lazy-calculated default value"""

		previous = {key: self.get(key, None)}
		value = super(ObservableAttrDict, self).setdefault(key, *([x() for x in args] if key not in self and len(args) > 0 and callable(args[0]) else args))
		current = {key: value}
		if previous != current:
			self.changed(self, previous=previous, current=current)
		return value

	def update(self, items, **kwargs):
		kwargs.update(items)

		current = {k: v for k, v in kwargs.iteritems() if k not in self or self[k] != v}
		if current:
			previous = {k: self.get(k, None) for k in current}
			super(ObservableAttrDict, self).update(kwargs)
			self.changed(self, previous=previous, current=current)


class ObservableList(list):
	"""List, which implements pattern Observer-Observable"""

	@Observable
	@classmethod
	def changed(cls, item=None, previous=None, current=None):
		"""Bind to it to receive 'changed'-events: (object.changed.bind(handler)), call it to send 'changed'-event"""

	def __init__(self, *args):
		super(ObservableList, self).__init__(*args)
		self.changed(self, previous={(0, 0): []}, current={(0, len(self)): list(self)})

	def __hash__(self):
		return id(self)

	def __setitem__(self, index, value):
		if len(self) <= index or self[index] != value:
			previous = {(index, index + 1): [self[index]]}
			super(ObservableList, self).__setitem__(index, value)
			self.changed(self, previous=previous, current={(index, index + 1): [self[index]]})

	def __delitem__(self, index):
		previous = {(index, index + 1): [self[index]]}
		super(ObservableList, self).__delitem__(index)
		self.changed(self, previous=previous, current={(index, index): []})

	def __setslice__(self, from_index, to_index, values):
		to_index = min(to_index, len(self))  # to_index for [:] is a very big number
		previous = {(from_index, to_index): self[from_index:to_index]}
		super(ObservableList, self).__setslice__(from_index, to_index, values)
		self.changed(self, previous=previous, current={(from_index, from_index + len(values)): values})

	def __delslice__(self, from_index, to_index):
		previous = {(from_index, to_index): self[from_index:to_index]}
		super(ObservableList, self).__delslice__(from_index, to_index)
		self.changed(self, previous=previous, current={(from_index, from_index): []})

	def __iadd__(self, values):
		previous, current = {(len(self), len(self)): []}, {(len(self), len(self) + len(values)): values}
		super(ObservableList, self).__iadd__(values)
		self.changed(self, previous=previous, current=current)
		return self

	def __imul__(self, count):
		if count != 1:
			previous, current = ({(0, len(self)): self[:]}, {(0, 0): []}) if count < 1 else ({(len(self), len(self)): []}, {(len(self), len(self) * (count)): self[:] * (count - 1)})
			super(ObservableList, self).__imul__(count)
			self.changed(self, previous=previous, current=current)
		return self

	def append(self, value):
		super(ObservableList, self).append(value)
		self.changed(self, previous={(len(self) - 1, len(self) - 1): []}, current={(len(self) - 1, len(self)): [value]})

	def insert(self, index, value):
		super(ObservableList, self).insert(index, value)
		index = min(index, len(self) - 1)
		self.changed(self, previous={(index, index): []}, current={(index, index + 1): [value]})

	def extend(self, values):
		previous, current = {(len(self), len(self)): []}, {(len(self), len(self) + len(values)): values}
		super(ObservableList, self).extend(values)
		self.changed(self, previous=previous, current=current)

	def pop(self, index=None):
		if index is None:
			index = len(self) - 1
		value = super(ObservableList, self).pop(index)
		self.changed(self, previous={(index, index + 1): [value]}, current={(index, index): []})
		return value

	def remove(self, value):
		index = self.index(value)
		super(ObservableList, self).remove(value)
		self.changed(self, previous={(index, index + 1): [value]}, current={(index, index): []})

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


class ObservableSet(set):
	"""Set, which implements pattern Observer-Observable"""

	@Observable
	@classmethod
	def changed(cls, item=None, previous=None, current=None):
		"""Bind to it to receive 'changed'-events: (object.changed.bind(handler)), call it to send 'changed'-event"""

	def __init__(self, *args):
		super(ObservableSet, self).__init__(*args)
		values = set(*args)
		self.changed(self, previous=set(), current=set(*args))

	def __hash__(self):
		return id(self)

	def __iand__(self, values):
		previous = set(self - values)
		if previous:
			super(ObservableSet, self).__iand__(values)
			self.changed(self, previous=previous, current=set())
		return self

	def __ior__(self, values):
		values = values.difference(self)
		if values:
			super(ObservableSet, self).__ior__(values)
			self.changed(self, previous=set(), current=values)
		return self

	def __isub__(self, values):
		values = values & self
		if values:
			super(ObservableSet, self).__isub__(values)
			self.changed(self, previous=values, current=set())
		return self

	def __ixor__(self, values):
		previous = values & self
		current = values.difference(self)
		super(ObservableSet, self).__ixor__(values)
		self.changed(self, current=current, previous=previous)
		return self

	def add(self, value):
		if value not in self:
			super(ObservableSet, self).add(value)
			self.changed(self, previous=set(), current=set([value]))

	def clear(self):
		previous = set(self)
		if previous:
			super(ObservableSet, self).clear()
			self.changed(self, previous=previous, current=set())

	def difference_update(self, values):
		previous = values & self
		if previous:
			super(ObservableSet, self).difference_update(values)
			self.changed(self, previous=previous, current=set())

	def discard(self, value):
		if value in self:
			super(ObservableSet, self).discard(value)
			self.changed(self, previous=set([value]), current=set())

	def intersection_update(self, values):
		previous = set(self - values)
		if previous:
			super(ObservableSet, self).intersection_update(values)
			self.changed(self, previous=previous, current=set())

	def pop(self):
		value = super(ObservableSet, self).pop()
		self.changed(self, previous=set([value]), current=set())
		return value

	def remove(self, value):
		super(ObservableSet, self).remove(value)
		self.changed(self, previous=set([value]), current=set())

	def symmetric_difference_update(self, values):
		previous = values & self
		current = values - self
		super(ObservableSet, self).symmetric_difference_update(values)
		self.changed(self, current=current, previous=previous)

	def update(self, values):
		if values:
			current = values - self
			value = super(ObservableSet, self).update(values)
			self.changed(self, previous=set(), current=current)


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
						ast.literal_eval(v) if v.startswith('{') and v.endswith('}') or v.startswith('[') and v.endswith(']') else (set(ast.literal_eval(v[4:-1])) if v.startswith('set([') and v.endswith('])') else v)
					)
				)
			)] for k, v in values]

		return values

	def save(self, model, *args, **kwargs):
		with open(self._path, 'w') as f:
			filename = os.path.split(self._path)[-1]
			# try:
			items = [[unicode(item[0]), unicode(item[1])] for item in (model.items() if isinstance(model, dict) else model) if item[1] is not None and item[1] is not self]  # Ignore Nones and Mementos
			# except:
			#     print >>sys.stderr, "model,", model; sys.stderr.flush()  # FIXME: must be removed
			#     print >>sys.stderr, "isinstance(model, dict),", isinstance(model, dict); sys.stderr.flush()  # FIXME: must be removed
			#     sys.exit()  # FIXME: must be removed

			max_tabs_count = max([len(x[0]) for x in items] or [0]) // 4 + 2  # Calculate max align for left_field
			for index, item in enumerate(items):
				# if index % 20 == 0:
				#     yield 'Saving {}:\n{} of {}'.format(filename, index, len(items))
				print >>f, item[0] + '\t' * (max_tabs_count - len(item[0]) // 4) + item[1]


class UndoRedo(object):
	"""Saves/restores model's states in order to implement Undo/Redo-operations"""

	def __init__(self, model):
		self._model = model
		self._states = [model.items()]
		self._index = len(self._states) - 1

	def save(self):
		self._index += 1
		self._states = self._states[:self._index] + [self._model.items()]

	def _restore(self):
		state = self._states[self._index]
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

	def _on_model_updated(self, model=None, previous=None, current=None):
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
			for key, subrecord in record.iteritems():
				if key.__class__ is tuple and len(key) == 2:
					from_index, to_index = key
					if model[from_index:to_index] != subrecord:
						raise ValueError('Can not apply, values are different: {} and {}'.format(model[from_index:to_index], subrecord))
					del model[from_index:to_index]
				else:
					_apply_removing(model[key], subrecord)

		def _apply_insertion(model, record):
			for key, subrecord in record.iteritems():
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


def _run_ObservableAttrDict():
	class Test(ObservableAttrDict):
		pass

	def print_message_on_changed(item=None, previous=None, current=None):
		print >>sys.stderr, "print_message_on_changed():", "item={}, previous={}, current={}".format(item, previous, current); sys.stderr.flush()  # FIXME: must be removed

	Test.changed.bind(print_message_on_changed)
	test = Test(a=1, b=2, c=3)
	test.changed.bind(print_message_on_changed)
	test.changed(test)
	test.d = 4
	test.d = 5
	test['e'] = 6
	test['e'] = 7
	test.update(dict(c=3, d=4), e=5)
	test.update(dict(c=3, d=4), e=5)
	del test['e']
	del test.d
	test.setdefault('d', 4)
	test.setdefault('d', 5)
	test.pop('d')
	test.pop('d', False)
	test.popitem()
	test.clear()
	test.clear()


def _run_ObservableList():
	class Test(ObservableList):
		pass

	def print_message_on_changed(item=None, previous=None, current=None):
		print >>sys.stderr, "print_message_on_changed():", "item={}, previous={}, current={}".format(item, previous, current); sys.stderr.flush()  # FIXME: must be removed

	Test.changed.bind(print_message_on_changed)
	test = Test([-1])
	test.changed.bind(print_message_on_changed)
	test[0] = 1
	test[0] = 1
	test.append(2)
	test.insert(10, 3)
	test.changed(test)
	test[1:3] = [4, 5, 6, 7, 8, 9]
	del test[2]
	del test[1:3]
	test.pop()
	test.pop(0)
	test.extend([2, 1, 5, 4, 3, 6])
	test.remove(8)
	test.reverse()
	test.sort()
	test += [8, 9]
	test *= 0
	test += [8, 9]
	test *= 3


def _run_ObservableSet():
	class Test(ObservableSet):
		pass

	def print_message_on_changed(item=None, previous=None, current=None):
		print >>sys.stderr, "print_message_on_changed():", "item={}, previous={}, current={}".format(item, previous, current); sys.stderr.flush()  # FIXME: must be removed

	Test.changed.bind(print_message_on_changed)
	test = Test([1, 2, 3])
	test.changed.bind(print_message_on_changed)
	test &= set([1, 2, 3])
	test &= set([2, 3, 4])
	test |= set([3, 4, 5, 6])
	test |= set([3, 4, 5, 6])
	test -= set([6])
	test -= set([6])
	test ^= set([1, 4, 5, 6])
	test ^= set([4, 5, 6])
	test.add(6)
	test.add(6)
	test.difference_update(set([6, 7]))
	test.difference_update(set([6, 7]))
	test.intersection_update(set([2, 3, 4, 5, 6]))
	test.intersection_update(set([2, 3, 4, 5, 6]))
	test.symmetric_difference_update(set([4, 5, 6, 7]))
	test.update(set([4, 5, 6, 7]))
	test.discard(7)
	test.discard(7)
	test.remove(6)
	try:
		test.remove(6)
	except KeyError:
		pass
	test.pop()
	test.pop()
	test.clear()
	test.clear()


def main():
	_run_ObservableAttrDict()
	# _run_ObservableList()
	# _run_ObservableSet()

if __name__ == '__main__':
	main()
