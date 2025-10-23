// // Copyright (c) 2023, Frappe and contributors
// // For license information, please see license.txt

// frappe.ui.form.on("LMS Payment", {
// 	onload(frm) {
// 		frm.set_query("member", function (doc) {
// 			return {
// 				filters: {
// 					ignore_user_type: 1,
// 				},
// 			};
// 		});
// 	},
// });


// lms_payment.js
frappe.ui.form.on('LMS Payment', {
    refresh: function(frm) {
        // Add button to create invoice if not exists
        if (frm.doc.payment_received && !frm.is_new()) {
            frappe.db.get_value('LMS Invoice', { 'payment_reference': frm.doc.name }, 'name')
                .then(r => {
                    if (!r.message.name) {
                        frm.add_custom_button(__('Create Invoice'), function() {
                            frm.trigger('create_invoice');
                        });
                    } else {
                        frm.add_custom_button(__('View Invoice'), function() {
                            frappe.set_route('Form', 'LMS Invoice', r.message.name);
                        });
                    }
                });
        }
        
        // Add bulk action in list view
        if (frm.is_list) {
            frm.page.add_menu_item(__('Create Invoices for Completed Payments'), function() {
                frappe.call({
                    method: 'lms.lms.doctype.lms_invoice.lms_invoice.auto_create_invoices_for_completed_payments',
                    callback: function(r) {
                        if (r.message) {
                            let msg = `Processed ${r.message.total_processed} payments:\n\n`;
                            r.message.results.forEach(result => {
                                msg += `• ${result.payment}: ${result.status}\n`;
                            });
                            frappe.msgprint(msg);
                            frm.refresh();
                        }
                    }
                });
            });
        }
    },
    
    payment_received: function(frm) {
        // Auto-create invoice when payment received is checked
        if (frm.doc.payment_received && !frm.is_new()) {
            setTimeout(() => {
                frappe.show_alert({
                    message: __('Invoice will be auto-generated for this payment'),
                    indicator: 'green'
                });
            }, 1000);
        }
    },
    
    create_invoice: function(frm) {
        frappe.call({
            method: 'lms.lms.doctype.lms_payment.lms_payment.create_invoice_for_payment',
            args: {
                payment_name: frm.doc.name
            },
            callback: function(r) {
                if (r.message) {
                    frappe.msgprint({
                        title: __('Success'),
                        indicator: 'green',
                        message: __('Invoice created successfully')
                    });
                    frm.refresh();
                }
            }
        });
    }
});