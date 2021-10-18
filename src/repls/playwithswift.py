#!/usr/bin/env python3

from swiftclient.service import SwiftService

with SwiftService() as swift:
    list_parts_gen = swift.list(container='helios')
    for page in list_parts_gen:
        print(page)
    