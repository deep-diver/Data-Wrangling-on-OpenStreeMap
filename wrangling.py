import os
import csv
import codecs
import xml.etree.ElementTree as ET
from collections import defaultdict
import re

import cerberus

import schema

OSM_FILE = "seoul_south-korea.osm"  

# Sample generation related
SAMPLE_FILE = "sample.osm"
k = 100 # Parameter: take every k-th top level element

# CSV file paths
NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

LOWER_COLON = re.compile(r'^([a-z|_]+)+:([a-z|_]+)+')
PROBLEMCHARS = re.compile(r'[=\+\/\&\<\>\;\'\"\?\%\#\$\@\,\. \t\r\n]')
STREET_TYPES = re.compile(r'\b\S+\.?$', re.IGNORECASE)

EXPECTED_STREET_TYPES = ["Street", "Avenue", "Boulevard", "Drive", "Court", "Place", "Square", "Lane", "Road", "Trail", "Parkway", "Commons"]
STREE_TYPE_MAPPINGS = { "St"    :  "Street",
                        "St."   :  "Street",
                        "Rd"    :  "Road",
                        "Rd."   :  "Road",
                        "Ave"   :  "Avenue"}

SCHEMA = schema.Schema

# Attributes for each tag
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']

def is_street_name(elem):
    return (elem.attrib['k'] == "addr:street")

def shape_tag_element(tag_element, ref_id):
      tag_attribs = {}

      key = tag_element.attrib['k']
      value = tag_element.attrib['v']

      if re.search(PROBLEMCHARS, key):
            return None

      key_match = re.search(LOWER_COLON, key)
      if key_match:
            key_type = key_match.group(1)
            key_index = (key.index(key_type) + len(key_type))+1         #key[key_index:]

            tag_attribs['key'] = key[key_index:]
            tag_attribs['type'] = key_type
      else:
            tag_attribs['key'] = key
            tag_attribs['type'] = 'regular'

      tag_attribs['id'] = ref_id
      tag_attribs['value'] = value

      return tag_attribs

def shape_nd_element(nd_element, ref_id, position):
      nd_attribs = {}

      nd_attribs['id'] = ref_id
      nd_attribs['node_id'] = nd_element.attrib['ref']
      nd_attribs['position'] = position

      return nd_attribs 

def shape_element(element, node_attr_fields=NODE_FIELDS, way_attr_fields=WAY_FIELDS,
                  problem_chars=PROBLEMCHARS, default_tag_type='regular'):
      node_attribs = {}
      way_attribs = {}
      way_nodes = []
      tags = []  # Handle secondary tags the same way for both node and way elements

      if element.tag == 'node':
            node_id = element.attrib['id']

            node_attribs['id'] = int(element.attrib['id'])
            node_attribs['uid'] = int(element.attrib['uid'])
            node_attribs['changeset'] = int(element.attrib['changeset'])
            node_attribs['lat'] = float(element.attrib['lat'])
            node_attribs['lon'] = float(element.attrib['lon'])
            node_attribs['user'] = element.attrib['user']
            node_attribs['version'] = element.attrib['version']
            node_attribs['timestamp'] = element.attrib['timestamp']

            for tag_element in element.iter('tag'):
                  tag_attribs = shape_tag_element(tag_element, node_id)

                  if tag_attribs != None:
                        tags.append(tag_attribs)

            return {'node': node_attribs, 'node_tags': tags}
      elif element.tag == 'way':
            # WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
            way_id = int(element.attrib['id'])

            way_attribs['id'] = int(element.attrib['id'])
            way_attribs['uid'] = int(element.attrib['uid'])
            way_attribs['changeset'] = int(element.attrib['changeset'])
            way_attribs['user'] = element.attrib['user']
            way_attribs['version'] = element.attrib['version']
            way_attribs['timestamp'] = element.attrib['timestamp']

            nd_position = 0
            for nd_element in element.iter('nd'):
                  nd_attribs = shape_nd_element(nd_element, way_id, nd_position)
                  way_nodes.append(nd_attribs)

                  nd_position += 1

            for tag_element in element.iter('tag'):
                  tag_attribs = shape_tag_element(tag_element, way_id)

                  if tag_attribs != None:
                        tags.append(tag_attribs)

            return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}


def get_element(osm_file, tags=('node', 'way', 'relation')):
    context = iter(ET.iterparse(osm_file, events=('start', 'end')))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()

def generate_sample():
  with open(SAMPLE_FILE, 'wb') as output:
      output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
      output.write('<osm>\n  ')

      # Write every kth top level element
      for i, element in enumerate(get_element(OSM_FILE)):
          if i % k == 0:
              output.write(ET.tostring(element, encoding='utf-8'))

      output.write('</osm>')

def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_string = pprint.pformat(errors)
        
        raise Exception(message_string.format(field, error_string))

class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

def process_map(file_in, validate):
    with codecs.open(NODES_PATH, 'w') as nodes_file, \
         codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
         codecs.open(WAYS_PATH, 'w') as ways_file, \
         codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
         codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])

def main():
      if not os.path.exists(SAMPLE_FILE):
            generate_sample()

      if os.path.exists(SAMPLE_FILE):
            process_map(SAMPLE_FILE, validate = False)

if __name__== "__main__":
  main()