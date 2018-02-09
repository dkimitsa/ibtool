#!/usr/bin/python

import sys
from collections import OrderedDict
from optparse import OptionParser
import ibdump

INDENT = "    "
MAX_DEEP_LEVEL = 2


def get_map_value(value_map, key, default):
    if key in value_map:
        return value_map[key]
    return default


def simplify_object_string(obj):
    # make single line simplification
    if obj.class_name == "NSLayoutConstraint":
        layout_attribute_map = {
            "1": "Left",
            "2": "Right",
            "3": "Top",
            "4": "Bottom",
            "5": "Leading",
            "6": "Trailing",
            "7": "Width",
            "8": "Height",
            "9": "CenterX",
            "10": "CenterY",
            "11": "Baseline",
            "12": "FirstBaseline",
            "13": "LeftMargin",
            "14": "RightMargin",
            "15": "TopMargin",
            "16": "BottomMargin",
            "17": "LeadingMargin",
            "18": "TrailingMargin",
            "19": "CenterXWithinMargins",
            "20": "CenterYWithinMargins"
        }
        first = obj.values["NSFirstItem"]
        first_attrib = obj.values["NSFirstAttribute"]
        if first_attrib in layout_attribute_map:
            first_attrib = layout_attribute_map[first_attrib]
        second = get_map_value(obj.values, "NSSecondItem", None)
        second_attrib = get_map_value(obj.values, "NSSecondAttribute", None)
        if second_attrib is not None and second_attrib in layout_attribute_map:
            second_attrib = layout_attribute_map[second_attrib]
        constant = float(get_map_value(obj.values, "NSConstant", 0.0))
        relation = int(get_map_value(obj.values, "NSRelation", 0))
        if relation < 0:
            relation = "<="
        elif relation > 0:
            relation = ">="
        else:
            relation = "="
        priority = get_map_value(obj.values, "NSPriority", 1000)
        multiplier = get_map_value(obj.values, "NSMultiplier", 1.0)

        res = first.obj.name + "." + first_attrib
        if second:
            res += " " + relation + " " + second.obj.name + "." + second_attrib
            if multiplier != 1.0:
                res += " * " + str(multiplier)
            if constant != 0.0:
                res += " "
                if constant >= 0.0:
                    res += "+"
                res += str(constant)
        else:
            res += " " + relation + " " + str(constant)
            if multiplier != 1.0:
                res += " * " + str(multiplier)
        if priority != 1000:
            res += " @" + str(priority)
        return obj.name + " { " + res + " }"

    elif obj.class_name in ["UINibKeyValuePair", "UIRuntimeOutletConnection", "UIRuntimeEventConnection",
                            "UIRuntimeOutletCollectionConnection"]:
        res = ""
        for key, v in obj.values.items():
            if isinstance(v, ClassEntryWrap):
                v = v.obj
            if isinstance(v, ClassEntry):
                v = "@" + v.name
            else:
                v = str(v)
            if len(res):
                res += ", "
            res += key + "=" + v
        return obj.name + " { " + res + " }"

    return None


class ClassEntry:
    def __init__(self, name, class_name, values):
        self.name = name
        self.class_name = class_name
        self.values = values

    def __str__(self):
        return self.name + ":" + self.class_name + "=" + str(self.values)


class ClassEntryWrap:
    def __init__(self, obj):
        self.obj = obj

    def __str__(self):
        return str(self.obj)


class FancyHtmlHexPrinter:
    def __init__(self, out=sys.stdout):
        self.out = out
        pass

    def dump_html_header(self):
        header = """
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
        print >> self.out, header

    def dump_html_bytes(self, file_bytes):
        print >> self.out, \
            """
            </pre>
            </div>
            <div class="Middle">
            <table id='mytable'>
            """
        # dump all bytes
        idx = 0
        while idx < len(file_bytes):
            s = "<tr><td>" + '{:06X}'.format(idx) + "</td>"
            left = len(file_bytes) - idx
            if left > 16:
                left = 16
            strv = ""
            for i in range(left):
                s += "<td>" + '{:02X}'.format(ord(file_bytes[idx + i])) + "</td>"
                if ord(file_bytes[idx + i]) >= 32:
                    strv += file_bytes[idx + i]
                else:
                    strv += '.'
            s += "<td>" + strv + "</td>"
            s += "</tr>"
            print >> self.out, s
            idx += left

        print >> self.out, "</table>"
        print >> self.out, "</div>"
        print >> self.out, "</div>"
        print >> self.out, "</body>"
        print >> self.out, "</html>"

    def fancy_print_objects(self, nib, prefix=""):
        objects, keys, values, classes = nib
        for o_idx, obj in enumerate(objects):
            # print object
            class_name, class_log = classes[obj[0]]
            obj_values = values[obj[1]:obj[1] + obj[2]]

            print >> self.out, prefix + "%3d: %s" % (o_idx, class_name)
            for v in obj_values:
                # print v
                k_str, k_log = keys[v[0]]
                v_str = str(v[1])
                v_log = v[3]

                if k_str == 'NS.bytes' and len(v_str) > 40 and v_str.startswith('NIBArchive'):
                    sub_nib = ibdump.readNibSectionsFromBytes(v[1])
                    self.fancy_print_objects(sub_nib, prefix + "    ")
                else:  # Boring regular data.
                    print >> self.out, prefix + '    ' + '<a href="#" onclick="Select(' + str(v_log[0]) + ', ' + str(
                        v_log[1]) + ')">' + k_str + ' =' + v_str + "</a>"

    def fancy_print(self, nib, file_bytes):
        self.dump_html_header()
        self.fancy_print_objects(nib)
        self.dump_html_bytes(file_bytes)


class FancyHtmlTreePrinter:
    HTML_HEADER = """
<html>
<head>
<style>
    ul.collapsibleList { position: relative; list-style: none; margin-left: 0; padding-left: 1.2em; }
    .collapsibleList li{ cursor : auto; }
    li.collapsibleList:before{ padding-right: 5px; position: absolute; left: 0;}
    li.collapsibleListOpen{}
    li.collapsibleListOpen:before{cursor: pointer; content: "\\2610"; padding-right: 5px; position: absolute; left: 0; }
    li.collapsibleListClosed{}
    li.collapsibleListClosed:before{cursor:pointer; content: "\\2612"; padding-right: 5px; position: absolute; left: 0;}
</style>
</head>

<script>
/*
CollapsibleLists.js
An object allowing lists to dynamically expand and collapse
Created by Kate Morley - http://code.iamkate.com/ - and released under the terms
of the CC0 1.0 Universal legal code:
http://creativecommons.org/publicdomain/zero/1.0/legalcode
*/
const CollapsibleLists = (function(){
  // Makes all lists with the class 'collapsibleList' collapsible. The
  // parameter is:
  //
  // doNotRecurse - true if sub-lists should not be made collapsible
  function apply(doNotRecurse){
    [].forEach.call(document.getElementsByTagName('ul'), node => {
      if (node.classList.contains('collapsibleList')){
        applyTo(node, true);
        if (!doNotRecurse){
          [].forEach.call(node.getElementsByTagName('ul'), subnode => {
            subnode.classList.add('collapsibleList')
          });
        }
      }
    })
  }

  // Makes the specified list collapsible. The parameters are:
  //
  // node         - the list element
  // doNotRecurse - true if sub-lists should not be made collapsible
  function applyTo(node, doNotRecurse){
    [].forEach.call(node.getElementsByTagName('li'), li => {
      if (!doNotRecurse || node === li.parentNode){
        // dkimitsa: commented out to allow text selection
        //li.style.userSelect       = 'none';
        //li.style.MozUserSelect    = 'none';
        //li.style.msUserSelect     = 'none';
        //li.style.WebkitUserSelect = 'none';
        li.addEventListener('click', handleClick.bind(null, li));
        toggle(li);
      }
    });
  }

  // Makes the specified list collapsible. The parameters are:
  //
  // node         - the list element
  // doNotRecurse - true if sub-lists should not be made collapsible
  function makeOpen(nodeId){
    li = document.getElementById(nodeId);
    animLi = li
    animLi.style.backgroundColor = 'yellow';
    var t = setTimeout(function(){
       animLi.style.backgroundColor = 'white';
    },600);
    while (li) {
        li = li.parentNode;
        if (li.nodeName == 'LI')
            switchState(li, open)
    }
  }

  // Handles a click. The parameter is:
  //
  // node - the node for which clicks are being handled
  function handleClick(node, e){
    // if there is any selection -- don't handle click to allow text copy 
    if (window.getSelection().toString().length > 0)
      return;

    let li = e.target;
    while (li.nodeName !== 'LI'){
      li = li.parentNode;
    }

    if (li === node){
      if (e.pageX > li.getBoundingClientRect().left)  
        return;
      toggle(node);
    }
  }

  // Opens or closes the unordered list elements directly within the
  // specified node. The parameter is:
  //
  // node - the node containing the unordered list elements
  function toggle(node){
    const open = node.classList.contains('collapsibleListClosed');
    switchState(node, open)
  }

  function switchState(node, open) {
    const uls  = node.getElementsByTagName('ul');
    [].forEach.call(uls, ul => {
      let li = ul;
      while (li.nodeName !== 'LI'){
        li = li.parentNode;
      }

      if (li === node){
        ul.style.display = (open ? 'block' : 'none');
      }
    });

    node.classList.remove('collapsibleListOpen');
    node.classList.remove('collapsibleListClosed');
    if (uls.length > 0){
      node.classList.add('collapsibleList' + (open ? 'Open' : 'Closed'));
    }
  }

  return {apply, applyTo, makeOpen};
})();

</script>
<body>
<ul class="collapsibleList">
    """

    HTML_FOOTER = """
</ul>
</body>
<script>
    CollapsibleLists.apply();
</script>
</html>
    """

    def __init__(self, objects, out=sys.stdout):
        self.objects = objects
        self.out = out
        self.objectsInStack = set()

        # build map of constraints
        self.objConstraints = {}
        # build map of outlets
        self.objOutlets = {}
        for idx in range(1, len(objects)):
            obj = self.objects[idx].obj
            if obj.class_name == "UIRuntimeOutletConnection":
                ref = obj.values["UISource"].obj
                if ref not in self.objOutlets:
                    self.objOutlets[ref] = []
                if obj not in self.objOutlets[ref]:
                    self.objOutlets[ref].append(obj)

                ref = obj.values["UIDestination"].obj
                if ref not in self.objOutlets:
                    self.objOutlets[ref] = []
                if obj not in self.objOutlets[ref]:
                    self.objOutlets[ref].append(obj)
            elif obj.class_name == "NSLayoutConstraint":
                ref = obj.values["NSFirstItem"].obj
                if ref not in self.objConstraints:
                    self.objConstraints[ref] = []
                if obj not in self.objConstraints[ref]:
                    self.objConstraints[ref].append(obj)

                if "NSSecondItem" in obj.values:
                    ref = obj.values["NSSecondItem"].obj
                    if ref not in self.objConstraints:
                        self.objConstraints[ref] = []
                    if obj not in self.objConstraints[ref]:
                        self.objConstraints[ref].append(obj)

    @staticmethod
    def build_click_code(item_name):
        return "<a href=\"#" + item_name + "\" onclick=\"CollapsibleLists.makeOpen('" + item_name + "')\">@</a>"

    def print_member(self, indent, level, key, v):
        if len(key):
            key = key + " = "
        if isinstance(v, ClassEntryWrap):
            v = v.obj

        if isinstance(v, basestring):
            print >> self.out, indent, "<li>" + key + v + "</li>"
        elif isinstance(v, list):
            if len(v):
                print >> self.out, indent, "<li>" + key + "["
                print >> self.out, indent + INDENT, "<ul>"
                item_indent = indent + INDENT + INDENT
                for listItem in v:
                    self.print_member(item_indent, level, "", listItem, )
                print >> self.out, indent + INDENT, "</ul>"
                print >> self.out, indent, "</li>"
            else:
                print >> self.out, indent, "<li>" + key + "[]" + "</li>"
        elif isinstance(v, dict):
            if len(v):
                print >> self.out, indent, "<li>" + key + "{"
                print >> self.out, indent + INDENT, "<ul>"
                item_indent = indent + INDENT + INDENT
                for dictKey, dictValue in v.items():
                    self.print_member(item_indent, level, dictKey, dictValue)
                print >> self.out, indent + INDENT, "</ul>"
                print >> self.out, indent, "</li>"
            else:
                print >> self.out, indent, "<li>" + key + "{}" + "</li>"

        elif isinstance(v, ClassEntry):
            simplified = simplify_object_string(v)
            has_simplified_desc = simplified != None
            if not simplified:
                # cant simplify, use name as ref
                simplified = v.name

            if has_simplified_desc or v in self.objectsInStack or not len(v.values) or level > MAX_DEEP_LEVEL:
                print >> self.out, indent, "<li>" + key + self.build_click_code(v.name) + simplified + "</li>"
            else:
                print >> self.out, indent, "<li>" + key + self.build_click_code(v.name) + simplified
                self.print_object(indent + INDENT, level + 1, v, False)
                print >> self.out, indent, "</li>"
        else:
            raise Exception("Unhandled value type " + str(type(v)))
            # print indent, key + ":"

    def print_object(self, indent, level, obj, print_title=True, print_id=False):
        if isinstance(obj, ClassEntryWrap):
            obj = obj.obj

        self.objectsInStack.add(obj)

        simplified_desc = simplify_object_string(obj)
        if simplified_desc is None:
            simplified_desc = obj.name

        # id to be inserted inside <li>
        obj_id_text = ""
        if print_id:
            obj_id_text = " id='" + obj.name + "'"

        if len(obj.values):
            # there are members, dump them
            if print_title:
                print >> self.out, indent + "<li" + obj_id_text + ">" + simplified_desc
            print >> self.out, indent + INDENT, "<ul>"
            member_indent = indent + INDENT + INDENT
            for key, v in sorted(obj.values.items()):
                self.print_member(member_indent, level, key, v)

            # dumps constraints if any
            if obj in self.objConstraints:
                self.print_member(member_indent, level, "*constraints", self.objConstraints[obj])
            # dump outlets if any
            if obj in self.objOutlets:
                self.print_member(member_indent, level, "*outlets", self.objOutlets[obj])

            print >> self.out, indent + INDENT, "</ul>"
            if print_title:
                print >> self.out, indent, "</li>"
        else:
            # empty object
            if print_title:
                print >> self.out, indent + "<li" + obj_id_text + ">" + simplified_desc + "</li>"

        self.objectsInStack.remove(obj)

    def dump_objects_in_type_groups(self):        # group objects by object classes
        obj_classes = {}
        for idx in range(1, len(self.objects)):
            obj = self.objects[idx].obj

            class_name = obj.class_name
            if class_name == "UIClassSwapper" and "UIClassName" in obj.values:
                class_name = obj.values["UIClassName"].obj
            if class_name in obj_classes:
                obj_list = obj_classes[class_name]
            else:
                obj_list = []
                obj_classes[class_name] = obj_list
            obj_list.append(obj)
        tmp = obj_classes
        obj_classes = OrderedDict()
        for key in sorted(tmp.keys()):
            obj_classes[key] = tmp[key]

        print >> self.out, INDENT + "<li>@ all objects by types ["
        print >> self.out, INDENT + "<ul>"

        for k, obj_list in obj_classes.items():
            print >> self.out, INDENT + INDENT + "<li>" + k + " ["
            print >> self.out, INDENT + INDENT + "<ul>"

            for o in obj_list:
                self.print_object(INDENT + INDENT + INDENT, 0, o, print_id=True)

            print >> self.out, INDENT + INDENT + "</ul>"
            print >> self.out, INDENT + INDENT + "</il>"

        print >> self.out, INDENT + "</ul>"
        print >> self.out, INDENT + "</il>"

    def fancy_print(self):
        print >> self.out, FancyHtmlTreePrinter.HTML_HEADER
        # print structure of xib from POV of root object
        self.print_object(INDENT, 0, self.objects[0])

        # now dump all objects
        self.dump_objects_in_type_groups()

        print >> self.out, FancyHtmlTreePrinter.HTML_FOOTER


class FancyTxtPrinter:

    def __init__(self, out=sys.stdout):
        self.out = out

    def print_member(self, indent, key, v):
        if len(key):
            key = key + " = "
        if isinstance(v, ClassEntryWrap):
            v = v.obj
        if isinstance(v, basestring):
            print >> self.out, indent, key + v
        elif isinstance(v, list):
            if len(v):
                print >> self.out, indent, key + "["
                item_indent = indent + INDENT
                for listItem in v:
                    self.print_member(item_indent, "", listItem)
                print >> self.out, indent, "]"
            else:
                print >> self.out, indent, key + "[]"
        elif isinstance(v, dict):
            if len(v):
                print >> self.out, indent, key + "{"
                item_indent = indent + INDENT
                for dictKey, dictValue in v.items():
                    self.print_member(item_indent, dictKey, dictValue)
                print >> self.out, indent, "}"
            else:
                print >> self.out, indent, key + "{}"

        elif isinstance(v, ClassEntry):
            simplified = simplify_object_string(v)
            if simplified:
                print >> self.out, indent, key + simplified
            else:
                # cant simplify, just output as ref
                print >> self.out, indent, key + "@" + v.name
        else:
            raise Exception("Unhandled value type " + str(type(v)))
            # print indent, key + ":"

    def print_obj(self, indent, obj):
        if len(obj.values):
            # there are members, dump them
            print >> self.out, indent, obj.name + " {"
            member_indent = indent + INDENT
            for key, v in obj.values.items():
                self.print_member(member_indent, key, v)
            print >> self.out, indent, "}"
        else:
            # empty object
            print >> self.out, indent, obj.name + "{}"

    def fancy_print(self, objects):
        # group objects by object classes
        obj_classes = {}
        for idx in range(1, len(objects)):
            obj = objects[idx].obj
            if obj.class_name in obj_classes:
                obj_list = obj_classes[obj.class_name]
            else:
                obj_list = []
                obj_classes[obj.class_name] = obj_list
            obj_list.append(obj)
        tmp = obj_classes
        obj_classes = OrderedDict()
        for key in sorted(tmp.keys()):
            obj_classes[key] = tmp[key]

        print >> self.out, "root:"
        self.print_obj(INDENT, objects[0].obj)
        for k, obj_list in obj_classes.items():
            print >> self.out, k + ":"
            for o in obj_list:
                self.print_obj(INDENT, o)


class FancyPrinter:
    def __init__(self):
        pass

    # helper converts variables list to dictionart
    @staticmethod
    def vars_to_dict(var_list):
        vals_key_cnt = {}
        res = OrderedDict()
        for key, v in var_list:
            if key not in vals_key_cnt:
                res[key] = v
                vals_key_cnt[key] = 1
            else:
                if key in res:
                    res[key + "[0]"] = res[key]
                    del res[key]
                res[key + "[" + str(vals_key_cnt[key]) + "]"] = v
                vals_key_cnt[key] = vals_key_cnt[key] + 1
        return res

    # helper that builds uniq names for objects
    @staticmethod
    def make_name_for_type(used_names, type_name):
        if type_name not in used_names:
            used_names[type_name] = 1
            return type_name + "1"
        else:
            idx = used_names[type_name] + 1
            used_names[type_name] = idx
            return type_name + str(idx)

    # def get list of object
    @staticmethod
    def build_objects(nib):
        result = []
        map_ref_to_result = {}
        used_names = {}

        objects, keys, values, classes = nib
        for o_idx, obj in enumerate(objects):
            # print object
            classname, classlog = classes[obj[0]]
            obj_values = values[obj[1]:obj[1] + obj[2]]
            vals = []
            for v in obj_values:
                # print v
                k_str, k_log = keys[v[0]]
                v_str = str(v[1])
                vals.append((k_str, v_str))
            wrap = ClassEntryWrap(ClassEntry(FancyPrinter.make_name_for_type(used_names, classname), classname,
                                             FancyPrinter.vars_to_dict(vals)))
            map_ref_to_result["@" + str(o_idx)] = wrap
            result.append(wrap)

        # resolve all references in objects
        for wrap in result:
            obj = wrap.obj
            resolved_values = OrderedDict()
            for v_key, v_value in obj.values.items():
                if isinstance(v_value, basestring) and v_value.startswith("@"):
                    resolved_values[v_key] = map_ref_to_result[v_value]
                else:
                    resolved_values[v_key] = v_value
            obj.values = resolved_values

        return result, used_names

    @staticmethod
    def optimize_single_primitive(obj):
        if obj.class_name == "NSString":
            if "NS.bytes" in obj.values:
                return obj.values["NS.bytes"]
        elif obj.class_name == "NSNumber":
            if len(obj.values) == 1:
                return obj.values.values()[0]
        elif obj.class_name == "UIProxyObject":
            if len(obj.values) == 1 and "UIProxiedObjectIdentifier" in obj.values:
                return "proxy: " + obj.values["UIProxiedObjectIdentifier"].obj
        elif obj.class_name == "NSArray" or obj.class_name == "NSMutableArray":
            res = []
            for key, v in obj.values.items():
                if key == "NSInlinedValue":
                    continue
                if not key.startswith("UINibEncoderEmptyKey"):
                    # not expected, don't convert
                    res = None
                    break
                res.append(v)
            return res
        elif obj.class_name == "NSDictionary" or obj.class_name == "NSMutableDictionary":
            res = OrderedDict()
            idx = 0
            dict_items = obj.values.items()
            while idx < len(dict_items):
                key, v = dict_items[idx]
                if key.startswith("UINibEncoderEmptyKey"):
                    if idx + 1 < len(dict_items):
                        entry_k = v.obj
                        entry_v = dict_items[idx + 1][1].obj
                        # key value has to be already optimized to string
                        assert isinstance(entry_k, basestring)
                        res[entry_k] = entry_v
                        idx += 2
                    else:
                        # not expected, don't convert
                        res = None
                        break
                else:
                    if key != "NSInlinedValue":
                        res[key] = v
                    idx += 1
            return res

    # noinspection PyUnresolvedReferences,PyTypeChecker
    @staticmethod
    def optimize_primitives(objects, allowed):
        result = []
        for wrap in objects:
            obj = wrap.obj
            optimized = None
            if obj.class_name in allowed:
                optimized = FancyPrinter.optimize_single_primitive(obj)
            if optimized is not None:
                # replace and don't add it to list (e.g. remove)
                wrap.obj = optimized
            else:
                result.append(wrap)
        return result

    @staticmethod
    def optimize_class_swappers(objects, used_names):
        for o in objects:
            if o.obj.class_name == "UIClassSwapper" and "UIClassName" in o.obj.values:
                o.obj.name = FancyPrinter.make_name_for_type(used_names, o.obj.values["UIClassName"].obj)

    @staticmethod
    def fancy_print(nib, file_bytes, nib_filename, options):
        objects, used_names = FancyPrinter.build_objects(nib)
        objects = FancyPrinter.optimize_primitives(objects, {"NSString", "NSNumber"})
        objects = FancyPrinter.optimize_primitives(objects, {"NSDictionary", "NSMutableDictionary", "NSArray",
                                                             "NSMutableArray"})
        objects = FancyPrinter.optimize_primitives(objects, {"UIProxyObject"})

        # now can update class swapper names to their class names
        FancyPrinter.optimize_class_swappers(objects, used_names)

        if options.textMode:
            printer = FancyTxtPrinter()
            printer.fancy_print(objects)

        if options.htmlFile is not None:
            html_filename = options.htmlFile
            if len(html_filename) == 0:
                html_filename = nib_filename + ".dump.html"
            with open(html_filename, 'w') as f:
                printer = FancyHtmlTreePrinter(objects, f)
                printer.fancy_print()

        if options.hexFile is not None:
            hex_filename = options.hexFile
            if len(hex_filename) == 0:
                hex_filename = nib_filename + ".hexdump.html"
            with open(hex_filename, 'w') as f:
                printer = FancyHtmlHexPrinter(f)
                printer.fancy_print(nib, file_bytes)


def dump(filename, options):
    with open(filename, 'rb') as f:
        file_bytes = f.read()

    pfx = file_bytes[0:10]
    print "Prefix: " + pfx

    headers = file_bytes[10:10 + 4]
    headers = ibdump.rword(headers)
    print "Headers: " + str(headers)

    if str(pfx) != "NIBArchive":
        print "\"%s\" is not a NIBArchive file." % filename
        return

    nib = ibdump.readNibSectionsFromBytes(file_bytes)
    FancyPrinter.fancy_print(nib, file_bytes, filename, options)


if __name__ == '__main__':
    parser = OptionParser(usage="usage: %prog [options] file.nib")
    parser.add_option("-t", action="store_true", dest="textMode", help="Produces text dump")
    parser.add_option("--html", dest="htmlFile", help="Produces html object tree dump to file")
    parser.add_option("--hex", dest="hexFile", help="Produces html object to hex dump to file")
    (opts, args) = parser.parse_args()
    if len(args) != 1:
        parser.print_help()
        sys.exit(-1)

    dump(args[0], opts)
