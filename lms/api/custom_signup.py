# lms/api/custom_signup.py
import frappe
from frappe import _
from frappe.utils.password import update_password
import time

@frappe.whitelist(allow_guest=True)
def create_user(full_name, email, username, password, invite_code=None):
    try:
        # Check if user already exists
        if frappe.db.exists("User", email):
            return {"success": False, "message": _("User with this email already exists")}
        
        if frappe.db.get_value("User", {"username": username}):
            return {"success": False, "message": _("Username already taken")}
        
        # Create user
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": full_name,
            "username": username,
            "send_welcome_email": 0,
            "user_type": "Website User",
            "enabled": 1
        })
        
        user.insert(ignore_permissions=True)
        
        # Set password using update_password
        update_password(user.name, password)
        
        # Force commit to ensure password is saved
        frappe.db.commit()
        
        # Small delay to ensure password is properly hashed and stored
        time.sleep(0.5)
        
        # Verify password works before auto-login
        from frappe.auth import check_password
        try:
            check_password(user.name, password)
        except Exception as e:
            frappe.log_error(f"Password verification failed for {user.name}: {str(e)}", "Signup Password Error")
            return {"success": False, "message": _("Password setup failed. Please try logging in manually.")}
        
        # Auto-login the user
        frappe.local.login_manager.login_as(user.name)
        
        return {"success": True, "message": _("Account created successfully")}
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Custom Signup Error")
        return {"success": False, "message": str(e)}