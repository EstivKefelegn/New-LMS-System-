import frappe

def get_user_initials(full_name):
    """Generate initials from full name"""
    if not full_name or full_name == "Student":
        return "ST"
    parts = full_name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    else:
        return full_name[:2].upper()


def _scale_rating_to_5(raw):
    """
    Scale any numeric rating to 0-5 with 1 decimal precision.
    """
    try:
        val = float(raw)
    except Exception:
        return 0.0

    if val <= 1.0:
        scaled = val * 5.0
    elif val <= 10.0:
        scaled = (val / 10.0) * 5.0
    elif val <= 100.0:
        scaled = (val / 100.0) * 5.0
    else:
        scaled = 5.0

    return round(max(0.0, min(5.0, scaled)), 1)


def get_context(context):
    # --- Categories ---
    try:
        categories = frappe.get_all("LMS Category", fields=["name", "category"])
    except Exception as e:
        frappe.log_error(f"Error fetching categories: {e}", "Home Page Error")
        categories = []
    context.categories = categories

    # --- Courses ---
    try:
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
                "owner",
                "category",
            ],
            filters={"published": 1},
            order_by="creation desc",
            limit_page_length=3
        )

        for course in courses:
            # instructor
            instructor_name = frappe.db.get_value("User", course.owner, "full_name")
            course.instructor_name = instructor_name or "Expert Instructor"
            course.instructor_initials = get_user_initials(course.instructor_name)

            # reviews for course
            course_reviews = frappe.get_all(
                "LMS Course Review",
                fields=["rating", "review", "creation", "owner"],
                filters={"course": course.name},
                order_by="creation desc",
                limit_page_length=50
            )

            if course_reviews:
                scaled_values = []
                for r in course_reviews:
                    try:
                        # scale rating
                        scaled = _scale_rating_to_5(r['rating'])
                        r['rating'] = scaled
                        scaled_values.append(scaled)

                        # fetch reviewer info dynamically
                        reviewer_name = frappe.db.get_value("User", r['owner'], "full_name")
                        reviewer_name = reviewer_name or "Student"
                        r['reviewer_name'] = reviewer_name
                        r['reviewer_initials'] = get_user_initials(reviewer_name)
                    except Exception:
                        continue

                if scaled_values:
                    avg = sum(scaled_values) / len(scaled_values)
                    course.rating = round(avg, 1)
                    course.review_count = len(scaled_values)
                else:
                    course.rating = 0.0
                    course.review_count = 0

                course.latest_reviews = course_reviews[:2]
            else:
                course.rating = 0.0
                course.review_count = 0
                course.latest_reviews = []

            course.duration = "30 hours"
            course.badge = {"text": "Popular", "color": "blue"}

        context.courses = courses
        context.total_courses = frappe.db.count("LMS Course", {"published": 1})

    except Exception as e:
        frappe.log_error(f"Error in course_list context: {str(e)}")
        context.courses = []
        context.total_courses = 0

    # --- Testimonials ---
    try:
        reviews = frappe.get_all(
            "LMS Course Review",
            fields=["name", "rating", "review", "course", "owner"],
            order_by="creation desc",
            limit_page_length=20,
            ignore_permissions=True
        )

        testimonials = []
        for r in reviews:
            # scale rating
            r['rating'] = _scale_rating_to_5(r['rating'])

            # fetch reviewer dynamically
            reviewer_name = frappe.db.get_value("User", r['owner'], "full_name") or "Student"
            r['user_name'] = reviewer_name
            r['user_initials'] = get_user_initials(reviewer_name)

            # fetch course title
            r['course_title'] = frappe.db.get_value("LMS Course", r['course'], "title") or "Our Course"

            testimonials.append(r)

        # assign colors for UI
        color_classes = ["blue", "green", "purple", "orange", "teal", "pink"]
        for i, t in enumerate(testimonials):
            t['color_class'] = color_classes[i % len(color_classes)]

        context.testimonials = testimonials

    except Exception as e:
        frappe.log_error(f"Error fetching testimonials: {str(e)}", "Testimonials Error")
        context.testimonials = []

    return context
