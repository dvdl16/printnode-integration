# -*- coding: utf-8 -*-

import json
import re
from base64 import b64decode, b64encode

import frappe
from frappe import _
from frappe.utils import get_url, now_datetime
from pymysql import OperationalError

try:
	from frappe.utils.file_manager import get_file
except ImportError:
	from frappe.core.doctype.file.file import download_file

	def get_file(file_url):
		download_file(file_url)
		file_content = frappe.response.file_content
		del frappe.local.response.file_content
		del frappe.local.response.file_name
		del frappe.local.response.type
		return [file_url, file_content]


from frappe.utils.jinja import render_template

# from xmlescpos.escpos import Escpos, StyleStack
from pdfkit.pdfkit import PDFKit
from six import string_types

# try:
# from cStringIO import StringIO
# except ImportError:
# from StringIO import StringIO

try:
	from printnodeapi.Gateway import Gateway
except ImportError:
	from printnodeapi.gateway import Gateway

# class IOPrinter(Escpos):
# def __init__(self):
# self.slip_sheet_mode = False
# self.io = StringIO()
# self.stylestack = StyleStack()

# def _raw(self, msg):
# self.io.write(msg)

# def get_content(self):
# return self.io.getvalue()


class PDFKit(PDFKit):
	def to_image(self, path):
		try:
			return self.to_pdf(path)
		except UnicodeDecodeError as e:
			pass


class Configuration(object):
	pass


def get_print_content(print_format, doctype, docname, is_escpos=False, is_raw=False):
	if is_escpos or is_raw:
		doc = frappe.get_doc(doctype, docname)
		content_field = "html"
		if frappe.db.get_value("Print Format", print_format, "raw_printing"):
			content_field = "raw_commands"
		template = frappe.db.get_value("Print Format", print_format, content_field)

		# Parse JSON if docfields are of type "Code"
		meta = frappe.get_meta(doctype)
		for code_field in meta.get_code_fields():
			if code_field.options == "JSON":
				string = getattr(doc, code_field.fieldname, "{}")
				parsed_dict = json.loads(string) if string else {}
				setattr(doc, code_field.fieldname, parsed_dict)

		content = render_template(template, {"doc": doc})
		if is_escpos:
			content.replace("<br>", "<br/>")
	else:
		# If doctype has a 'language' field, use it to translate the content
		lang_field = frappe.get_meta(doctype).get_field("language")
		lang = frappe.db.get_value(doctype, docname, lang_field.fieldname) if lang_field else None
		result_content = frappe.attach_print(doctype, docname, print_format=print_format, lang=lang)
		content = result_content["fcontent"]

	if is_escpos:
		frappe.throw(_("Escpos is not supported"))
	elif is_raw:
		raw = content.encode()
	else:
		raw = content

	# frappe.msgprint("<pre>%s</pre>" %raw)

	return b64encode(raw)


@frappe.whitelist()
def print_via_printnode(action, **kwargs):
	settings = frappe.get_doc("Print Node Settings", "Print Node Settings")
	if not settings.api_key:
		frappe.throw(_("Your Print Node API Key is not configured in Print Node Settings"))
	if not frappe.db.exists("Print Node Action", action):
		frappe.throw(_("Unable to find an action in Print settings to execute this print"))
	else:
		action = frappe.get_doc("Print Node Action", action)
		if not kwargs.get("doctype") and action.get("print_format"):
			kwargs["doctype"] = frappe.db.get_value("Print Format", action.print_format, "doc_type")

	if action.get("capabilities"):
		print_settings = json.loads(action.capabilities)
	else:
		print_settings = {}

	if "collate" in print_settings:
		print_settings["collate"] = bool(print_settings["collate"])

	printer_name = action.printer

	# If a specific printer is defined for this user for this action, rather use this printer
	user_printer = frappe.db.get_value(
		"Print Node Settings User",
		{"print_node_action": action.name, "user": frappe.session.user},
		"default_printer",
	)
	if user_printer:
		printer_name = user_printer
	else:
		# If a specific printer is defined for the linked location for this action, rather use this printer
		if kwargs.get("doctype") == "Stock Entry Detail":
			location_name = get_work_order_linked_location(kwargs.get("docname"))
			if location_name:
				location_printer = frappe.db.get_value(
					"Print Node Settings Location",
					{"print_node_action": action.name, "location": location_name},
					"default_printer",
				)
				if location_printer:
					printer_name = location_printer

	printer = frappe.db.get_value("Print Node Hardware", printer_name, "hw_id")

	gateway = Gateway(apikey=settings.api_key)

	if action.printable_type == "Print Format":
		print_content = get_print_content(
			action.print_format if not action.use_standard else "Standard",
			kwargs.get("doctype"),
			kwargs.get("docname"),
			action.is_xml_esc_pos,
			action.is_raw_text,
		)
		raw = action.is_xml_esc_pos or action.is_raw_text
		gateway.PrintJob(
			printer=int(printer),
			job_type="raw" if raw else "pdf",
			title=action.action + " (" + kwargs.get("doctype") + ": " + kwargs.get("docname") + ")",
			base64=print_content.decode("utf-8"),
			options=print_settings,
		)
	else:
		file_name, file_content = get_file(kwargs.get("filename"))
		print_content = b64encode(file_content)
		gateway.PrintJob(
			printer=int(printer),
			job_type="pdf" if file_name.lower().endswith(".pdf") else "raw",
			base64=print_content.decode("utf-8"),
			options=print_settings,
			title=f'PrintJob ({kwargs.get("doctype")}: {kwargs.get("docname")} | {file_name})',
		)

	job = frappe.new_doc("Print Node Job").update(
		{
			"print_node_action": action.name,
			"printer_id": action.printer,
			"print_type": "File" if action.printable_type == "Attachment" else "Print Format",
			"file_link": kwargs.get("filename"),
			"print_format": action.print_format if not action.use_standard else "Standard",
			"ref_type": kwargs.get("doctype"),
			"ref_name": kwargs.get("docname"),
			"is_xml_esc_pos": action.is_xml_esc_pos,
			"is_raw_text": action.is_raw_text,
			"print_job_name": action.action,
			"copies": print_settings.get("copies", 1),
			"job_owner": frappe.local.session.user,
			"print_timestamp": now_datetime(),
		}
	)
	# Try to extract info from raw ZPL
	if action.is_raw_text:
		raw_print_job_content = b64decode(print_content).decode("utf-8").strip()
		pattern = r"\^PQ(\d),0,1,Y\^XZ"
		result = re.search(pattern, raw_print_job_content)
		job.nr_of_labels = result.group(1) if result is not None else None
		if action.store_raw_print_job_content:
			job.raw_print_job_content = raw_print_job_content

	job.flags.ignore_permissions = True
	job.flags.ignore_links = True
	job.flags.ignore_validate = True
	job.insert()


@frappe.whitelist()
def batch_print_via_printnode(action, docs):
	if isinstance(docs, string_types):
		docs = json.loads(docs)

	for doc in docs:
		print_via_printnode(action, **doc)


@frappe.whitelist()
def get_action_list(dt):
	return frappe.get_all(
		"Print Node Action",
		fields=[
			"name",
			"action",
			"printable_type",
			"attachment_pattern",
			"depends_on",
			"allow_inline_batch",
			"batch_field",
			"hotkey",
		],
		filters={"dt": dt},
		order_by="idx ASC",
		limit_page_length=50,
	)


def shorten_url(content, return_docname=False):
	short_url = frappe.get_doc({"doctype": "Short URL", "url": content, "docstatus": 1})
	short_url.insert()
	if return_docname:
		content = short_url.name
	else:
		content = get_url() + "/desk#Form/Short%20URL/" + short_url.name
	return content


def get_work_order_linked_location(stock_entry_detail_name: str):
	try:
		result = frappe.db.sql(
			"""
			SELECT t_wo.sg_default_production_area
				FROM `tabStock Entry Detail` t_sed
				INNER JOIN `tabStock Entry` t_se
					ON t_se.name = t_sed.parent 
				INNER JOIN `tabWork Order` t_wo
					ON t_wo.name = t_se.work_order
				WHERE 
					t_sed.name = '{stock_entry_detail_name}'
					AND t_se.stock_entry_type = 'Manufacture';
		""".format(
				stock_entry_detail_name=stock_entry_detail_name
			),
			as_dict=True,
		)
		if len(result) == 0:
			return None
		return result[0]["sg_default_production_area"]
	except OperationalError as e:
		frappe.log_error(
			title=_("Error while retrieving linked location for Manufacture Stock Entry"),
			message=json.dumps(e.args),
		)
		return None
