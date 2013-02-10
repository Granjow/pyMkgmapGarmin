#!/usr/bin/python
# -*- coding: utf-8 -*-

# This class stores and loads settings for mkgmap-python-2.py in/from an
# xml file. Example settings: Amount of RAM available, number of threads.

from lxml import etree
from libSettingsfile import SettingsFile
import os
import re

reMap = re.compile('(.*).osm.(bz2|pbf)')

class MkgmapInfo(SettingsFile) :
    # Variables
    I_SPLITTER = 'splitter-location'
    I_MKGMAP = 'mkgmap-location'
    I_RAM_TOTAL = 'available-ram'
    I_RAM = 'available-thread-ram'
    I_THREADS = 'threads'
    
    def __init__(self, filename) :
        self.filename = filename
        SettingsFile.__init__(self, self.filename, rootTag=etree.Element('pyMkgmap', src="openstreetmap.org", obj="prog"), writeback=True, forceTag=True)
