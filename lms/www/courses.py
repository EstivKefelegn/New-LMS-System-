import frappe

def get_context(context):
    category_slug = frappe.form_dict.get("category")
    filters = {"featured": 1}

    # --- DEFAULT CONTEXT ---
    context.selected_category = "All Courses"
    context.category_short_intro = ""

    # --- CATEGORY FILTER ---
    if category_slug:
        category_name = category_slug.replace("_", " ").title()
        category_doc = frappe.get_all(
            "LMS Category",
            filters={"category": category_name},
            fields=["name", "short_intruduction"]  # fetch short_intruduction from category
        )

        if category_doc:
            category = frappe.get_doc("LMS Category", category_doc[0].name)
            filters["category"] = category.name
            context.selected_category = category.category
            context.category_short_intro = category.short_intruduction or ""
        else:
            # Category not found
            context.courses = []
            context.selected_category = category_name
            context.title = f"Featured Courses in {context.selected_category}"
            context.category_short_intro = ""
            return context

    # --- FETCH COURSES IN THIS CATEGORY ---
    courses = frappe.get_all(
        "LMS Course",
        fields=[
            "name",
            "title",
            "category",
            "short_introduction",
            "image",
            "course_price",
            "currency",
            "creation",
            "featured"
        ],
        filters=filters,
        order_by="creation desc",
        limit=3
    )

    # --- GET CURRENCY SYMBOL FOR EACH COURSE ---
    for course in courses:
        if course.currency:
            currency_doc = frappe.get_doc("Currency", course.currency)
            course["currency_symbol"] = currency_doc.symbol
        else:
            course["currency_symbol"] = ""  # fallback if no currency

    # --- CONTEXT FOR TEMPLATE ---
    context.courses = courses
    context.title = f"Featured Courses in {context.selected_category}"

    return context






# import frappe

# def get_context(context):
#     # Get category from URL like /courses/personal_development
#     category = frappe.form_dict.category

#     filters = {}
#     if category:
#         filters["category"] = category.replace("_", " ")  # adjust if your field name differs

#     # Fetch courses matching the category
#     context.courses = frappe.get_all(
#         "LMS Course",
#         fields=["name", "title", "category"],
#         filters=filters
#     )

#     context.selected_category = category
#     return context
