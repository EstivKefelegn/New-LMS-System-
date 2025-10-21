import frappe

@frappe.whitelist(allow_guest=True)
def get_more_courses(start=0, limit=6):
    start = int(start)
    limit = int(limit)

    try:
        courses = frappe.get_all(
            "LMS Course",
            fields=[
                "name",
                "title",
                "short_introduction",
                "image",
                "owner",
                "course_price",
                "currency",
                "creation"
            ],
            filters={"published": 1},
            order_by="creation desc",
            start=start,
            limit_page_length=limit
        )

        for course in courses:
            instructor_name = frappe.db.get_value("User", course.owner, "full_name")
            course.instructor_name = instructor_name or "Expert Instructor"
            course.rating = 4.5
            course.duration = "30 hours"

        return {"courses": courses}

    except Exception as e:
        frappe.log_error(f"Error in get_more_courses: {str(e)}")
        return {"courses": []}
