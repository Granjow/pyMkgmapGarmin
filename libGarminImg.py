#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2009-2010, Simon A. Eugster <simon.eu@gmail.com>
# License: GNU General Public License, see http://www.gnu.org/licenses/gpl.html

# hex to bin: 'ab'.decode('hex') -> '\xab'
# bin to hex: '%02x' % ord('\xab')
# hex to dec: int('ab', 16) -> 171
# dec to hex: '%x' % (171)

from __future__ import with_statement # Python rocks ;)
import os # Path manipulation
import mmap # Binary Editing




def hex2dec(s) :
    """Hexadecimal string input: 'ff', decimal output: 255"""
    return int(s, 16)

def bin2dec(b) :
    """Binary input: '\10\10', decimal output: 21"""
    return int(b.encode('hex'), 16)

def bin2hex(b) :
    """Binary input: '\64\65', string output: '6465'"""
    return b.encode('hex')





class GarminImg :
    """Garmin .img file manipulation. See also
    https://sourceforge.net/projects/garmin-img/files/
    for further information."""
    
    def __init__(self, filename) :
        self.filename = os.path.abspath(filename)
    
    # Offsets relative to the beginning of the TRE section.
    offsetMapID = 0x74 
    offsetMapValues = 0x9a
    
    def binWord(self, id) :
        """Return the little endian byte representation of the 32bit input string"""
        return ('%08x' % (int(id))).decode('hex')[::-1]

    def updateID(self, toID, prefix='') :
        """Changes the map ID. The ID is saved in binary format as well 
        as a hash which needs to be correct, otherwise the map will not 
        be displayed on the Garmin device (most likely)."""
        
        with open(self.filename, 'r+b') as f :
            map = mmap.mmap(f.fileno(), 0) # 0: Read whole file
            
            # Position of the TRE subfile: Just do a binary search to find it.
            pos = map.find('GARMIN TRE') & 0xffffffffffffff00 # 14*f,2*0: Delete the last two bytes.
            
            
            # Find current map ID and print it (just for fun)
            l = pos+GarminImg.offsetMapID
            id = map[l : l+4][::-1] # Need to reverse.
            print('%sOld map ID at %x: 0x%08x = %s' % (prefix, pos, hex2dec(id.encode('hex')), hex2dec(id.encode('hex'))))
            
            # Set the new map ID.
            map[l : l+4] = self.binWord(toID)
            
            
            # Get the header length. Given by the first byte in the header section. 
            # For images created by mkgmap usually 188 bytes.
            headerLength = bin2dec(map[pos])
            print('%sHeader length: %d' % (prefix, headerLength))
            
            
            # Find current ID hash and print it (also just for fun)
            l = pos+GarminImg.offsetMapValues
            values = [map[l+4*i : l+4*(i+1)][::-1] for i in range(4)]
            print('%sValues: %s %s %s %s (original)' % (prefix, bin2hex(values[0]), bin2hex(values[1]), bin2hex(values[2]), bin2hex(values[3])))
            
            # Calculate new ID hash and write it to the img file.
            mv = MapValues(toID, headerLength)
            mv.calculate()
            print('%sValues: %08x %08x %08x %08x (calculated)' % (prefix, mv.value(0), mv.value(1), mv.value(2), mv.value(3)))
            for i in range(4) : 
                map[l+4*i : l+4*(i+1)] = self.binWord(mv.value(i))
            


    def rename(self, toID, prefix='') :
        """Renames the file names of all subfiles in the File Allocation Table (FAT) section.
        Example: 00010230RGN, 00010230TRE, 00010230LBL (8 digit name, file type)"""
        try :
            int(toID)
            self.ID = str(toID)
            if len(self.ID) < 8 :
                # Fill up with zeroes (from left) if necessary. 1 -> 00000001
                self.ID = self.ID.zfill(8)
            
            if len(self.ID) == 8 :
                pos = 0x600 # Starting position of the File Allocation Table.
                renamed = []
                count = 0
                oldid = ''
                with open(self.filename, 'r+b') as f :
                    map = mmap.mmap(f.fileno(), 0) # 0: Read whole file
                    oldid = map[pos+1:pos+9]
                    while not (map[pos] == '\x00') : # Header ends if 00 is read there.
                        renamed.append(pos)
                        count += 1
                        
                        # Change the file name
                        map[pos+1:pos+9] = self.ID
                        
                        # Position of next entry: Offset of 0x200 = 512 bytes
                        pos += 0x200
                
                # Change the map ID too.
                self.updateID(toID, prefix)
                
                return (count, renamed, oldid)
            else :
                print('%sWrong length (%s) of ID %s.' % (prefix, len(self.ID), toID))
        except ValueError :
            print('%sWrong ID: %s (needs to be 8 digits)' % (prefix, toID))
        return None

class MapValues :
    # This is the Python copy of this file:
    # http://svn.parabola.me.uk/mkgmap/trunk/src/uk/me/parabola/imgfmt/app/trergn/MapValues.java
    # which has been written by (c) Steve Ratcliffe (including comments).
    def __init__(self, mapId, headerLength) :
        self.mapId = mapId
        self.length = headerLength
        
        self.values = [range(8), range(8), range(8), range(8)]

    # Converts the digits in the map id to the values seen in this section.
    mapIdCodeTable = [
            0x0, 0x1, 0xf, 0x5,
            0xd, 0x4, 0x7, 0x6,
            0xb, 0x9, 0xe, 0x8,
            0x2, 0xa, 0xc, 0x3
    ]

    # Used to work out the required offset that is applied to all the
    # digits of the values.
    offsetMap = [
            6, 7, 5, 11,
            3, 10, 13, 12,
            1, 15, 4, 14,
            8, 0, 2, 9
    ]


    def value(self, n) :
        """There are four values.  Get value n.
        @param n Get value n, starting at 0 up to four."""
        
        out = self.values[n]

        res = 0
        for i in range(8) :
            res |= ((out[i] & 0xf) << (4 * (7 - i)))

        return res


    def calculate(self) :
        # Done in this order because the first and second depend on things
        # we have already calculated in three.
        self.calcThird()
        self.calcFourth()
        self.calcFirst()
        self.calcSecond()

        self.addOffset()

    def addOffset(self) :
        """Add an offset to all previously calculated values."""
        
        # To get the offset value we add up all the even nibbles of the map
        # number and transform via a table.
        n = self.mapIdDigit(1) + self.mapIdDigit(3) + self.mapIdDigit(5) + self.mapIdDigit(7)

        offset = MapValues.offsetMap[n & 0xf]
        for i in range(4) :
            for j in range(8) :
                self.values[i][j] += offset


    def calcFirst(self) :
        """This value is made from the third value, combined with the raw
        map id values."""
        
        out = self.values[0]
        v3 = self.values[3]

        # First bytes are the low bytes of the mapId, with the corresponding
        # value from value[3] added.
        out[0] = self.mapIdDigit(4) + v3[0]
        out[1] = self.mapIdDigit(5) + v3[1]
        out[2] = self.mapIdDigit(6) + v3[2]
        out[3] = self.mapIdDigit(7) + v3[3]

        # Copies of v3
        out[4] = v3[4]
        out[5] = v3[5]
        out[6] = v3[6]

        #Always (?) one more.  The one likely comes from some other
        # part of the header, but we don't know if or where.
        out[7] = v3[7] + 1



    def calcSecond(self) :
        """This is made from various parts of the third value and the raw digits
        from the map id.  There are two digits where the header length digits
        are used (or that could be a coincidence, but it holds up well so far)."""
        
        out = self.values[1]
        v3 = self.values[3]

        # Just same as in v3
        out[0] = v3[0]
        out[1] = v3[1]

        h1 = self.length >> 4
        h2 = self.length
        out[2] = (v3[2] + h1) & 0xf
        out[3] = (v3[3] + h2) & 0xf

        # The following are the sum of individual nibbles in U3 and the
        # corresponding nibble in the top half of mapId.
        out[4] = v3[4] + self.mapIdDigit(0)
        out[5] = v3[5] + self.mapIdDigit(1)
        out[6] = v3[6] + self.mapIdDigit(2)
        out[7] = v3[7] + self.mapIdDigit(3)


    def calcThird(self) :
        """This is made of the hex digits of the map id in a given order
        translated according to a given table of values."""
        
        out = self.values[2]
        for i in range(8) :
            n = self.mapIdDigit(i)
            out[(i ^ 1)] = MapValues.mapIdCodeTable[n]


    def calcFourth(self) :
        """This is just a copy of the third value."""
        
        out = self.values[3]
        v2 = self.values[2]
        for i in range(8) :
            out[i] = v2[i]


    def mapIdDigit(self, i) :
        """Extract the given nibble of the map id.  0 is the highest four bits.
        @param i The nibble number, 0 most significant, 7 the least.
        @return The given nibble of the map id."""

        return int(('%08x' % (int(self.mapId)))[i], 16)
