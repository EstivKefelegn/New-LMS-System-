import frappe
from frappe import _
import re

no_cache = 1

def get_context(context):
    # Try both parameter names to be safe
    course_name = frappe.form_dict.get("course_id") or frappe.form_dict.get("course")
    
    if not course_name:
        frappe.local.flags.redirect_location = "/courses"
        raise frappe.Redirect
    
    try:
        course = frappe.get_doc("LMS Course", course_name)
        context.course = course
        
        # Extract YouTube ID if video_link exists
        if course.video_link:
            context.youtube_id = extract_youtube_id(course.video_link)
        
        # Get course statistics
        context.enrollments = course.enrollments or 0
        context.lessons_count = course.lessons or 0
        context.rating = course.rating or 0
        
        # Get chapters and lessons - handle case where doctype might not exist
        context.chapters = get_course_chapters(course_name)
        
        # Get instructors
        context.instructors = get_course_instructors(course.instructors) if course.instructors else []
        
        # Get related courses
        context.related_courses = get_related_courses(course.related_courses) if course.related_courses else []
        
        # Meta tags for SEO
        context.meta_tags = {
            "title": course.title,
            "description": course.short_introduction or course.description,
            "image": course.image,
            "keywords": course.tags or ""
        }
        
    except frappe.DoesNotExistError:
        frappe.throw(_("Course not found"), frappe.DoesNotExistError)

def extract_youtube_id(url):
    """Extract YouTube ID from various YouTube URL formats"""
    if not url:
        return None
    
    # If it's already just an ID (like "XKHEtdqhLK8")
    if len(url) == 11 and not any(char in url for char in ['/', '?', '=', '&']):
        return url
    
    # Pattern for different YouTube URL formats
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&]+)',
        r'youtube\.com\/embed\/([^?]+)',
        r'youtube\.com\/v\/([^?]+)',
        r'v=([^&]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def get_course_chapters(course_name):
    """Get all chapters and their lessons for the course"""
    try:
        # Check if Course Chapter doctype exists
        if not frappe.db.exists("DocType", "Course Chapter"):
            return []
            
        chapters = frappe.get_all("Course Chapter",
            filters={"course": course_name},
            fields=["name", "title", "description"],
            order_by="idx"
        )
        
        for chapter in chapters:
            # Check if Course Lesson doctype exists
            if frappe.db.exists("DocType", "Course Lesson"):
                chapter.lessons = frappe.get_all("Course Lesson",
                    filters={"chapter": chapter.name},
                    fields=["name", "title", "duration", "content_type", "idx"],
                    order_by="idx"
                )
            else:
                chapter.lessons = []
        
        return chapters
    except Exception as e:
        frappe.log_error(f"Error getting chapters for course {course_name}: {str(e)}")
        return []

def get_course_instructors(instructors):
    """Get instructor details"""
    instructor_details = []
    for instructor in instructors:
        try:
            instructor_doc = frappe.get_doc("User", instructor.instructor)
            instructor_details.append({
                "name": instructor_doc.name,
                "full_name": instructor_doc.full_name,
                "bio": getattr(instructor_doc, 'bio', ''),
                "headline": getattr(instructor_doc, 'headline', 'Course Instructor'),
                "user_image": instructor_doc.user_image
            })
        except Exception as e:
            frappe.log_error(f"Error getting instructor details: {str(e)}")
            continue
    return instructor_details

def get_related_courses(related_courses):
    """Get related courses details"""
    related = []
    for related_course in related_courses:
        try:
            course = frappe.get_doc("LMS Course", related_course.course)
            if course.published:
                related.append({
                    "name": course.name,
                    "title": course.title,
                    "image": course.image,
                    "short_introduction": course.short_introduction,
                    "course_price": course.course_price,
                    "currency": course.currency
                })
        except Exception as e:
            frappe.log_error(f"Error getting related course: {str(e)}")
            continue
    return related[:3]  # Limit to 3 related courses