#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2009-2011, Simon A. Eugster <simon.eu@gmail.com>
# License: GNU General Public License, see http://www.gnu.org/licenses/gpl.html
# Download: http://granjow.net/projects.html#garmin

# REQUIRES
# * Python 2.6 (not 3.x) <http://python.org/>, 
# * libSettingsfile.py, libMapinfo.py, libMkgmapinfo.py, libArgreader.py,
#   libGarminImg.py
# * lxml (package python-lxml on Linux).
#   For Windows: http://codespeak.net/lxml/installation.html
#   (Use easy_install)
# * Additionally: mkgmap.jar and splitter.jar, see
#   <http://www.mkgmap.org.uk/page/main>

# What does this program do?
# 
# mkgmap-garmin.py has to be invoked on the command line (use -h as
# argument to see the possible arguments).
#   All .osm.bz2 source files (direct extracts from the OpenStreetMap 
# Planet File) are at first split into smaller files for mkgmap
# (*.osm.gz). Then mkgmap creates images for each map (*.img) in their
# directory. 
#   At the end, mkgmap puts all selected maps (*.img) into one single 
# image, the gmapsupp.img file.
#   Existing map images will be re-used if the map has not changed 
# since the last time mkgmap-garmin.py has been run. This saves lots of 
# time because big maps won't have to be re-generate if you e.g. forgot
# to add one map to your gmapsupp.img map collection :)
#
# See also mkgmap-README.txt.


from __future__ import with_statement
import os # Running programs
import sys # Reading arguments
import re # Regular Expressions
import glob # Listing files
import urllib # URLs
import threading # Multi Threading
import Queue # Task Queue

from optparse import OptionParser
from libMapinfo import MapInfo
from libMkgmapinfo import MkgmapInfo
from libGarminImg import GarminImg
from libDirHash import dirHash


# Set up variables
config = 'config.xml'
mki = MkgmapInfo(config)
dirXml = 'xmlData'
dirData = 'osmData'
log = 'log-mkgmap.txt'
wd = os.getcwdu() # Working directory
fail = 'failed'

# License information for geonames file: http://download.geonames.org/export/dump/
geonamesUrl = 'http://download.geonames.org/export/dump/cities15000.zip'
geonames = os.path.join(dirData, re.search('/([^/]+)$',geonamesUrl).group(1))
reImgname = re.compile('(.*)(\d{4})(\d{4}\.img)')
reImgNr = re.compile('\d{4}(\d{4})')
imglist = []


parser = OptionParser(usage='Usage: %prog [options] [.osm.bz2 files] [.maplist files]\n\
\t.osm.bz2 files\n\
\t\tYou can get them from e.g. http://download.geofabrik.de/osm/ \n\
\t\tor http://downloads.cloudmade.com/.\n\n\
\t.maplist files\n\
\t\tPlain text files with a map filename on each line.\n\
\t\tWill add the maps given there to the list.')
parser.add_option('--nogeonames', action='store_false', default=True, dest='bGeonames', help='Do not use geonames file for city entries. (Is otherwise downloaded automatically if not available)')
parser.add_option('--noreuse', action='store_true', default=False, dest='bNoReuse', help='Do not re-use already compiled images, also if they are identical')
parser.add_option('--backup', action='store_true', default=False, dest='bBackup', help='Create a backup of all settings. TODO (not yet implemented)')
parser.add_option('-s', '--style-file', action='store', dest='fStyle', help='Optional style file (directory or zip)')
parser.add_option('-t', '--typ-file', action='store', dest='fTyp', help='Optional TYP file')
parser.add_option('-f', '--family-id', action='store', default="1", dest='sFamId', help='Optional family ID (shall match with TYP file)')
parser.add_option('-n', '--max-nodes', action='store', dest='iMaxNodes', help='Maximum nodes per map segment')
parser.add_option('-c', '--read-config', action='store', dest='fMkgmapConfig', help='Optional mkgmap configuration file (the --read-config= option passed to mkgmap)')
(options, args) = parser.parse_args()

if options.fStyle is not None : options.fStyle = os.path.abspath(options.fStyle)
if options.fTyp is not None : options.fTyp = os.path.abspath(options.fTyp)




# Check for paths.
if not os.path.exists(dirXml) :
    os.mkdir(dirXml)
if not os.path.exists(dirData) :
    os.mkdir(dirData)
if mki.empty(MkgmapInfo.I_SPLITTER) :
    mki.setText(MkgmapInfo.I_SPLITTER, 'splitter.jar')
if mki.empty(MkgmapInfo.I_MKGMAP) :
    mki.setText(MkgmapInfo.I_MKGMAP, 'mkgmap.jar')
if mki.empty(MkgmapInfo.I_THREADS) :
    threads = raw_input('How many threads should we use? \nNote that the available RAM will be divided by the number of threads.\nThe more threads, the less RAM for each thread. \n> threads (1): ')
    try :
        threads = int(threads)
    except ValueError :
        threads = 1
    if threads < 1 : threads = 1
    mki.setText(MkgmapInfo.I_THREADS, threads)
    mki.removeTag(MkgmapInfo.I_RAM) # Need to re-calculate
    threads = None
if mki.empty(MkgmapInfo.I_RAM) or mki.empty(MkgmapInfo.I_RAM_TOTAL) :
    threads = int(mki.text(MkgmapInfo.I_THREADS))
    minram = 1000*threads
    ram = raw_input('How many MB of RAM can we use in total? (default: 1500; minimum: %s) \n> ram (%s): ' % (minram, minram))
    try :
        ram = int(ram)
    except ValueError :
        ram = 1500
    if ram < minram :
        ram = minram
    
    tram = ram / threads # Ram per thread
    mki.setText(MkgmapInfo.I_RAM_TOTAL, str(ram) + 'm')
    mki.setText(MkgmapInfo.I_RAM, str(tram) + 'm')
    ram = None
if not os.path.isfile(mki.text(MkgmapInfo.I_SPLITTER)) :
    path = raw_input('Path for splitter.jar? ')
    if os.path.isdir(path) :
        path = os.path.join(path, 'splitter.jar')
    if not os.path.isfile(path) :
        print('Not existing: %s (May also be entered in %s)' % (path, config))
        sys.exit()
    else :
        # Set path. Use absolute path because we will be changing the directory later on.
        path = os.path.abspath(path)
        mki.setText(MkgmapInfo.I_SPLITTER, path)
        print('Set path: %s' % (path))
    path = None
if not os.path.isfile(mki.text(MkgmapInfo.I_MKGMAP)) :
    path = raw_input('Path for mkgmap.jar? ')
    if os.path.isdir(path) :
        path = os.path.join(path, 'mkgmap.jar')
    if not os.path.isfile(path) :
        print('Not existing: %s (May also be entered in %s)' % (path, config))
        sys.exit()
    else :
        # Set path
        path = os.path.abspath(path)
        print('Using absolute path ' + path)
        mki.setText(MkgmapInfo.I_MKGMAP, path)
        print('Set path: %s' % (path))
    path = None

mkgmap = mki.text(MkgmapInfo.I_MKGMAP)
splitter = mki.text(MkgmapInfo.I_SPLITTER)
ram = mki.text(MkgmapInfo.I_RAM)
threads = int(mki.text(MkgmapInfo.I_THREADS))

def word(w) :
    """Without spaces at the beginning and end."""
    o = re.search('^\s*(\w.*?\w?)\s*$', w)
    val = ''
    if o :
        val = o.group(1)
    return val










class ImgItem :
    def __init__(self, path, id) :
        self.path = path
        self.id = id

class MapThread(threading.Thread) :
    
    MapLock = threading.Lock()
    MapQueue = Queue.Queue()
    
    def run(self) :
        while True :
            self.map = MapThread.MapQueue.get()
            
            self.mapNr = self.map.text(MapInfo.I_MAP_NUMBER)
            self.prefix = str(self.mapNr).zfill(4)
            self.id = self.prefix + '0000'
            self.spid = str(self.mapNr) + ' \t'
            self.spids = re.sub('\d', ' ', self.spid)
            
            MapThread.MapLock.acquire()
            self.sdir = os.path.join(wd, self.map.text(MapInfo.I_DIR_SPLITS))
            print("%ssdir: %s, \n%swd: %s, \n%ssd: %s" % (self.spid, self.sdir, self.spids, wd, self.spids, self.map.text(MapInfo.I_DIR_SPLITS)))
            self.osmfile = os.path.join(wd, self.map.text(MapInfo.I_FILENAME_MAP))
            MapThread.MapLock.release()
            
            self.filesGz = ''
            
            self.makeMap()
            
            MapThread.MapQueue.task_done()
        
    def makeMap(self) :
        
        print('\n%sProcessing: %s.' % (self.spid, self.map.text(MapInfo.I_FILENAME_MAP)))
        self.err = False
        
        
        # Check whether maps can be re-used without re-compiling #
        self.imgfilelist = glob.glob(os.path.join(self.sdir, '*.img'))
        self.available = False
        self.osmStat = str(os.stat(self.osmfile))
        
        if self.map.text(MapInfo.I_MAP_STAT) == fail :
            print('%sBuilding this map failed last time.' % (self.spid))
        
        if options.bNoReuse :
            print('%sReuse of %s not desired.' % (self.spid, self.osmfile))
        elif self.osmStat != self.map.text(MapInfo.I_MAP_STAT) :
            print('%sThe osm file %s has changed in the meantime, need to rebuild it.' % (self.spid, self.osmfile))
        elif len(self.imgfilelist) <= 0:
            print('%sNo image files available for %s, need to build them.' % (self.spid, self.osmfile))
        elif str(options.fStyle) != self.map.text(MapInfo.I_STYLE_FILE) :
            print('%sStyle file has changed from %s to %s, map needs to be rebuilt.' % (self.spid, self.map.text(MapInfo.I_STYLE_FILE), options.fStyle))
        elif options.fStyle is not None and dirHash(options.fStyle) != self.map.text(MapInfo.I_STYLE_HASH) :
            print('%sStyle has been altered, map needs to be rebuilt.' % (self.spid))
        elif str(options.iMaxNodes) < self.map.text(MapInfo.I_MAX_NODES) :
            print('%sMaximum nodes have decreased from %s to %s, map needs to be rebuilt.' % (self.spid, self.map.text(MapInfo.I_MAX_NODES), options.iMaxNodes))
        else :
            # May be able to re-use map. 
            self.stat = str(os.stat(self.imgfilelist[0]))
            if self.stat == self.map.text(MapInfo.I_IMG_STAT) :
                
                print('%sMap did not change since last time; Re-using it.' % (self.spid))
                print('%sRenaming original files %s if necessary.' % (self.spid, self.imgfilelist))
                for self.file in self.imgfilelist :
                    
                    self.o = reImgname.match(self.file)
                    
                    if self.o is not None :
                        # Change ID in the file itself
                        id = self.prefix + reImgNr.search(self.file).group(1)
                        gi = GarminImg(self.file)
                        t = gi.rename(id, self.spid)
                        if not t == None :
                            print('%sReplaced old map ID (%s) with new one (%s) %s times \n%sin %s.' % (self.spid, t[2], id, t[0], self.spids, self.file))
                        # Change filename
                        os.rename(self.file, self.o.group(1) + self.prefix + self.o.group(3))
                        print('%sRenamed %s \n%sto %s.' % (self.spid, self.file, self.spids, self.o.group(1) + self.prefix + self.o.group(3)))
                        
                self.available = True
            else :
                print("%sMap info changed from \n%s%s to \n%s%s, cannot re-use, need to rebuild." % (self.spid, self.spids, self.map.text(MapInfo.I_IMG_STAT), self.spids, self.stat))
        self.imgfilelist = None; self.stat = None; self.osmStat = None; self.o = None; self.file = None;

        # We need to re-build the map.
        if not self.available :
            # Split the map into smaller files
            self.filter = '*.osm.gz'
            self.filelist = glob.glob(os.path.join(self.sdir, self.filter))
            if len(self.filelist) > 0 :
                print('%sRemoving %s: %s' % (self.spid, self.filter, self.filelist))
                for self.file in self.filelist :
                    os.remove(self.file)
            self.args = ''
            if options.bGeonames : self.args += ' --geonames-file=%s' % (os.path.join(wd, geonames))
            if options.iMaxNodes is not None : self.args += ' --max-nodes=%s' % (options.iMaxNodes)
            cmd = 'cd %s && java -Xmx%s -jar %s --mapid=%s --status-freq=1 %s %s 1>%s' % (self.sdir, ram, splitter, self.id, self.args, self.osmfile, log)
            print('%sSplitter: %s' % (self.spid, cmd))
            self.ret = os.system(cmd)
            self.filter = None; self.filelist = None; self.args = None; self.file = None
            
            if self.ret != 0 :
                print('%sError running splitter! Cannot build map %s.' % (self.spid, self.osmfile))
                self.available = False
                self.err = True
            else :
                self.ret = None
                
                self.filelist = glob.glob(os.path.join(self.sdir, '*.osm.gz'))
                print('%sSplit map files are %s' % (self.spid, self.filelist))
                for self.item in self.filelist :
                    self.filesGz += ' ' + self.item
                self.filelist = None; self.item = None;
                
                # Remove old .img files
                self.filter = '*.img'
                self.filelist = glob.glob(os.path.join(self.sdir, self.filter))
                if len(self.filelist) > 0 :
                    print('%sRemoving %s: %s' % (self.spid, self.filter, self.filelist))
                    for self.file in self.filelist :
                        os.remove(self.file)
                self.filter = None; self.filelist = None; self.file = None
                    
                # Create a .img file for this map
                print('%swd: %s' % (self.spid, os.getcwd()))
                self.args = ''
                if options.fStyle is not None : self.args += " --style-file=%s" % (options.fStyle)
                cmd = 'cd %s && java -enableassertions -Xmx%s -jar %s --adjust-turn-headings --check-roundabouts --merge-lines --keep-going --remove-short-arcs --latin1 --route --make-all-cycleways --add-pois-to-areas --preserve-element-order --location-autofill=1 --country-name="%s" --country-abbr=%s --family-name="map_%s" %s -n %s %s' % (self.sdir, mki.text(MkgmapInfo.I_RAM), mkgmap, self.map.text(MapInfo.I_CNAME, 'COUNTRY'), self.map.text(MapInfo.I_CABBR, 'ABC'), self.map.text(MapInfo.I_CABBR, 'ABC'), self.args, self.id, self.filesGz)
                print('%smkgmap:%s', (self.spid, cmd))
                ret = os.system(cmd)
                
                # Write .img file status
                if ret == 0 :
                    self.map.setText(MapInfo.I_MAP_STAT, str(os.stat(self.osmfile)))
                    self.available = True
                else :
                    # Error encountered.
                    print('%sError building map %s!' % (self.spid, self.osmfile))
                    self.available = False
                    self.err = True

        if self.err == True :
            self.map.setText(MapInfo.I_MAP_STAT, fail)
            
        elif self.available == True :
            # Add .img files to the gmapsupp list
            self.filelist = glob.glob(os.path.join(self.sdir, '*.img'))
            for self.file in self.filelist :
                MapThread.MapLock.acquire()
                if reImgname.match(self.file) is not None :
                    # Only accept valid file names (\d{8}.img)
                    imglist.append(ImgItem(self.file, self.mapNr))
                MapThread.MapLock.release()
            
            # Update the last used values to detect changes next time
            self.map.setText(MapInfo.I_STYLE_FILE, options.fStyle)
            self.map.setText(MapInfo.I_MAX_NODES, options.iMaxNodes)
            if options.fStyle is not None :
                self.map.setText(MapInfo.I_STYLE_HASH, dirHash(options.fStyle))
            
            if len(self.filelist) > 0 :
                # Write map file status
                self.map.setText(MapInfo.I_IMG_STAT, str(os.stat(self.filelist[0])))
            print('%sProcess FINISHED. Images: %s' % (self.spid, self.filelist))
            self.filelist = None; self.file = None;
        else :
            print('%sHow did we get there? Might be an error.' % (self.spid))
            None # Because of error









# Get maps from input argument
maplist = []
maplist = [s for s in args if re.compile('(?i).*\.osm\.bz2$').match(s)]

# Read maps from .maplist files, if there are some given
textlist = [s for s in args if re.compile('(?i).*\.maplist').match(s)]
reMap = re.compile('(?i)^[^#].*\.osm\.bz2')
for text in textlist :
    print('Reading items from %s (items can be commented out with a leading #).' % (text))
    try :
        f = open(text, 'r')
        for line in f :
            o = reMap.search(line)
            if o is not None :
                line = o.group()
                if not maplist.count(line) > 0 :
                    maplist.append(line)
                    print('Added from %s: %s' % (text, line))
    except IOError :
        None

c = 0
prefix = '\n'
for item in maplist :
    if not os.path.exists(item) :
        if c > 0 :
            prefix = ''
        print('%sRemoved map %s: File is not existing!' % (prefix, item))
        maplist.remove(item)
        c += 1
if c > 0 :
    print('')
c = None

if len(maplist) == 0 :
    imgs = glob.glob('*.osm.bz2')
    if len(imgs) > 0 :
        all = raw_input('No map file given. Use these instead?\n%s\n(Y/n) ' % imgs)
        if all.lower() == 'y' or all.lower() == 'j' or all == '' :
            for l in imgs :
                maplist.append(l)
if len(maplist) == 0:
    sys.exit()


# Download geonames file if necessary and requested
if options.bGeonames :
    if not os.path.exists(geonames) :
        f = open(geonames, 'wb')
        try :
            print('Downloading %s ...' % (geonamesUrl))
            zip = urllib.urlopen(geonamesUrl)
            for l in zip :
                f.write(l)
            f.close()
        except URLError :
            print('Could not download geonames file from %s to %s.' % (geonamesUrl, geonames))
            options.bGeonames = False


#Retrieve map information
mapinfolist = []
for map in maplist :
    # Read map information, if already available.
    mapinfo = MapInfo(map, splitDir=dirData)
    # Read missing information for this map
    missing = mapinfo.missing()
    if len(missing) > 0 :
        print('\n%s' % (map))
    for tag in missing :
        value = raw_input('\t%s? ' % (tag))
        value = word(value)
        if len(value) > 0 : 
            mapinfo.setText(tag, value)
    if not os.path.exists(mapinfo.text(MapInfo.I_DIR_SPLITS)) :
        os.mkdir(mapinfo.text(MapInfo.I_DIR_SPLITS))
    mapinfolist.append(mapinfo)
mapinfo = None
if len(mapinfolist) == 0 :
    print('No input maps (*.osm.bz2) given, exiting.')
    sys.exit()

# Build maps
n=0
mapThreads = [MapThread() for i in range(threads)]
for thread in mapThreads :
    thread.setDaemon(True)
    thread.start()
for map in mapinfolist :
    n = n+1
    map.setText(MapInfo.I_MAP_NUMBER, n)
    MapThread.MapQueue.put(map)
MapThread.MapQueue.join()
print('')


try :
    os.remove('gmapsupp.img')
except OSError :
    None


# Create gmapsupp.img from all .img files
list = '['
for img in imglist :
    list += img.path + ', '
list += ']'
print('Using available images: %s' % (list))

files = ''
reID = re.compile('(\d{8}).img')

for item in imglist :
    files += ' %s' % (item.path)

args = ""
if options.fTyp is not None : args += options.fTyp
if options.fMkgmapConfig is not None : args += " --read-config=%s" % (options.fMkgmapConfig)

cmd = 'java -Xmx%s -jar %s --gmapsupp --family-id=%s %s %s' % (mki.text(MkgmapInfo.I_RAM), mkgmap, options.sFamId, files, args)
print(cmd)
os.system(cmd)
