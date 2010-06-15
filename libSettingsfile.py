#!/usr/bin/python
# -*- coding: utf-8 -*-

# This class manages settings which are stored in an xml file. The 
# settings can autmatically be written back as soon as changed.

import lxml
from lxml import etree
import os

class SettingsFile :

    def __init__(self, filename, rootTag=None, writeback=False, forceTag=False) :
        """writeback immeadiately writes changes"""
        self.writeback = writeback
        self.filename = os.path.abspath(filename)
        
        if rootTag == None :
            rootTag = etree.Element('xml')
        if not isinstance(rootTag, lxml.etree._Element) :
            raise Exception('rootTag element %s is not of type %s!' % (rootTag, lxml.etree._Element))
        
        self.exists = False
        # Check whether the info file is already existing.
        # If yes, read it, if not, create one in memory.
        if os.path.exists(self.filename) :
            try :
                self.doc = etree.parse(filename).getroot()
                if forceTag and (not rootTag.tag == self.doc.tag) :
                    None
                else :
                    print("Read settings: " + self.filename)
                    self.exists = True
            except lxml.etree.XMLSyntaxError:
                print("Error reading settings. " + self.filename)
                None
        if not self.exists :
            self.doc = rootTag
        
    def write(self) :
        """Write the map info to disk. Not necessary if writeback is 
        enabled."""
        
        file = open(self.filename, 'w')
        file.write(etree.tostring(self.doc, encoding='utf-8', pretty_print=True))
        file.close()
        
    def node(self, tag) :
        return self.doc.find('.//' + tag)
        
    def text(self, tag, default=None) :
        """Returns the tag's text node («value»)"""
        
        if default is None :
            # Set default value
            # See http://docs.python.org/tutorial/controlflow.html#default-argument-values
            default = ''
        
        try :
            value = self.doc.find('.//%s' % (tag)).text
        except AttributeError :
            value = default
        return value

    def setText(self, tag='unknown', value='none') :
        """Sets text node («value»). Adds text node if necessary.
        Returns true if tag already contained value."""
        equal = False
        converted = False
        
        # Check encoding
        try :
            # Assuming value is an utf-8 encoded byte sequence it should
            # be possible to decode the object to an abstract unicode
            # object. If it fails, value was not utf-8 encoded and 
            # needs to be decoded (to standard python string format) 
            # from another encoding.
            value.decode('utf-8')
        except UnicodeDecodeError :
            # This should not happen here!
            value = value.decode('cp1252')
            print('Converted value: >' + value + "<")
            converted = True
        except AttributeError :
            value = str(value) # Not an object of type str
        
        # Set/update node value
        node = self.doc.find('.//' + tag)
        if node is None :
            node = etree.SubElement(self.doc, tag)
        if node.text == value :
            equal = True
        else :
            node.text = value
            if self.writeback :
                self.write()
        return equal
    
    def removeTag(self, tag) :
        """Returns True if tag has been removed."""
        removed = False
        node = self.node(tag)
        if node is not None :
            node.getparent().remove(node)
            removed = True
        return removed

    def empty(self, tag) :
        return (self.text(tag) == '')
