#!/bin/sh
# -*- coding: utf-8 -*-
# vim: noexpandtab
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division, unicode_literals

__doc__ = """
This module provides a model to store program's settings
"""

import os
import sys

if __name__ == '__main__':
	reload(sys); sys.setdefaultencoding('utf-8')
	os.chdir((os.path.dirname(__file__) or '.') + '/..'); sys.path.insert(0, os.path.realpath(os.getcwd()))

from models.abstract import Memento, ObservableAttrDict


class Settings(ObservableAttrDict):
	"""Stores program's settings"""

	def __init__(self):
		import styles

		for key, value in dict(
				# default_font=dict(family='DejaVu Sans', pixelSize=styles.mm2px(2.6), weight=12, italic=False),
		).items():
			setattr(self.__class__, key, value)
			# setattr(self, key, None)
		self._memento = memento = Memento('settings.txt')
		self.update(memento.restore(parse_values=True))
		self.changed.bind(memento.save)

	def __repr__(self):
		return object.__repr__(self)

	def __getattr__(self, key):
		try:
			value = super(Settings, self).__getattr__(key)
		except KeyError:
			value = getattr(self.__class__, 'default_' + key)
		return value


def main():
	pass

if __name__ == '__main__':
	main()
