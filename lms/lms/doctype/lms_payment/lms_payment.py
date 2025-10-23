# lms_payment.py
import frappe
from frappe.model.document import Document

class LMSPayment(Document):
    def before_save(self):
        # Auto-set payment_received based on certain conditions
        if self.payment_id and not self.payment_received:
            self.payment_received = 1
    
    def on_update(self):
        """Create invoice automatically when payment is marked as received"""
        if self.payment_received and not self.is_new():
            self.create_automated_invoice()
    
    def create_automated_invoice(self):
        """Automatically create invoice when payment is received"""
        try:
            # Check if invoice already exists for this payment
            existing_invoice = frappe.db.exists("LMS Invoice", {
                "payment_reference": self.name
            })
            
            if existing_invoice:
                frappe.msgprint(f"Invoice already exists: {existing_invoice}")
                return
            
            # Create invoice using the existing function
            from lms.lms.doctype.lms_invoice.lms_invoice import create_invoice_from_payment
            invoice_name = create_invoice_from_payment(self.name)
            
            frappe.msgprint(f"Auto-generated invoice: {invoice_name}")
            
        except Exception as e:
            frappe.log_error(f"Failed to auto-create invoice for payment {self.name}: {str(e)}")
            # Don't throw error to avoid blocking payment save

@frappe.whitelist()
def create_invoice_for_payment(payment_name):
    """API endpoint to manually create invoice for payment"""
    from lms.lms.doctype.lms_invoice.lms_invoice import create_invoice_from_payment
    return create_invoice_from_payment(payment_name)