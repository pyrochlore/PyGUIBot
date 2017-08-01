Description
===========
Application to automate GUI tests.

Requirements
============
sip
PyQt4 or PyQt5


pip install \
	pyuserinput \
	pyscreenshot

Links
=====
Cool screen recorder: git://git.cessen.com/recordscreen.git
	or http://www.davidrevoy.com/article65/recordscreen-py-video-and-audio-capture-from-terminal-for-ubuntu-12-04

Bugs
====
1) Hangs if mouse press event is invoking outside any window (on desktop)

Todo
====
* implement pyautogui

HowTo
=====
* Build *.deb:
	
	#!/bin/sh
	sudo dpkg -r pyguibot
	make clean deb
	echo INSTALLING
	sudo dpkg -i .build/pyguibot_0.1_all.deb 
	cd / && pyguibot data-install-manager

* Run in virtualenv sandbox:

	#!/bin/sh
	SANDBOX_PATH=".sandbox"
	read -r -d '' REQUIREMENTS << EOM
		colorama
		watchdog
	EOM
	test -d ${SANDBOX_PATH} || virtualenv --no-site-packages ${SANDBOX_PATH}
	. ${SANDBOX_PATH}/bin/activate
	{
		echo "${REQUIREMENTS}" > ${SANDBOX_PATH}/requirements.txt
		pip install -r ${SANDBOX_PATH}/requirements.txt
		./pyguibot.py
	} || exit 0
	deactivate
