// lms_invoice.js
frappe.ui.form.on('LMS Invoice', {
    setup: function(frm) {
        // Set up query for payment reference
        frm.set_query('payment_reference', function() {
            return {
                filters: {
                    'docstatus': 0  // Only show submitted payments if needed
                }
            };
        });
        
        // Set up query for course
        frm.set_query('course', function() {
            return {
                filters: {
                    'paid_course': 1
                }
            };
        });
    },
    
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            frm.add_custom_button(__('View Payment'), function() {
                if (frm.doc.payment_reference) {
                    frappe.set_route('Form', 'LMS Payment', frm.doc.payment_reference);
                }
            }, __('View'));
            
            frm.add_custom_button(__('Send Email'), function() {
                frm.trigger('send_invoice_email');
            }, __('Actions'));
            
            frm.add_custom_button(__('Print Invoice'), function() {
                frm.print_doc();
            }, __('Actions'));
        }
        
        frm.add_custom_button(__('Create from Payment'), function() {
            frm.trigger('create_from_payment');
        }, __('Create'));
        
        // Toggle display of payment details based on payment reference
        frm.toggle_display(['payment_details_section_section', 'order_id', 'payment_id', 'currency', 'section_break_fucm', 'billing_name', 'address', 'gstn', 'pan'], 
                          !!frm.doc.payment_reference);
    },
    
    payment_reference: function(frm) {
        if (frm.doc.payment_reference) {
            // Auto-populate details from payment
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'LMS Payment',
                    name: frm.doc.payment_reference
                },
                callback: function(r) {
                    if (r.message) {
                        let payment = r.message;
                        
                        // Map payment fields to invoice fields
                        let field_map = {
                            'member': 'customer',
                            'order_id': 'order_id',
                            'payment_id': 'payment_id', 
                            'currency': 'currency',
                            'amount': 'amount',
                            'billing_name': 'billing_name',
                            'address': 'address',
                            'gstin': 'gstn',  // Map gstin to gstn
                            'pan': 'pan'
                        };
                        
                        Object.keys(field_map).forEach(payment_field => {
                            let invoice_field = field_map[payment_field];
                            if (payment[payment_field] && !frm.doc[invoice_field]) {
                                frm.set_value(invoice_field, payment[payment_field]);
                            }
                        });
                        
                        // Set payment_for based on payment document
                        if (payment.payment_for_document_type && payment.payment_for_document) {
                            if (payment.payment_for_document_type === 'LMS Course') {
                                frm.set_value('course', payment.payment_for_document);
                                frappe.db.get_value('LMS Course', payment.payment_for_document, 'title')
                                    .then(r => {
                                        if (r.message.title) {
                                            frm.set_value('payment_for', `Course: ${r.message.title}`);
                                        }
                                    });
                            } else if (payment.payment_for_document_type === 'LMS Batch') {
                                frappe.db.get_value('LMS Batch', payment.payment_for_document, 'title')
                                    .then(r => {
                                        if (r.message.title) {
                                            frm.set_value('payment_for', `Batch: ${r.message.title}`);
                                        }
                                    });
                            }
                        }
                        
                        // Set status based on payment received
                        if (payment.payment_received && frm.doc.status === 'Draft') {
                            frm.set_value('status', 'Paid');
                        }
                        
                        frm.refresh_fields();
                    }
                }
            });
        } else {
            // Clear payment-related fields if payment reference is removed
            ['order_id', 'payment_id', 'billing_name', 'address', 'gstn', 'pan'].forEach(field => {
                frm.set_value(field, null);
            });
            frm.refresh_fields();
        }
    },
    
    amount: function(frm) {
        frm.trigger('calculate_total');
    },
    
    tax_amount: function(frm) {
        frm.trigger('calculate_total');
    },
    
    calculate_total: function(frm) {
        let amount = flt(frm.doc.amount) || 0;
        let tax = flt(frm.doc.tax_amount) || 0;
        frm.set_value('total_amount', amount + tax);
    },
    
    create_from_payment: function(frm) {
        let d = new frappe.ui.Dialog({
            title: __('Create Invoice from Payment'),
            fields: [
                {
                    label: __('Payment Reference'),
                    fieldname: 'payment',
                    fieldtype: 'Link',
                    options: 'LMS Payment',
                    reqd: 1,
                    get_query: function() {
                        return {
                            filters: {
                                'name': ['not in', frappe.db.get_list('LMS Invoice', { 
                                    fields: ['payment_reference'],
                                    filters: { 'payment_reference': ['is', 'set'] }
                                }).then(r => r.map(d => d.payment_reference))]
                            }
                        };
                    }
                }
            ],
            primary_action: function(data) {
                frappe.call({
                    method: 'lms.lms.doctype.lms_invoice.lms_invoice.create_invoice_from_payment',
                    args: {
                        payment_name: data.payment
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: __('Success'),
                                indicator: 'green',
                                message: __('Invoice {0} created successfully', [r.message])
                            });
                            frappe.set_route('Form', 'LMS Invoice', r.message);
                        }
                    }
                });
                d.hide();
            },
            primary_action_label: __('Create')
        });
        d.show();
    },
    
    send_invoice_email: function(frm) {
        if (!frm.doc.customer) {
            frappe.msgprint(__('Please select a customer first'));
            return;
        }
        
        frappe.call({
            method: 'frappe.core.doctype.communication.email.make',
            args: {
                recipients: frm.doc.customer,
                subject: `Invoice ${frm.doc.invoice_number} - ${frm.doc.payment_for}`,
                content: `Dear ${frm.doc.billing_name || 'Valued Customer'},<br><br>
Please find your invoice attached for your reference.<br><br>
<strong>Invoice Details:</strong><br>
• Invoice Number: ${frm.doc.invoice_number}<br>
• Invoice Date: ${frm.doc.invoice_date}<br>
• Due Date: ${frm.doc.due_date || 'N/A'}<br>
• Amount: ${frm.doc.currency} ${frm.doc.total_amount}<br>
• Payment For: ${frm.doc.payment_for}<br>
• Status: ${frm.doc.status}<br><br>
Thank you for your business!`,
                doctype: frm.doc.doctype,
                name: frm.doc.name,
                send_email: 1,
                print_format: 'Standard',
                attachments: [{
                    'print_format_attachment': 1,
                    'doctype': frm.doc.doctype,
                    'name': frm.doc.name,
                    'print_format': 'Standard'
                }]
            },
            callback: function(r) {
                if (r.message) {
                    frappe.msgprint({
                        title: __('Success'),
                        indicator: 'green', 
                        message: __('Invoice email sent successfully to {0}', [frm.doc.customer])
                    });
                }
            }
        });
    }
});

// List view settings
frappe.listview_settings['LMS Invoice'] = {
    onload: function(listview) {
        listview.page.add_menu_item(__('Create from Payment'), function() {
            let d = new frappe.ui.Dialog({
                title: __('Create Invoice from Payment'),
                fields: [
                    {
                        label: __('Payment'),
                        fieldname: 'payment',
                        fieldtype: 'Link',
                        options: 'LMS Payment',
                        reqd: 1
                    }
                ],
                primary_action: function(data) {
                    frappe.call({
                        method: 'lms.lms.doctype.lms_invoice.lms_invoice.create_invoice_from_payment',
                        args: {
                            payment_name: data.payment
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint(__('Invoice created successfully'));
                                listview.refresh();
                            }
                        }
                    });
                    d.hide();
                }
            });
            d.show();
        });
    },
    
    button: {
        show: function(doc) {
            return __("View");
        },
        action: function(doc) {
            frappe.set_route('Form', 'LMS Invoice', doc.name);
        }
    }
};