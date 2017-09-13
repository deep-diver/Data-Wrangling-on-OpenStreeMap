import os
import re
import csv
import schema
import codecs
import cerberus
import xml.etree.ElementTree as ET
from collections import defaultdict

SCHEMA = schema.Schema

OSM_FILE = "seattle_washington.osm"  
SAMPLE_FILE = "seattle_washington_sample_500.osm"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

STREET_TYPES_RE = re.compile(r'\b\S+\.?$', re.IGNORECASE)
PROBLEMCHARS = re.compile(r'[=\+\/\&\<\>\;\'\"\?\%\#\$\@\,\. \t\r\n]')
LOWER_COLON = re.compile(r'^([a-z|_]+)+:([a-z|_]+)+')

NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']

STREET_TYPE_MAPPINGS = { "St"    :  "Street",
                         "St."   :  "Street",
                         "Rd"    :  "Road",
                         "Rd."   :  "Road",
                         "Ave"   :  "Avenue",
                         "SW"    :  "Southwest",
                         "NW"    :  "Northwest",
                         "SE"    :  "Southeast",
                         "NE"    :  "Northeast",
                         "S."    :  "South",
                         "N."    :  "North",
                         "WY"    :  "Way"}

def audit_speed(filename):
      speed_types = []

      for event, elem in ET.iterparse(filename, events=("start",)):
            if elem.tag == "node" or elem.tag == "way":
                  for tag in elem.iter("tag"):
                        key = tag.attrib['k']
                        if key == 'maxspeed' or key == 'minspeed':
                              speed_types.append(tag.attrib['v'])

      return speed_types

def update_speed_unit(value):
      if value.find('mph') > -1:
            return value
      else:
            value = '{} mph'.format(value)
            return value

def audit_phone(filename):
      phone_len = defaultdict(list)

      for event, elem in ET.iterparse(filename, events=("start",)):
            if elem.tag == "node" or elem.tag == "way":
                  for tag in elem.iter("tag"):
                        key = tag.attrib['k']
                        if key == 'phone':
                              phone_num = re.sub(r'[\+\(\)\-\s]', '', tag.attrib['v'])
                              phone_len[len(phone_num)].append(tag.attrib['v'])

      return phone_len

def update_phone(phone_num):
      phone_num = re.sub(r'[\+\(\)\-\s]', '', phone_num)

      if len(phone_num) != 10 and \
            len(phone_num) != 11:
                  return None

      if len(phone_num) == 10:
            phone_num = '1{}'.format(phone_num)

      phone_num_parts = []
      phone_num_parts.append('+')
      phone_num_parts.append(phone_num[:1])
      phone_num_parts.append(' ')
      phone_num_parts.append(phone_num[1:4])
      phone_num_parts.append('-')
      phone_num_parts.append(phone_num[4:7])
      phone_num_parts.append('-')
      phone_num_parts.append(phone_num[7:])

      return ''.join(phone_num_parts)

def audit_street_name(filename):
      street_types = defaultdict(set)

      for event, elem in ET.iterparse(filename, events=("start",)):
            if elem.tag == "node" or elem.tag == "way":
                  for tag in elem.iter("tag"):
                        key = tag.attrib['k']
                        if key == "addr:street":
                              street_name = tag.attrib['v']
                              match = STREET_TYPES_RE.search(street_name)
                              if match:
                                    street_type = match.group()
                                    street_types[street_type].add(street_name)

      return street_types

def update_street_name(name):
      m = STREET_TYPES_RE.search(name)

      if m:
            street_type = m.group()
            
            try:
                  name = re.sub(street_type, STREET_TYPE_MAPPINGS[street_type], name)
                  return name
            except KeyError as e:
                  return name

def shape_tag_element(tag_element, ref_id, default_tag_type):
      tag_attribs = {}

      key = tag_element.attrib['k']
      value = tag_element.attrib['v']

      if re.search(PROBLEMCHARS, key):
            return None

      key_match = re.search(LOWER_COLON, key)
      if key_match:
            key_type = key_match.group(1)
            key_index = (key.index(key_type) + len(key_type))+1         

            tag_attribs['key'] = key[key_index: ]
            tag_attribs['type'] = key_type
      else:
            tag_attribs['key'] = key
            tag_attribs['type'] = default_tag_type

      tag_attribs['id'] = ref_id

      '''
      this is where tag value update will happen
      '''
      if tag_attribs['key'] == 'maxspeed' or tag_attribs['key'] == 'minspeed':
            value = update_speed_unit(value)
      elif tag_attribs['key'] == 'phone':
            value = update_phone(value)
      elif tag_attribs['key'] == 'street':
            value = update_street_name(value)
            
      if value == None:
            return None

      tag_attribs['value'] = value

      return tag_attribs

def shape_tag_elements(tags, parent_element, default_tag_type):
      for tag_element in parent_element.iter('tag'):
            tag_attribs = shape_tag_element(tag_element, \
                                          parent_element.attrib['id'], \
                                          default_tag_type)

            if tag_attribs != None:
                  tags.append(tag_attribs)

def shape_common_for_node_and_way(common_attribs, element):
      common_attribs['id'] = int(element.attrib['id'])
      common_attribs['uid'] = int(element.attrib['uid'])
      common_attribs['changeset'] = int(element.attrib['changeset'])
      common_attribs['user'] = element.attrib['user']
      common_attribs['version'] = element.attrib['version']
      common_attribs['timestamp'] = element.attrib['timestamp']

def shape_nd_element(nd_element, ref_id, position):
      nd_attribs = {}

      nd_attribs['id'] = ref_id
      nd_attribs['node_id'] = nd_element.attrib['ref']
      nd_attribs['position'] = position

      return nd_attribs 

def shape_element(element, key_error_count, problem_chars=PROBLEMCHARS, default_tag_type='regular'):
      node_attribs = {}
      way_attribs = {}
      way_nodes = []
      tags = []

      if element.tag == 'node':
            try:
                  shape_common_for_node_and_way(node_attribs, element)
                  node_attribs['lat'] = float(element.attrib['lat'])
                  node_attribs['lon'] = float(element.attrib['lon'])

                  shape_tag_elements(tags, element, default_tag_type)
                  return {'node': node_attribs, 'node_tags': tags}
            except KeyError as e:
                  key_error_count += 1

      elif element.tag == 'way':
            try:
                  shape_common_for_node_and_way(way_attribs, element)
                  shape_tag_elements(tags, element, default_tag_type)

                  nd_position = 0
                  for nd_element in element.iter('nd'):
                        nd_attribs = shape_nd_element(nd_element, \
                                                      int(element.attrib['id']), \
                                                      nd_position)
                        way_nodes.append(nd_attribs)
                        nd_position += 1

                  return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}
            except KeyError as e:
                  key_error_count += 1

class UnicodeDictWriter(csv.DictWriter, object):
      def writerow(self, row):
            super(UnicodeDictWriter, self).writerow({
                  k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
            })

      def writerows(self, rows):
            for row in rows:
                  self.writerow(row)

def get_element(osm_file, tags=('node', 'way', 'relation')):
      """Yield element if it is the right type of tag"""

      context = ET.iterparse(osm_file, events=('start', 'end'))
      _, root = next(context)
      for event, elem in context:
            if event == 'end' and elem.tag in tags:
                  yield elem
                  root.clear()

def process_map(file_in):
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

                  validator = cerberus.Validator()
                  key_error_count = 0

                  for element in get_element(file_in, tags=('node', 'way')):
                        el = shape_element(element, key_error_count)
                        if el:
                              if element.tag == 'node':
                                    nodes_writer.writerow(el['node'])
                                    node_tags_writer.writerows(el['node_tags'])
                              elif element.tag == 'way':
                                    ways_writer.writerow(el['way'])
                                    way_nodes_writer.writerows(el['way_nodes'])
                                    way_tags_writer.writerows(el['way_tags'])
            
                  print 'number of node or way element that encountered KeyError {}'.format(key_error_count)

def generate_sample():
      with open(SAMPLE_FILE, 'wb') as output:
            output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            output.write('<osm>\n  ')

            # Write every kth top level element
            for i, element in enumerate(get_element(OSM_FILE)):
                  if i % k == 0:
                        output.write(ET.tostring(element, encoding='utf-8'))

            output.write('</osm>')

def main():
      # generate sample file
      if not os.path.exists(SAMPLE_FILE):
            generate_sample() 

      if os.path.exists(SAMPLE_FILE):
            process_map(SAMPLE_FILE)

if __name__== "__main__":
      main()      