# lms/api/custom_signup.py
import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def create_user(full_name, email, username, password, invite_code=None):
    try:
        # Check if user already exists
        if frappe.db.exists("User", email):
            return {"success": False, "message": _("User with this email already exists")}
        
        if frappe.db.get_value("User", {"username": username}):
            return {"success": False, "message": _("Username already taken")}
        
        # Create user WITHOUT email verification
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": full_name,
            "username": username,
            "new_password": password,
            "send_welcome_email": 0,
            "user_type": "Website User",
            "enabled": 1
        })
        
        user.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Auto-login the user
        frappe.local.login_manager.login_as(user.name)
        
        return {"success": True, "message": _("Account created successfully")}
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Custom Signup Error")
        return {"success": False, "message": str(e)}