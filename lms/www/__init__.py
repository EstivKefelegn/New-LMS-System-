# your_app/www/__init__.py
import frappe

def get_base_context(context):
    """Add common context variables to all pages"""
    # Add categories for navigation
    context.categories = frappe.get_all(
        "LMS Category", 
        fields=["name", "category"], 
        order_by="name"
    )
    return context