#!/bin/sh
# -*- coding: utf-8 -*-
# vim: set filetype=python noexpandtab:
"exec" "python" "-B" "$0" "$@"
# (c) gehrmann

from __future__ import division, unicode_literals; del division, unicode_literals
import setuptools
import sys

if __name__ == '__main__':
	# Sets utf-8 (instead of latin1) as default encoding for every IO
	reload(sys); sys.setdefaultencoding('utf-8')

# import pyguibot

__doc__ = """A setuptools-based setup module.

Links
=====

Documentation about setup.py (setuptools, eggs, etc):
	http://setuptools.readthedocs.io/en/latest/setuptools.html

Packaging and distributing projects (setup.py, wheels, etc.):
	https://packaging.python.org/en/latest/distributing.html
	https://github.com/pypa/sampleproject

How to use package resources:
	http://setuptools.readthedocs.io/en/latest/pkg_resources.html#id23

Suffix '.egg-info':
	/usr/lib/python2.7/dist-packages/setuptools/command/egg_info.py:104


Targets
=======

`sdist`
-------

Source distribution.
Creates archive specified by current platform
Arguments:
	--help-formats
	--formats=gztar,zip,bztar,ztar,tar
	--keep-temp
	--dist-dir


`install`
---------


`develop`
---------

Creates an .egg-link (in site-packages)
Arguments:
	-u, --uninstall			Uninstalls, but does not remove wrappers
	-m, --multi-version		Prevents to write entry into easy-install.pth, removes entries for other versions.
							No default version in this case. Use pkg_resources.require(...) to load a specific version.
	-d, --install-dir=PATH	Default is system's "site-packages" or based on options 'prefix' or 'install_lib'
	-s, --script-dir=PATH	Default is install-dir if specified or default system's place for scripts
	-x, --exclude-scripts	Do not create wrappers
	-a, --always-copy		Force copying if already required (in sys.path)
	--egg-path=PATH			Force path for .egg-link

"""


# # Get the long description from the README file
# with open(os.path.join(os.path.dirname(__file__), 'README.TXT'), encoding='utf-8') as f:
#     long_description = f.read()

setuptools.setup(
	name='pyguibot',
	version='0.1.1',  # Should comply with PEP440. For single-sourcing see https://packaging.python.org/en/latest/single_source_version.html
	description='Tool to automate GUI-interactions',
	# description='Tool to create/find a list of image templates and run keyboard/mouse actions on them',
	# long_description=long_description,
	url='https://bitbucket.org/gehrmann/pyguibot',  # The project's homepage
	author='Vladyslav Savchenko',
	author_email='gehrmann.mail@gmail.com',
	license='GNU GPL v3',
	keywords='gui auto tests check tool mouse keyboard',  # What does a project relate to?

	# See https://pypi.python.org/pypi?%3Aaction=list_classifiers
	classifiers=[
		# How mature is this project? Common values are
		#   3 - Alpha
		#   4 - Beta
		#   5 - Production/Stable
		'Development Status :: 3 - Alpha',

		# Indicate who your project is intended for
		'Intended Audience :: Developers',
		'Topic :: Software Development :: Build Tools',

		# Pick your license as you wish (should match "license" above)
		'License :: OSI Approved :: MIT License',

		# Specify the Python versions you support here. In particular, ensure
		# that you indicate whether you support Python 2, Python 3 or both.
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.3',
		'Programming Language :: Python :: 3.4',
		'Programming Language :: Python :: 3.5',
	],

	# Local packages to include (custom list or through setuptools.find_packages())
	# packages=setuptools.find_packages(exclude=['*.tests']),
	packages=setuptools.find_packages(exclude=[]),

	# Local scripts to include
	scripts=[
		'interactive-crop',
		'pyguibot',
	],

	# Alternatively, if you want to distribute just a my_module.py, uncomment this:
	# py_modules=["my_module"],

	python_requires='>=2.7',

	# Run-time dependencies. Will be installed by pip during installation.
	# https://packaging.python.org/en/latest/requirements.html
	# install_requires=['peppercorn', 'docutils>=0.3'],
	install_requires=[
		# '<package> [\[<extra>,...\]] [(==|<|<=|>|>=)<version>] [; [python_version(==|<|<=|>|>=)"<version>" | platform_system=="(Windows|<<from_PEP508>>|...)"]]',
		'setuptools',  # Needed to resolve version from pkg-tool (in pyguibot/__init__.py)
	],
	dependency_links=[
		# '[
		#     <url_to_eggs_repository>
		#   | <url_to_egg>
		#   | <url_to_single_script.py>#egg=<project>-<version>
		#   | ([git+]<url_to_git>|[svn+]<url_to_svn>|[hg+]<url_to_hg>)[@<revision>]#egg=<project>-<version>
		#   | SourceForge's showfiles.php
		# ]',
		# <version> can be omitted if also omitted in requirements
	],

	# Additional dependencies (tagged)
	# > pip install -e .[dev|test]
	extras_require={
		# 'PDF':  ["ReportLab>=1.2", "RXP"],
		# 'reST': ["docutils>=0.3"],
		# 'dev': ['check-manifest'],
		# 'test': ['coverage'],
	},

	# include_package_data=True,  # Append data found in MANIFEST.in

	# Local data to include (>=py27)
	package_data={
		# '': ['*.txt', '*.rst'],  # Include any *.txt or *.rst files from any package
		# 'hello': ['*.msg'],  # Include any *.msg files found in the 'hello' package
	},

	# exclude_package_data={  # Excludes data _from_installation_
	#     '': ['README.TXT'],
	# },

	# 'package_data' is the preferred approach, but you may need to place data into <sys.prefix>/my_data.
	# In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
	# See: http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files
	# data_files=[('my_data', ['data/data_file'])],
	data_files=[],

	eager_resources=[],  # List of files forced to be extracted from "resources" (*.dll, *.so, *.dylib will be extracted anyway)

	# To provide executable scripts, use entry points in preference to the
	# "scripts" keyword. Entry points provide cross-platform support and allow
	# pip to create the appropriate form of executable for the target platform.
	entry_points={
		# '(gui_scripts|console_scripts|setuptools.installation|<entry_point_group>)': [
		#     '(<name_of_executable>|.<extension>|eggsecutable) = <package>.<path_to_module>:(<function>|<class>.<method>) [\[<required_extra>, ...\]]',
		# ],
		'gui_scripts': [
			'pyguibot = controllers.qt_gui',
			'.pgb = controllers.qt_gui',
		],
	},
)
