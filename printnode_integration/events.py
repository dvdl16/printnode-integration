# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import json

import frappe
from frappe.utils import nowdate
from frappe.utils.background_jobs import enqueue
from frappe.utils.caching import redis_cache

from . import api


def print_via_printnode(doctype, docname, docevent):
	if frappe.flags.in_import or frappe.flags.in_patch or is_virtual_doctype(doctype):
		return
	if not frappe.db.exists(doctype, docname):
		enqueue(
			"printnode_integration.events.print_via_printnode",
			enqueue_after_commit=False,
			doctype=doctype,
			docname=docname,
			docevent=docevent,
		)

	doc = frappe.get_doc(doctype, docname)
	ignore_flags = True
	eval_globals = {"json": json}

	if not ignore_flags:
		if doc.flags.on_import or doc.flags.ignore_print:
			return

	if not frappe.db.exists("Print Node Action", {"dt": doc.doctype, "print_on": docevent}):
		return

	for d in frappe.db.get_all(
		"Print Node Action",
		["name", "ensure_single_print", "allow_inline_batch", "batch_field", "print_on_condition"],
		{"dt": doc.doctype, "print_on": docevent},
	):
		if (
			docevent in ["Update", "UpdateAfterSubmit"]
			and d.ensure_single_print
			and frappe.db.exists("Print Job", d.name)
		):
			continue
		if not d.allow_inline_batch:
			# validate condition
			# allow eval usage to use json in scripts: https://github.com/dvdl16/fssc_22000/issues/292
			# nosemgrep
			if d.print_on_condition and not eval(d.print_on_condition, eval_globals, get_context(doc)):
				continue
			api.print_via_printnode(d.name, doctype=doc.doctype, docname=doc.name)
		else:
			if "." in d.batch_field:
				table_field = d.batch_field.split(".")[0]
				reference_list = doc.get(table_field)
				if d.print_on_condition:
					# allow eval usage to use json in scripts: https://github.com/dvdl16/fssc_22000/issues/292
					# nosemgrep
					reference_list = [
						row for row in reference_list if eval(d.print_on_condition, eval_globals, get_context(row))
					]
			else:
				reference_list = [doc]
			inline_field = d.batch_field.split(".")[-1]
			api.batch_print_via_printnode(
				d.name,
				map(
					lambda d: frappe._dict(docname=d.get(inline_field), doctype=d.get("doctype")), reference_list
				),
			)


PRINT_ACTION_CACHE_KEY = "printnode_active_actions"


def _active_print_actions():
	"""Set of "<doctype>::<print_on>" pairs that have a Print Node Action.

	Cached in redis; rebuilt lazily and invalidated by
	clear_print_action_cache() whenever Print Node Settings (which owns the
	Action child table) is saved.
	"""
	actions = frappe.cache.get_value(PRINT_ACTION_CACHE_KEY)
	if actions is None:
		actions = {
			f"{d.dt}::{d.print_on}"
			for d in frappe.get_all("Print Node Action", fields=["dt", "print_on"])
			if d.dt and d.print_on
		}
		frappe.cache.set_value(PRINT_ACTION_CACHE_KEY, actions)
	return actions


def _enqueue_print(doc, docevent):
	# cheap redis set lookup; filters out the ~all doctypes with no action
	if f"{doc.doctype}::{docevent}" not in _active_print_actions():
		return
	if is_virtual_doctype(doc.doctype):
		return
	enqueue(
		"printnode_integration.events.print_via_printnode",
		enqueue_after_commit=True,
		doctype=doc.doctype,
		docname=doc.name,
		docevent=docevent,
		now=True,
	)


def clear_print_action_cache(doc=None, method=None):
	frappe.cache.delete_value(PRINT_ACTION_CACHE_KEY)


def after_insert(doc, handler=None):
	_enqueue_print(doc, "Insert")


def on_update(doc, handler=None):
	_enqueue_print(doc, "Update")


def on_update_after_submit(doc, handler=None):
	_enqueue_print(doc, "UpdateAfterSubmit")


def on_submit(doc, handler=None):
	_enqueue_print(doc, "Submit")


def on_trash(doc, handler=None):
	if not is_virtual_doctype(doc.doctype):
		settings = frappe.get_cached_doc("Print Node Settings", "Print Node Settings")
		if not settings.api_key or settings.allow_deletion_for_printed_documents:
			for print_job in frappe.get_all(
				"Print Node Job", fields=["name"], filters={"ref_type": doc.doctype, "ref_name": doc.name}
			):
				frappe.delete_doc("Print Node Job", print_job.name, ignore_permissions=True)


def get_context(doc):
	return {"doc": doc, "nowdate": nowdate, "frappe.utils": frappe.utils}


@redis_cache(ttl=86400)
def is_virtual_doctype(doctype):
	meta = frappe.get_meta(doctype)
	return meta.is_virtual
