import frappe

from printnode_integration.api import shorten_url


def get_qr(content, scale, short_url=False, return_docname=False):
	import pyqrcode
	from io import BytesIO

	if short_url:
		content = shorten_url(content, return_docname)

	url = pyqrcode.create(content)
	stream = BytesIO()
	url.svg(stream, scale=scale)
	output = stream.getvalue(), 200, {
		'Content-Type': 'image/svg+xml',
		'Cache-Control': 'no-cache, no-store, must-revalidate',
		'Pragma': 'no-cache',
		'Expires': '0'}

	string = output[0].decode()
	start = string.find('<svg xmlns=')
	end = string.find('</svg>') + 6
	return(string[start:end])


def get_barcode(content, scale=15, short_url=False, type='code128'):
	import barcode
	from io import BytesIO

	if short_url:
		content = shorten_url(content, return_docname=True)

	bar = barcode.get_barcode_class(type)

	string = bar(content).render(
		writer_options =
			{'module_height': scale,
			'module_width': 0.3
			},
		text = ''
		).decode()

	start = string.find('<svg')
	end = string.find('</svg>') + 6
	return(string[start:end])