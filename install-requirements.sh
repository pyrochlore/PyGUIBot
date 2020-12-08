#!/bin/sh

sudo pip3 install --requirement=requirements.txt 

sudo dpkg -l ffmpeg || ( \
	sudo apt install ffmpeg ; \
)
sudo dpkg -l python3-opencv || ( \
	sudo pip3 uninstall opencv-python ; \
	sudo apt install python3-opencv ; \
)
sudo dpkg -l zenity || ( \
	sudo apt install zenity ; \
)
