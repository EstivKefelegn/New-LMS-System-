# your_app/www/contact.py
import frappe
from . import get_base_context

def get_context(context):
    # Disable CSRF for this page
    frappe.local.flags.ignore_csrf = True
    
    # Base context
    context = get_base_context(context)

    # Contact Info
    contact_settings = frappe.get_single("Contact Us Settings")
    context.heading = getattr(contact_settings, "heading", "")
    context.email = getattr(contact_settings, "email_id", "")
    context.phone = getattr(contact_settings, "phone", "")
    context.address = getattr(contact_settings, "address_title", "")
    context.support_hours = getattr(contact_settings, "introduction", "")

    # FAQs
    context.faqs = frappe.get_all(
        "Faq",
        filters={"published": 1},
        fields=["question", "answer"],
        order_by="name asc"
    )

    # Handle form POST submission
    if frappe.local.request.method == "POST":
        first_name = frappe.form_dict.get("firstName", "").strip()
        last_name = frappe.form_dict.get("lastName", "").strip()
        email_address = frappe.form_dict.get("email", "").strip()
        subject = frappe.form_dict.get("subject", "").strip()
        message = frappe.form_dict.get("message", "").strip()

        print(f"🔵 Form Data - First: {first_name}, Last: {last_name}, Email: {email_address}, Subject: {subject}")

        # Validation
        if first_name and email_address and message:
            try:
                print("🟢 Validation passed, creating Communication document...")
                
                # Create full name
                full_name = f"{first_name} {last_name}".strip()
                
                # Create Communication document
                comm_doc = frappe.get_doc({
                    "doctype": "Communication",
                    "subject": f"Contact Form: {subject}",
                    "content": f"""
Name: {full_name}
Email: {email_address}
Subject: {subject}

Message:
{message}
                    """,
                    "sender": email_address,
                    "sender_full_name": full_name,
                    "sent_or_received": "Received",
                    "communication_type": "Communication",
                    "communication_medium": "Email",
                    "status": "Open"
                })
                
                comm_doc.insert(ignore_permissions=True)
                frappe.db.commit()
                
                print(f"🟢 Communication created successfully: {comm_doc.name}")
                context.success_message = "Thank you! Your message has been submitted successfully."
                
            except Exception as e:
                frappe.db.rollback()
                error_msg = f"Error saving contact form: {str(e)}"
                print(f"🔴 ERROR: {error_msg}")
                frappe.log_error(error_msg, "Contact Form Error")
                context.error_message = "Oops! Something went wrong. Please try again."
        else:
            context.error_message = "Please fill all required fields."

    return context