# lms_invoice.py
import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, add_days, getdate, flt

# In lms_invoice.py - update the LMSInvoice class
class LMSInvoice(Document):
    def before_save(self):
        self.set_invoice_number()
        self.calculate_totals()
        self.set_due_date()
    
    def set_invoice_number(self):
        # Autoname will handle this via "INV-.YYYY.-.MM.-.#####"
        if not self.invoice_number:
            self.invoice_number = self.name
    
    def calculate_totals(self):
        # Calculate total amount including tax
        self.tax_amount = flt(self.tax_amount or 0)
        self.total_amount = flt(self.amount or 0) + self.tax_amount
    
    def set_due_date(self):
        if not self.due_date:
            # Set due date to 30 days from invoice date
            self.due_date = add_days(getdate(self.invoice_date), 30)
    
    def validate(self):
        self.validate_payment_reference()
        self.validate_course_pricing()
    
    def validate_payment_reference(self):
        if self.payment_reference and not frappe.db.exists("LMS Payment", self.payment_reference):
            frappe.throw(f"Payment Reference {self.payment_reference} does not exist")
    
    def validate_course_pricing(self):
        if self.course and not self.amount:
            course_price = frappe.db.get_value("LMS Course", self.course, "course_price")
            if course_price:
                self.amount = course_price
    
    def on_submit(self):
        """When invoice is submitted, create enrollment and update payment"""
        if self.status == "Paid":
            self.create_course_enrollment()
            self.update_payment_status()
    
    def on_cancel(self):
        """When invoice is cancelled, update related records"""
        self.update_payment_status_on_cancel()
    
    def update_payment_status(self):
        """Update the linked LMS Payment record to mark as received"""
        if self.payment_reference:
            try:
                frappe.db.set_value("LMS Payment", self.payment_reference, "payment_received", 1)
                frappe.db.commit()
                frappe.msgprint(f"Payment {self.payment_reference} marked as received")
            except Exception as e:
                frappe.log_error(f"Failed to update payment status: {str(e)}")
    
    def update_payment_status_on_cancel(self):
        """Revert payment status when invoice is cancelled"""
        if self.payment_reference:
            try:
                frappe.db.set_value("LMS Payment", self.payment_reference, "payment_received", 0)
                frappe.db.commit()
                frappe.msgprint(f"Payment {self.payment_reference} status reverted")
            except Exception as e:
                frappe.log_error(f"Failed to revert payment status: {str(e)}")
    
    def create_course_enrollment(self):
        """Create LMS Enrollment when invoice is submitted and paid"""
        if self.course and self.customer:
            try:
                # Check if enrollment already exists
                enrollment_filters = {
                    "member": self.customer,
                    "course": self.course
                }
                
                enrollment_name = frappe.db.exists("LMS Enrollment", enrollment_filters)
                
                if enrollment_name:
                    # Update existing enrollment - ONLY set payment field
                    frappe.db.set_value("LMS Enrollment", enrollment_name, "payment", self.payment_reference)
                    frappe.msgprint(f"Updated existing enrollment {enrollment_name} with payment reference")
                else:
                    # Create new enrollment with only existing fields
                    enrollment_data = {
                        "doctype": "LMS Enrollment",
                        "member": self.customer,
                        "course": self.course,
                        "payment": self.payment_reference
                    }
                    
                    enrollment = frappe.get_doc(enrollment_data)
                    enrollment.insert(ignore_permissions=True)
                    frappe.msgprint(f"Created new enrollment {enrollment.name}")
                
                frappe.db.commit()
                
            except Exception as e:
                frappe.log_error(f"Failed to create/update enrollment: {str(e)}")
                frappe.msgprint(f"Warning: Could not create enrollment: {str(e)}", alert=True)
@frappe.whitelist()
def create_invoice_for_course_enrollment(course, member, amount, payment_method=None):
    """Create complete payment and invoice flow for course enrollment"""
    try:
        # Create LMS Payment first
        payment_data = {
            "doctype": "LMS Payment",
            "member": member,
            "payment_for_document_type": "LMS Course",
            "payment_for_document": course,
            "amount": amount,
            "currency": "INR",  # Default currency
            "payment_received": 1,
            "billing_name": frappe.db.get_value("User", member, "full_name"),
        }
        
        if payment_method:
            payment_data["source"] = payment_method
        
        payment = frappe.get_doc(payment_data)
        payment.insert(ignore_permissions=True)
        
        # Auto-create invoice
        invoice_name = create_invoice_from_payment(payment.name)
        
        return {
            "success": True,
            "payment": payment.name,
            "invoice": invoice_name
        }
        
    except Exception as e:
        frappe.log_error(f"Course enrollment invoice creation failed: {str(e)}")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def auto_create_invoices_for_completed_payments():
    """Bulk create invoices for all completed payments without invoices"""
    try:
        # Find payments that are received but don't have invoices
        payments_without_invoices = frappe.db.sql("""
            SELECT lp.name 
            FROM `tabLMS Payment` lp
            LEFT JOIN `tabLMS Invoice` li ON li.payment_reference = lp.name
            WHERE lp.payment_received = 1 
            AND li.name IS NULL
            AND lp.payment_for_document_type = 'LMS Course'
        """, as_dict=True)
        
        results = []
        for payment in payments_without_invoices:
            try:
                invoice_name = create_invoice_from_payment(payment.name)
                results.append({
                    "payment": payment.name,
                    "invoice": invoice_name,
                    "status": "Success"
                })
            except Exception as e:
                results.append({
                    "payment": payment.name,
                    "invoice": None,
                    "status": f"Failed: {str(e)}"
                })
        
        return {
            "total_processed": len(payments_without_invoices),
            "results": results
        }
        
    except Exception as e:
        frappe.log_error(f"Bulk invoice creation failed: {str(e)}")
        return {"success": False, "error": str(e)}
    
    
@frappe.whitelist()
def create_invoice_from_payment(payment_name):
    """Create invoice automatically from LMS Payment"""
    try:
        payment = frappe.get_doc("LMS Payment", payment_name)
        
        # Check if invoice already exists for this payment
        existing_invoice = frappe.db.exists("LMS Invoice", {"payment_reference": payment_name})
        if existing_invoice:
            frappe.msgprint(f"Invoice already exists: {existing_invoice}")
            return existing_invoice
        
        invoice_data = {
            "doctype": "LMS Invoice",
            "customer": payment.member,
            "payment_reference": payment_name,
            "invoice_date": nowdate(),
            "status": "Paid" if payment.payment_received else "Draft"
        }
        
        # Populate from payment details
        if payment.order_id:
            invoice_data["order_id"] = payment.order_id
        if payment.payment_id:
            invoice_data["payment_id"] = payment.payment_id
        if payment.currency:
            invoice_data["currency"] = payment.currency
        if payment.amount:
            invoice_data["amount"] = payment.amount
        if payment.billing_name:
            invoice_data["billing_name"] = payment.billing_name
        if payment.address:
            invoice_data["address"] = payment.address
        if payment.gstin:
            invoice_data["gstn"] = payment.gstin
        if payment.pan:
            invoice_data["pan"] = payment.pan
        
        # Set payment_for and course based on payment document
        if payment.payment_for_document_type == "LMS Course":
            invoice_data["course"] = payment.payment_for_document
            course_title = frappe.db.get_value("LMS Course", payment.payment_for_document, "title")
            invoice_data["payment_for"] = f"Course Enrollment: {course_title}"
        elif payment.payment_for_document_type == "LMS Batch":
            batch_title = frappe.db.get_value("LMS Batch", payment.payment_for_document, "title")
            invoice_data["payment_for"] = f"Batch Enrollment: {batch_title}"
        
        invoice = frappe.get_doc(invoice_data)
        invoice.insert(ignore_permissions=True)
        
        frappe.msgprint(f"Invoice {invoice.name} created successfully")
        
        # Auto-submit if payment is already received
        if payment.payment_received:
            invoice.submit()
        
        frappe.db.commit()
        return invoice.name
        
    except Exception as e:
        frappe.log_error(f"Failed to create invoice from payment {payment_name}: {str(e)}")
        frappe.throw(f"Failed to create invoice: {str(e)}")    