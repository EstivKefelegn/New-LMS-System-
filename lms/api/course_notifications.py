import frappe

def notify_users_on_new_course(doc, method):
    """Send email to all active users when a new course is added"""
    course_title = doc.title
    course_link = frappe.utils.get_url(f"/lms/courses/{doc.name}")
    sender = frappe.session.user or "Administrator"

    # Get all users except Guest
    users = frappe.get_all("User", filters={"enabled": 1}, fields=["email"])
    recipient_emails = [u.email for u in users if u.email and u.email != "guest@example.com"]

    if not recipient_emails:
        frappe.logger().info("No recipients found for course notification.")
        return

    subject = f"New Course Added: {course_title}"
    message = f"""
    <p>Hello,</p>
    <p>A new course <b>{course_title}</b> has just been uploaded to the LMS.</p>
    <p>You can check it out here: <a href="{course_link}">{course_link}</a></p>
    <br>
    <p>Best regards,<br>Your LMS Team</p>
    """

    # Send the email
    frappe.sendmail(
        recipients=recipient_emails,
        sender=sender,
        subject=subject,
        message=message,
        delayed=False  # Set to True if you want to queue it for later sending
    )

    frappe.logger().info(f"Sent new course notification for '{course_title}' to {len(recipient_emails)} users.")
