import frappe
from frappe.utils import nowdate, get_url

def create_invoice_for_payment(doc, method):
    """Create LMS Invoice after a payment is completed."""
    try:
        doc.reload()

        # Only create invoice if payment is received
        if not doc.get("payment_received"):
            return

        # Prevent duplicate invoices
        if frappe.db.exists("LMS Invoice", {"payment_reference": doc.name}):
            return

        # Create invoice
        invoice = frappe.get_doc({
            "doctype": "LMS Invoice",
            "invoice_number": frappe.generate_hash(length=10),
            "customer": doc.member,
            "amount": doc.amount,
            "payment_reference": doc.name,
            "payment_for": doc.payment_for_document,
            "invoice_date": nowdate(),
            "status": "Paid"
        })

        invoice.insert(ignore_permissions=True)

        # Submit if submittable
        if invoice.meta.is_submittable:
            invoice.submit()

        # Return URL for invoice page
        doc.invoice_url = get_url(f"/lms/billing/course/{doc.payment_for_document}/invoice")
        doc.save(ignore_permissions=True)


        frappe.logger().info(f"✅ LMS Invoice created: {invoice.name}")

    except Exception as e:
        frappe.log_error(f"Invoice creation failed for payment {doc.name}: {str(e)}",
                         "LMS Invoice Creation Failed")
