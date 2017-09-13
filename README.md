# Data Wrangling on Open Street Map data in Seattle area.

## What files this project includes?
- wrangling.py
 - standalone python source. This file consists of functions of the following
  - audit_speed(), audit_phone(), audit_street_name() to audit some data
  - update_speed(), update_phone(), update_street_name() to update inconsistent data to be consistent
  - shape_tag_element(), shape_tag_elements(), shape_nd_element(), shape_common_for_node_and_way(), shape_element() to operate extracting, auditing, updating, and save the given data into dictionary datatype.
  - process_map() to write re-organized data into seperate CSV files to import into SQLite DB later.
  - generate_sample() to generate sample OSM data file from the original since the original file is too big to audit at first.
- wrangle_us.ipynb
 - this file gives a better description how I did analyse, audit, update, and make SQL quries in step by step manner.
- wrangle_seattle.pdf
 - this file is converted version of wrangle_us.ipynb file.

## About the data
- Open Street Map
 - This kind of data is chosen to practive data wrangling because the data is not machine generated rather lots of human participated into form the entire set. I means there are lots of inconsistent data, so I could give a shot to look into it and re-organize them which is very good to practive data wrangling.
- Map area
 - Seattle 
  - the data can be downloaded here (https://mapzen.com/data/metro-extracts/metro/seattle_washington/)
  - mapzen provides pre-generated dataset for popular areas.
 - why seattle?
  - just for my interesting since I have spent an year as an exchange student at UW in 2011.
