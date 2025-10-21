import frappe
from . import get_base_context  # Import the shared function

def get_context(context):
    context = get_base_context(context)
    
    try:
        # Get course categories for dropdown
        categories = frappe.get_all("LMS Category", fields=["name", "category"])
    except Exception as e:
        frappe.log_error(f"Error fetching categories: {e}", "Home Page Error")
        categories = []
    
    context.categories = categories
    
    try:
        # Get initial 3 courses
        courses = frappe.get_all(
            "LMS Course",
            fields=[
                "name",
                "title", 
                "short_introduction",
                "image",
                "course_price",
                "currency",
                "creation",
                "owner"
            ],
            filters={"published": 1},
            order_by="creation desc",
            limit_page_length=3
        )
        
        # Enhance course data
        for course in courses:
            # Get instructor name
            instructor_name = frappe.db.get_value("User", course.owner, "full_name")
            course.instructor_name = instructor_name or "Expert Instructor"
            
            # Generate initials
            if not instructor_name or instructor_name == "Expert Instructor":
                course.instructor_initials = "EI"
            else:
                parts = instructor_name.split()
                if len(parts) >= 2:
                    course.instructor_initials = (parts[0][0] + parts[1][0]).upper()
                else:
                    course.instructor_initials = instructor_name[:2].upper()
            
            # Set default values
            course.rating = 4.5
            course.duration = "30 hours"
            course.badge = {"text": "Popular", "color": "blue"}
            
        context.courses = courses
        context.total_courses = frappe.db.count("LMS Course", {"published": 1})
        
    except Exception as e:
        frappe.log_error(f"Error in course_list context: {str(e)}")
        context.courses = []
        context.total_courses = 0
    
    return context