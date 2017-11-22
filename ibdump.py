#!/usr/bin/python

import os
import sys
import struct
import json
from collections import Counter


def rword(bytes):
	return struct.unpack("<i", bytes)[0]
def rquad(bytes):
	return struct.unpack("<q", bytes)[0]
def rdouble(bytes):
	return struct.unpack("<d", bytes)[0]
def rsingle(bytes):
	return struct.unpack("<f", bytes)[0]

# Reads a flexible number from the bytes array and returns a tuple
# containing the number read and the number of bytes read.
def readFlexNumber(bytes, addr):
	number = 0
	shift = 0
	ptr = addr
	while True:
		num = ord(bytes[ptr])
		ptr += 1

		number |= (num & 0x7F) << shift
		shift += 7

		if num & 0x80:
			break
		if shift > 30:
			raise Exception("Flex number invalid or too large.")
	return (number, ptr - addr)

def readHeader(bytes, start):
	hsize = rword(bytes[start : start+4])
	# print "Header size (words): " + str(hsize)
	sections = []
	sectionDataStart = start + 4
	for section in range(0, (hsize - 1)/2):
		objcount = rword(bytes[sectionDataStart + section * 8 : sectionDataStart + section * 8 + 4])
		address = rword(bytes[sectionDataStart + section * 8 + 4 : sectionDataStart + section * 8 + 8])
		sections += [(objcount, address)]
	return sections

def readKeys(bytes, keysSection):
	count, ptr = keysSection
	keys = []
	for i in range(0, count):
		start_ptr = ptr
		rd = readFlexNumber(bytes, ptr)
		length = rd[0]
		ptr += rd[1]

		keys.append((str(bytes[ptr: ptr + length]), (start_ptr, ptr - start_ptr, [])))
		ptr += length
	return keys

def readObjects(bytes, objectsSection):
	count, ptr = objectsSection
	objects = []
	for i in range(0, count):
		r0 = readFlexNumber(bytes, ptr)
		r1 = readFlexNumber(bytes, ptr + r0[1])
		r2 = readFlexNumber(bytes, ptr + r0[1] + r1[1])

		class_idx = r0[0]
		start_idx = r1[0]
		size = r2[0]
		log = [ptr, r0[1] + r1[1] + r2[1],
			   [("class_idx", ptr, r0[1]),
				("start_idx", ptr + r0[1], r1[0]),
				("size", ptr + r0[1] + r1[1], r2[0])]]

		ptr += r0[1] + r1[1] + r2[1]

		objects.append((class_idx, start_idx, size, log))
	return objects

def readClasses(bytes, classSection):
	count, addr = classSection
	classes = []
	ptr = addr
	for i in range(0, count):
		ptr_start = ptr
		r = readFlexNumber(bytes, ptr)
		length = r[0]
		ptr += r[1]

		tp = ord(bytes[ptr])
		ptr += 1

		unknown = None
		assert(tp in [0x80, 0x81])
		if tp == 0x81:
			unknown = rword(bytes[ptr : ptr + 4])
			ptr += 4
			print 'readClasses: Mystery value:', unknown, '(',

		classes.append((str(bytes[ptr: ptr + length - 1]), (ptr_start, length, [])))

		if unknown:
			print classes[-1], ')'

		ptr += length

	return classes

def readValues(bytes, valuesSection, debugKeys = []):
	count, addr = valuesSection
	values = []
	ptr = addr
	for i in range(0, count):
		start_ptr = ptr
		r = readFlexNumber(bytes, ptr)
		key_idx = r[0]
		ptr += r[1]

		encoding = ord(bytes[ptr])
		ptr += 1

		value = None
		if encoding == 0x00:  # single byte
			value = struct.unpack('b', (bytes[ptr]))[0]
			ptr += 1
		elif encoding == 0x01:  # short
			value = struct.unpack("<h", bytes[ptr: ptr + 2])[0]
			ptr += 2
		elif encoding == 0x02:  # 4 byte integer
			value = rword(bytes[ptr:ptr + 4])
			ptr += 4
		elif encoding == 0x03:  # 8 byte integer
			value = rquad(bytes[ptr:ptr+8])
			ptr += 8
		elif encoding == 0x04:
			value = False
		elif encoding == 0x05:	# true
			value = True
		elif encoding == 0x06:	# word
			# if len(debugKeys):
				# print "Found encoding with 0x6", debugKeys[key_idx]
			value = rsingle(bytes[ptr:ptr+4])
			ptr += 4
		elif encoding == 0x07:	# floating point
			value = rdouble(bytes[ptr:ptr+8])
			ptr += 8
		elif encoding == 0x08:	# string
			r = readFlexNumber(bytes, ptr)
			length = r[0]
			ptr += r[1]
			if length and ord(bytes[ptr]) == 0x07:  # double
				if length == 17:
					value = struct.unpack("<dd", bytes[ptr + 1 : ptr + 17])
				elif length == 33:
					value = struct.unpack("<dddd", bytes[ptr + 1 : ptr + 33])
				else:
					raise Exception("Well this is weird.")
			# elif length and ord(bytes[ptr]) == 0x06: # float
			# 	if length == 9:
			# 		value = struct.unpack("<ff", bytes[ptr + 1: ptr + 9])
			# 	elif length == 17:
			# 		value = struct.unpack("<ffff", bytes[ptr + 1: ptr + 17])
			# 	else:
			# 		raise Exception("Well this is weird.")
			else:
				value = str(bytes[ptr : ptr + length])
			ptr += length
		elif encoding == 0x09:	# nil?
			value = None
		elif encoding == 0x0A:	# object
			value = '@' + str(rword(bytes[ptr:ptr+4])) #object is stored as a 4 byte index.
			ptr += 4
		else:
			# print "dumping classes:", globals()['classes']
			print "dumping keys:" #, globals()['keys']
			for n, key in enumerate(globals()['keys']):
				print "%X\t%X\t%s" % (n, (n | 0x80), key)
			raise Exception("Unknown value encoding (key %d idx %d addr %d): " % (key_idx, i, ptr - 1) + str(encoding))
		values.append((key_idx, value, encoding, (start_ptr, ptr - start_ptr, [])))
	return values

def fancyPrintObjects(nib, prefix="", showencoding=False, objectDump={}, html=None):
	objects, keys, values, classes = nib
	for o_idx, object in enumerate(objects):
		#print object
		classname, classlog = classes[object[0]]
		obj_values = values[object[1]:object[1] + object[2]]

		print prefix + "%3d: %s" % (o_idx, classname)
		if html: print >> html, prefix + "%3d: %s" % (o_idx, classname)

		vals = []
		for v in obj_values:
			# print v
			k_str, k_log = keys[v[0]]
			v_str = str(v[1])
			v_log = v[3]

			printSubNib = k_str == 'NS.bytes' and len(v_str) > 40 and v_str.startswith('NIBArchive')

			if printSubNib:
				print prefix + '\t' + k_str + " = Encoded NIB Archive"
				nib = readNibSectionsFromBytes(v[1])
				fancyPrintObjects(nib, prefix + "\t", showencoding)

			else: # Boring regular data.
				if showencoding:
					print prefix + '\t' + k_str + ' = (' + str(v[2]) + ')', v_str
				else:
					print prefix + '\t' + k_str + ' =', v_str
					if html: print >> html, '<a href="#" onclick="Select(' + str(v_log[0]) + ', ' + str(
						v_log[1]) + ')">', prefix + '\t' + k_str + ' =', v_str + "</a>"
			vals.append((k_str, v_str))
		objectDump["@" + str(o_idx)] = [classname, vals]
	# if k_str == 'NS.bytes' and len(v_str) > 200:
	# 	with open('embedded.nib', 'wb') as f:
	# 		f.write(v[1])

def readNibSectionsFromBytes(bytes):
	sections = readHeader(bytes, 14)
	# print sections
	classes = readClasses(bytes, sections[3])
	# print classes
	objects = readObjects(bytes, sections[0])
	# print objects
	keys = readKeys(bytes, sections[1])
	# print keys
	values = readValues(bytes, sections[2])
	# print values
	return (objects, keys, values, classes)


def varsToDict(vars):
	vals_key_cnt = {}
	res = {}
	for key, v in vars:
		if not key in vals_key_cnt:
			res[key] = v
			vals_key_cnt[key] = 1
		else:
			if key in res:
				res[key + "[0]"] = res[key]
				del res[key]
			res[key + "[" + str(vals_key_cnt[key]) + "]"] = v
			vals_key_cnt[key] = vals_key_cnt[key] + 1
	return res


def optimizeSingleObject(objectDump, tp, values):
	res = None
	if tp == "NSString":
		if len(values) == 1 and "NS.bytes" == values[0][0]:
			res = values[0][1]
	elif tp == "UIColor":
		res = varsToDict(values)
	elif tp == "UIButtonContent":
		res = varsToDict(values)
	elif tp == "NSNumber":
		if len(values) == 1:
			res = values[0][1]
	elif (tp == "NSValue"):
		res = varsToDict(values)
	elif tp == "UIProxyObject":
		if len(values) == 1 and "UIProxiedObjectIdentifier" == values[0][0]:
			res = "proxy: " + values[0][1]
	elif (tp == "NSArray" or tp == "NSMutableArray"):
		res = []
		for key, v in values:
			if key == "NSInlinedValue":
				continue
			if key != "UINibEncoderEmptyKey":
				# not expected, don't convert
				res = None
				break
			res.append(v)
	elif (tp == "NSDictionary" or tp == "NSMutableDictionary"):
		res = {}
		idx = 0
		while idx < len(values):
			key = values[idx][0]
			v = values[idx][1]
			if key == "UINibEncoderEmptyKey":
				if idx + 1 < len(values):
					res[v] = values[idx + 1][1]
					idx += 2
				else:
					# not expected, don't convert
					res = None
					break
			else:
				if key != "NSInlinedValue":
					res[key] = v
				idx += 1
	elif (tp == "UINibKeyValuePair"):
		asDict = varsToDict(values)
		if "UIKeyPath" in asDict and "UIObject" in asDict and "UIValue" in asDict:
			uival = asDict["UIValue"]
			if not isinstance(uival, basestring): uival = json.dumps(uival, sort_keys=True)
			res = "pair: " + asDict["UIObject"] + "." + asDict["UIKeyPath"] + " = " + uival
	elif (tp == "UIRuntimeOutletConnection"):
		asDict = varsToDict(values)
		if "UIDestination" in asDict and "UILabel" in asDict and "UISource" in asDict:
			res = "outlet: " + asDict["UIDestination"] + " -> " + asDict["UISource"] + "." + asDict["UILabel"]
	elif (tp == "UIRuntimeEventConnection"):
		asDict = varsToDict(values)
		if "UIDestination" in asDict and "UILabel" in asDict and "UISource" in asDict and "UIEventMask" in asDict:
			res = "action: " + asDict["UISource"] + "on(" + str(asDict["UIEventMask"]) + ") -> " + asDict[
				"UIDestination"] + "." + asDict["UILabel"]
	elif (tp == "UIRuntimeOutletCollectionConnection"):
		asDict = varsToDict(values)
		if "UIDestination" in asDict and "UILabel" in asDict and "UISource" in asDict:
			# destination here is a reference, optimize it
			id = asDict["UIDestination"]
			dest = optimizeSingleObject(objectDump, objectDump[id][0], objectDump[id][1])
			res = "collection: [" + ",".join(dest) + "] - >" + asDict["UISource"] + "." + asDict["UILabel"]
	return res


def optimize(objectDump, allowed):
	# simplify NSString, NSColor, NSNumber
	oneLineValues = {}
	for id, d in sorted(objectDump.items()):
		tp = d[0]
		if not tp in allowed: continue
		values = d[1]
		res = optimizeSingleObject(objectDump, tp, values)
		if res != None: oneLineValues[id] = res

	# replace now in usages
	refCount = set()
	for id, d in sorted(objectDump.items()):
		values = d[1]
		for idx in range(len(values)):
			v = values[idx][1]
			if not isinstance(v, basestring) or not v.startswith("@"): continue
			if not v in oneLineValues: continue
			refCount.add(v)
			values[idx] = (values[idx][0], oneLineValues[v])

	# drop referenced
	for k in refCount:
		del objectDump[k]


def tryRemoveItem(id, objectDump, toRemove, removed, containers, inprogress=set()):
	# solve dependency by removing other items
	inprogress.add(id)
	tp = objectDump[id][0]
	values = objectDump[id][1]
	for idx in range(len(values)):
		v = values[idx][1]
		if not isinstance(v, basestring) or not v.startswith("@"): continue
		if not v in toRemove: continue
		# check for cycles
		if v in inprogress:
			raise Exception("Cycle reference when flatting down " + id + ",  following branch is problem " + v)
		if v in removed:
			res = objectDump[v][1]
		else:
			res = tryRemoveItem(v, objectDump, toRemove, removed, containers, inprogress)

		# removing dependency
		values[idx] = (values[idx][0], {v: res})

	inprogress.remove(id)
	removed.add(id)
	if tp in containers:
		objectDump[id][1] = optimizeSingleObject(objectDump, tp, values)
	else:
		objectDump[id][1] = varsToDict(values)
	return objectDump[id][1]


def embedObjects(objectDump, containers):
	# embedd data that has only one reference directly into objects
	# skip containers to allows objects jump inside container
	refCount = Counter()
	toRemove = set()
	for id, d in sorted(objectDump.items()):
		tp = d[0]
		values = d[1]
		# make sure object listed in these keys never embedded, so give them big refcount
		refValue = 1
		if tp in {"UINibObjectsKey", "UINibTopLevelObjectsKey"}: refValue = 100
		# also mark container to remove if it is removable
		if tp in containers and optimizeSingleObject(objectDump, tp, values) != None:
			toRemove.add(id)
		for idx in range(len(values)):
			v = values[idx][1]
			if not isinstance(v, basestring) or not v.startswith("@"): continue
			refCount[v] += refValue

	# get list of objects to be embedded (refCount == 1) altogether with containers
	for id, cnt in refCount.items():
		if cnt == 1: toRemove.add(id)

	# now move through removal list and remove items resolving dependencies
	removed = set()
	for id in toRemove:
		if id in removed: continue
		tryRemoveItem(id, objectDump, toRemove, removed, containers)

	# move through all removed and update ref
	for id, d in sorted(objectDump.items()):
		if id in removed: continue
		values = d[1]
		for idx in range(len(values)):
			v = values[idx][1]
			if not isinstance(v, basestring) or not v.startswith("@"): continue
			if not v in removed: continue
			values[idx] = (values[idx][0], objectDump[v][1])

	# remove now
	for id in removed:
		del objectDump[id]


def fancyPrintObjects2(objectDump):
	# find all UINibObjectsKey and rename them all just to have controlled names
	objRenameMap = {}
	tmp = varsToDict(objectDump["@0"][1])["UINibObjectsKey"]
	tmp = objectDump[tmp][1]  # it is NSArray of UINibObjectsKey
	for k, id in tmp:
		if k != "UINibEncoderEmptyKey": continue
		objRenameMap[id] = "@" + objectDump[id][0] + "[" + str(len(objRenameMap)) + "]"

	# replace ids to have object type in it
	for id, d in sorted(objectDump.items()):
		values = d[1]
		for idx in range(len(values)):
			v = values[idx][1]
			if not isinstance(v, basestring) or not v.startswith("@"): continue
			if v in objRenameMap:
				key = objRenameMap[v]
			else:
				key = v + "_" + objectDump[v][0]
			values[idx] = (values[idx][0], key)
	tmp = {}
	for id, d in sorted(objectDump.items()):
		if id in objRenameMap:
			key = objRenameMap[id]
		else:
			key = id + "_" + d[0]
		tmp[key] = d
	objectDump = tmp

	# group datas
	optimize(objectDump, {"NSString", "NSNumber"})
	optimize(objectDump, {"UIColor"})
	optimize(objectDump, {"UIButtonContent"})
	optimize(objectDump, {"UIProxyObject"})
	optimize(objectDump, {"NSValue"})
	optimize(objectDump, {"UINibKeyValuePair"})
	optimize(objectDump,
			 {"UIRuntimeEventConnection", "UIRuntimeOutletConnection", "UIRuntimeOutletCollectionConnection"})

	# embedd data that has only one reference directly into objects
	# skip containers to allows objects jump inside container
	containers = {"NSDictionary", "NSMutableDictionary", "NSArray", "NSMutableArray"}
	embedObjects(objectDump, containers)

	# covert all tuples in vars to dictionaries and replace type
	for id, d in sorted(objectDump.items()):
		objectDump[id] = varsToDict(d[1])

	print json.dumps(objectDump, sort_keys=True, indent=2, separators=(',', ': '))


def dumpHtmlHeader(html):
	header = \
		"""
		<html>
		<head>
		<style>
		.Container {display: flex; height: 100vh; position: relative; width: 100%; }
		.Left, .Middle {overflow: auto; height: auto;  padding: .5rem; }
		.Left {width: 30%;}
		.Middle {flex: 1; }
		table {font-family: monospace;}
		</style>
		</head>
		<script>
		
		var selOffset = -1
		var selSize = -1
		function selectOnTable(table, offset, size, color, scroll) {
			var row = (offset >> 4)
			var col = offset & 15
			if (scroll) {
				table.rows[row].cells[col + 1].scrollIntoView(true);
			}
			while (size > 0) {
				table.rows[row].cells[col + 1].style.backgroundColor = color;
				col += 1
				if (col > 15) {
					col = 0;
					row += 1;
				}
				size--;
			}
		}
		
		function Select(offset, size) {
			var table = document.getElementById('mytable');
			if (selSize  != -1) {
				// deselect old 
				selectOnTable(table, selOffset, selSize, 'FFFFFF', false)
			}
		
			selOffset = offset
			selSize = size
			selectOnTable(table, selOffset, selSize, '#EEEEA0', true)
		}
		
		</script>
		<body>
		<div class="Container">
		<div class="Left">
		<pre>"""
	print >> html, header


def dumpHtmlBytes(html, filebytes):
	print >> html, \
		"""
		</pre>
		</div>
		<div class="Middle">
		<table id='mytable'>
		"""
	# dump all bytes
	idx = 0
	while (idx < len(filebytes)):
		s = "<tr><td>" + '{:06X}'.format(idx) + "</td>"
		left = len(filebytes) - idx
		if left > 16: left = 16
		strv = ""
		for i in range(left):
			s += "<td>" + '{:02X}'.format(ord(filebytes[idx + i])) + "</td>"
			if ord(filebytes[idx + i]) >= 32:
				strv += filebytes[idx + i]
			else:
				strv += '.'
		s += "<td>" + strv + "</td>"
		s += "</tr>"
		print >> html, s
		idx += left

	print >> html, "</table>"
	print >> html, "</div>"
	print >> html, "</div>"
	print >> html, "</body>"
	print >> html, "</html>"


def ibdump(filename, showencoding=None):
	with open(filename, 'rb') as file:
		filebytes = file.read()

	pfx = filebytes[0:10]
	print "Prefix: " + pfx

	headers = filebytes[10:10+4]
	headers = rword(headers)
	print "Headers: " + str(headers)

	if str(pfx) != "NIBArchive":
		print "\"%s\" is not a NIBArchive file." % (filename)
		return

	nib = readNibSectionsFromBytes(filebytes)
	data = {}

	with open('fancyout.html', 'w') as html:
		dumpHtmlHeader(html)
		fancyPrintObjects(nib, showencoding=showencoding, objectDump=data, html=html)
		dumpHtmlBytes(html, filebytes)

	fancyPrintObjects2(data)


if __name__ == '__main__':
	ibdump(filename = sys.argv[1])