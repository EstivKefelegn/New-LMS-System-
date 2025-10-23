import frappe
from frappe.utils import flt, getdate
from collections import defaultdict

def execute(filters=None):
    # Table columns
    columns = [
        {"label": "Course", "fieldname": "course", "fieldtype": "Data", "width": 250},
        {"label": "Month", "fieldname": "month", "fieldtype": "Data", "width": 120},
        {"label": "Total Payments", "fieldname": "total_payments", "fieldtype": "Currency", "width": 120},
        {"label": "Number of Payments", "fieldname": "num_payments", "fieldtype": "Int", "width": 120},
    ]

    data = []
    summary_dict = defaultdict(lambda: {"total": 0, "count": 0})
    monthly_total = defaultdict(float)  # Sum of all payments per month
    total_revenue = 0
    total_payments_count = 0
    total_courses = set()

    filters = filters or {}

    # Payment filters
    payment_filters = {}
    if filters.get("course"):
        payment_filters["payment_for_document"] = filters["course"]
    if filters.get("from_date"):
        payment_filters["creation"] = [">=", filters["from_date"]]
    if filters.get("to_date"):
        if "creation" in payment_filters:
            payment_filters["creation"].append(["<=", filters["to_date"]])
        else:
            payment_filters["creation"] = ["<=", filters["to_date"]]

    # Fetch payments
    payments = frappe.get_all(
        "LMS Payment",
        fields=["payment_for_document", "amount", "creation"],
        filters=payment_filters,
        order_by="creation asc"
    )

    # Aggregate
    for p in payments:
        month = getdate(p.creation).strftime("%Y-%m")
        course = p.payment_for_document
        total_courses.add(course)
        key = (course, month)
        summary_dict[key]["total"] += flt(p.amount)
        summary_dict[key]["count"] += 1
        monthly_total[month] += flt(p.amount)  # total payments per month
        total_revenue += flt(p.amount)
        total_payments_count += 1

    # Table data
    for (course, month), vals in summary_dict.items():
        data.append({
            "course": course,
            "month": month,
            "total_payments": vals["total"],
            "num_payments": vals["count"]
        })

    data.sort(key=lambda x: x["month"], reverse=True)

    # Summary
    summary = {
        "Total Revenue": {"type": "Currency", "value": total_revenue},
        "Total Payments": {"type": "Int", "value": total_payments_count},
        "Total Courses": {"type": "Int", "value": len(total_courses)},
    }

    # Chart
    months = sorted(list({k[1] for k in summary_dict.keys()}))
    courses = sorted(list({k[0] for k in summary_dict.keys()}))
    datasets = []

    colors = ["#3498db", "#2ecc71", "#e74c3c", "#f39c12", "#9b59b6", "#1abc9c"]

    # Add course datasets
    for i, course in enumerate(courses):
        values = [flt(summary_dict.get((course, month), {}).get("total", 0)) for month in months]
        datasets.append({
            "name": course,
            "values": values,
            "color": colors[i % len(colors)]
        })

    # Add total payments dataset (sum of all courses per month)
    total_values = [flt(monthly_total.get(month, 0)) for month in months]
    datasets.append({
        "name": "Total Payments",
        "values": total_values,
        "color": "#34495e"  # Dark gray
    })

    chart = {
        "data": {
            "labels": months,
            "datasets": datasets
        },
        "type": "bar",
        "stacked": False,  # Set True if you want a stacked bar
        "height": 300,
        "title": "Course Revenue and Total Payments by Month"
    } if datasets else {}

    return columns, data, {"chart": chart, "summary": summary}
