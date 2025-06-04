# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import frappe


def execute():
	"""
	For all Print Node Actions, if 'is_raw_text' is 0, set 'apply_letter_head' to 1
	"""
	frappe.reload_doctype("Print Node Action")

	frappe.db.sql("UPDATE `tabPrint Node Action` SET apply_letter_head = 1 WHERE is_raw_text = 0")
	frappe.db.commit()
