// Copyright (c) 2020, MaxMorais and contributors
// For license information, please see license.txt

frappe.ui.form.on('Short URL', {
	setup: function(frm) {
    if(!frm.doc.__islocal && frm.doc.docstatus == 1){
      window.location.href = frm.doc.url;
	  }
  }
});
