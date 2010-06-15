#!/usr/bin/python
# -*- coding: utf-8 -*-

from lxml import etree
from libSettingsfile import SettingsFile
import os
import re

reMap = re.compile('(?:.*/)?([^/]*).osm.bz2')

class MapInfo(SettingsFile) :
    # Variables
    I_CNAME = 'country-name'
    I_CABBR = 'country-abbreviation'
    I_FILENAME_MAP = 'filename-map'		# Filename.
    I_DIR_SPLITS = 'directory-splits'	# Where to put the splits
    I_MAP_STAT = 'map-stat'
    I_IMG_STAT = 'img-stat'
    I_MAP_NUMBER = 'map-number'
    I_STYLE_FILE = 'style-file'

    def __init__(self, mapfilename, dir=os.path.join('.','xmlData'), splitDir=os.path.join('.','osmData')) :
        try :
            self.mapID = reMap.match(mapfilename).group(1)
        except AttributeError :
            print('Error reading the map name from %s! Using default instead.' % (mapfilename))
            self.mapID = 'default'
        
        self.filename = os.path.join(dir, self.mapID + '.xml')
        SettingsFile.__init__(self, self.filename, rootTag=etree.Element('pyMkgmap', src="openstreetmap.org", obj="maps"), writeback=True, forceTag=True)
        
        self.setText(MapInfo.I_FILENAME_MAP, mapfilename)
        self.setText(MapInfo.I_DIR_SPLITS, os.path.join(splitDir, self.mapID))

    def complete(self) :
        return not (self.empty(MapInfo.I_CNAME) or self.empty(MapInfo.I_CABBR))
        
    def missing(self) :
        missing = []
        if self.empty(MapInfo.I_CNAME) :
            missing.append(MapInfo.I_CNAME)
        if self.empty(MapInfo.I_CABBR) :
            missing.append(MapInfo.I_CABBR)
        return missing
