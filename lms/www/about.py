import frappe
from . import get_base_context

def get_context(context):
    context = get_base_context(context)
    context.no_cache = 1
    
    # Get website settings
    website_settings = frappe.get_doc("Website Settings")
    context.app_name = website_settings.app_name or "Our Learning Platform"
    
    # Fetch About US page content - get your specific document
    try:
        # Get the specific document
        about_us = frappe.get_doc("About US", "LMS About Us")
        
        # Set context with actual values
        context.vision = about_us.vision or ""
        context.mission = about_us.mission or ""
        context.our_story = about_us.our_story or ""
        context.about_image = about_us.about_image or ""
        
        print(f"DEBUG - Successfully loaded About US data")
        
    except Exception as e:
        print(f"DEBUG - Error loading About US: {e}")
        context.vision = ""
        context.mission = ""
        context.our_story = ""
        context.about_image = ""
    
    # Fetch Team Members
    context.team_members = []
    try:
        if frappe.db.exists("DocType", "About Us Team Member"):
            team_members = frappe.get_all(
                "About Us Team Member",
                fields=["full_name", "bio", "image_link"],
                order_by="creation"
            )
            context.team_members = team_members
            print(f"DEBUG - Found {len(team_members)} team members")
    except Exception as e:
        print(f"DEBUG - Error fetching team members: {e}")
        context.team_members = []
    
    return context