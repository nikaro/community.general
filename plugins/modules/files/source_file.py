#!/usr/bin/python

from __future__ import absolute_import, division, print_function

import os
import re

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.parsing.convert_bool import BOOLEANS, boolean
from ansible.module_utils.six import string_types

__metaclass__ = type

DOCUMENTATION = """
module: source_file
short_description: Source remote bash/dotenv file
description:
  - This module register variables from a remote bash/dotenv-like file.
  - It handles boolean (`MY_VAR=1`).
  - It handles basic list (`MY_VAR=one,two,three`).
  - It handles basic dictionnary (`MY_VAR=a=1;b=2;c=3`).
author:
  - "Nicolas Karolak (@nikaro)"
options:
  path:
    description:
      - Path to the file to source.
    required: true
    type: path
  prefix:
    description:
      - Prefix to add to the registred variable name.
    required: false
    default: ""
    type: str
  lower:
    description:
      - Wether to lower or not the variable name.
    required: false
    default: false
    type: bool
"""

EXAMPLES = """
- name: source my conf
  register: my_conf
  source_file:
    path: /root/my_conf.sh
    lower: true

- name: show my conf
  debug:
    var: my_conf.vars
"""

RETURN = """
"""


def typed_value(value):
    # remove surrounding quotes
    if (
        isinstance(value, string_types)
        and (
            (value.startswith("'") and value.endswith("'"))
            or (value.startswith('"') and value.endswith('"'))
        )
    ):
        value = value[1:-1].strip()

    # handle list value
    if "," in value:
        value = [typed_value(i.strip()) for i in value.split(",")]

    # handle dict value
    if ";" in value and "=" in value:
        value_items = [typed_value(i.strip()) for i in value.split(";")]
        value = {}
        for item in value_items:
            key_item, value_item = (i.strip() for i in item.split("="))
            value.update({key_item: typed_value(value_item)})

    # handle bool value
    if isinstance(value, string_types) and value.lower() in BOOLEANS:
        value = boolean(value)

    return value


def main():
    module = AnsibleModule(
        argument_spec={
            "path": {"type": "path", "required": True},
            "prefix": {"type": "str", "required": False, "default": ""},
            "lower": {"type": "bool", "required": False, "default": False},
        },
        supports_check_mode=True,
    )

    result = {
        "changed": False,
    }

    path = module.params["path"]
    prefix = module.params["prefix"]
    lower = boolean(module.params["lower"])

    variables = {}

    key_pattern = "[a-zA-Z_][a-zA-Z0-9_-]*"
    regex_key = re.compile("^" + key_pattern + "$")
    regex_key_value = re.compile("^(?P<key>" + key_pattern + ")=(?P<value>.*)")

    if not os.path.isfile(path):
        module.fail_json(
            msg="'%s' does not exist or is not a file" % path, **result
        )

    if prefix and not regex_key.match(prefix):
        module.fail_json(
            msg="'%s' is not a valid prefix it must starts with a letter or"
            " underscore character, and contains only letters, numbers and"
            " underscores" % prefix,
            **result
        )

    with open(path) as file:
        for line in file:
            match = regex_key_value.match(line)

            # skip lines that are not assignation (comments, blank, code, etc.)
            if not match:
                continue

            # get key and value
            key = str(match.group("key")).strip()
            value = str(match.group("value")).strip()

            # merge prefix + key
            if prefix:
                key = "%s%s" % (prefix, key)

            # lower key
            if lower:
                key = key.lower()

            # check key validity
            if not regex_key.match(key):
                module.fail_json(
                    msg="'%s' is not a valid variable name it must starts with"
                    " a letter or underscore character, and contains only"
                    " letters, numbers and underscores" % key, **result
                )

            # parse value and apply correct type operations
            variables[key] = typed_value(value)

            if not module.check_mode:
                result["vars"] = variables

    module.exit_json(**result)


if __name__ == "__main__":
    main()
