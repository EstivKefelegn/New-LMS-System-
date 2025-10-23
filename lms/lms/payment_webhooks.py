# apps/lms/lms/payment_webhooks.py
import frappe
import json
import hashlib
import hmac
from frappe import _
from frappe.utils import now_datetime

@frappe.whitelist(allow_guest=True)
def handle_payment_success():
    """Handle payment success webhooks from payment gateways"""
    try:
        # Get webhook data
        if frappe.request.method != "POST":
            return {"success": False, "error": "Method not allowed"}
        
        data = frappe.request.get_json()
        
        if not data:
            return {"success": False, "error": "No data received"}
        
        # Log the webhook for debugging
        frappe.logger().info(f"Payment webhook received: {json.dumps(data, default=str)}")
        
        # Get request headers for signature verification
        headers = dict(frappe.request.headers)
        
        # Handle different payment gateways
        
        # 1. Stripe Webhook (check for Stripe signature OR stripe-like payload)
        if headers.get('Stripe-Signature') or data.get('type', '').startswith('payment_intent.') or data.get('type', '').startswith('checkout.session.'):
            return handle_stripe_webhook(data, headers)
        
        # 2. Razorpay Webhook
        elif data.get('event') == 'payment.captured':
            return handle_razorpay_webhook(data)
        
        # 3. PayPal Webhook
        elif data.get('event_type') == 'PAYMENT.CAPTURE.COMPLETED':
            return handle_paypal_webhook(data)
        
        # 4. Custom payload (for testing or custom integrations)
        elif data.get('payment_status') == 'completed':
            return handle_custom_webhook(data)
        
        else:
            return {
                "success": False,
                "message": "Webhook event not supported",
                "received_event": data.get('event') or data.get('type') or 'unknown'
            }
            
    except Exception as e:
        frappe.log_error(f"Payment webhook processing failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def handle_stripe_webhook(data, headers):
    """Handle Stripe webhook with optional signature verification"""
    try:
        # Skip signature verification for testing (or implement it properly for production)
        # if not verify_stripe_signature(headers):
        #     return {"success": False, "error": "Invalid Stripe signature"}
        
        event_type = data.get('type')
        frappe.logger().info(f"Processing Stripe event: {event_type}")
        
        # Handle different Stripe event types
        if event_type == 'payment_intent.succeeded':
            return handle_stripe_payment_intent_succeeded(data)
        elif event_type == 'checkout.session.completed':
            return handle_stripe_checkout_completed(data)
        elif event_type == 'invoice.payment_succeeded':
            return handle_stripe_invoice_payment_succeeded(data)
        else:
            return {
                "success": True,
                "message": f"Stripe event {event_type} received but not processed",
                "event_type": event_type
            }
            
    except Exception as e:
        frappe.log_error(f"Stripe webhook failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
        
def verify_stripe_signature(headers):
    """Verify Stripe webhook signature"""
    try:
        stripe_webhook_secret = frappe.db.get_single_value('LMS Settings', 'stripe_webhook_secret')
        
        if not stripe_webhook_secret:
            frappe.logger().warning("Stripe webhook secret not configured")
            return True  # Skip verification if secret not set
        
        signature = headers.get('Stripe-Signature')
        if not signature:
            return False
        
        # Get the raw request body for signature verification
        from frappe.utils import get_site_name
        import stripe
        
        payload = frappe.request.get_data(as_text=True)
        
        # Verify the signature
        stripe.Webhook.construct_event(
            payload, 
            signature, 
            stripe_webhook_secret
        )
        
        return True
        
    except Exception as e:
        frappe.log_error(f"Stripe signature verification failed: {str(e)}")
        return False

def handle_stripe_payment_intent_succeeded(data):
    """Handle Stripe payment_intent.succeeded event"""
    try:
        payment_intent = data.get('data', {}).get('object', {})
        
        payment_id = payment_intent.get('id')
        amount = payment_intent.get('amount') / 100  # Stripe amounts are in cents
        currency = payment_intent.get('currency', 'usd').upper()
        metadata = payment_intent.get('metadata', {})
        
        frappe.logger().info(f"Processing Stripe payment intent: {payment_id}")
        
        # Extract course and user information from metadata
        course_id = metadata.get('course_id') or metadata.get('course')
        user_email = metadata.get('user_email') or metadata.get('customer_email')
        
        if not course_id or not user_email:
            return {
                "success": False,
                "message": "Missing course_id or user_email in Stripe metadata"
            }
        
        # Find user by email
        user = frappe.db.get_value("User", {"email": user_email}, "name")
        if not user:
            return {
                "success": False,
                "message": f"User not found with email: {user_email}"
            }
        
        # Create or update payment record WITHOUT source field
        payment_name = create_or_update_stripe_payment(
            user=user,
            course_id=course_id,
            amount=amount,
            payment_id=payment_id,
            currency=currency,
            metadata=metadata
        )
        
        # Create invoice directly
        invoice_result = create_invoice_directly(payment_name, course_id, user, amount)
        
        frappe.db.commit()
        
        # Send confirmation email
        send_payment_confirmation(user, course_id, amount, currency, payment_id)
        
        return {
            "success": True,
            "message": "Stripe payment processed successfully",
            "payment": payment_name,
            "invoice": invoice_result.get("invoice"),
            "user": user,
            "course": course_id
        }
        
    except Exception as e:
        frappe.log_error(f"Stripe payment intent processing failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def create_or_update_stripe_payment(user, course_id, amount, payment_id, currency, metadata):
    """Create or update Stripe payment record WITHOUT source field"""
    try:
        # Check if payment already exists
        payment_name = frappe.db.get_value("LMS Payment", {
            "payment_id": payment_id
        }, "name")
        
        if payment_name:
            # Update existing payment
            frappe.db.set_value("LMS Payment", payment_name, {
                "payment_received": 1,
                "amount": amount,
                "currency": currency
            })
            frappe.logger().info(f"Updated existing Stripe payment: {payment_name}")
            return payment_name
        else:
            # Create new payment WITHOUT source field
            payment_data = {
                "doctype": "LMS Payment",
                "member": user,
                "payment_for_document_type": "LMS Course",
                "payment_for_document": course_id,
                "amount": amount,
                "currency": currency,
                "payment_received": 1,
                "payment_id": payment_id,
                "order_id": metadata.get('order_id'),
                "billing_name": frappe.db.get_value("User", user, "full_name") or user,
                "address": "newuser-Billing"  # Use the default address we found earlier
                # Don't include source field to avoid validation errors
            }
            
            payment = frappe.get_doc(payment_data)
            payment.insert(ignore_permissions=True)
            frappe.logger().info(f"Created new Stripe payment: {payment.name}")
            return payment.name
            
    except Exception as e:
        frappe.log_error(f"Failed to create/update Stripe payment: {str(e)}")
        raise e
    

def handle_stripe_checkout_completed(data):
    """Handle Stripe checkout.session.completed event"""
    try:
        session = data.get('data', {}).get('object', {})
        
        session_id = session.get('id')
        payment_intent_id = session.get('payment_intent')
        amount_total = session.get('amount_total', 0) / 100
        currency = session.get('currency', 'usd').upper()
        
        metadata = session.get('metadata', {})
        customer_email = session.get('customer_email')
        
        frappe.logger().info(f"Processing Stripe checkout session: {session_id}")
        
        # Extract course information from metadata
        course_id = metadata.get('course_id') or metadata.get('course')
        
        if not course_id or not customer_email:
            return {
                "success": False,
                "message": "Missing course_id or customer_email in Stripe checkout session"
            }
        
        # Find user by email
        user = frappe.db.get_value("User", {"email": customer_email}, "name")
        if not user:
            return {
                "success": False,
                "message": f"User not found with email: {customer_email}"
            }
        
        # Create or update payment record
        payment_name = create_or_update_stripe_payment(
            user=user,
            course_id=course_id,
            amount=amount_total,
            payment_id=payment_intent_id or session_id,
            currency=currency,
            metadata=metadata
        )
        
        # Auto-create invoice
        from lms.lms.doctype.lms_invoice.lms_invoice import create_invoice_from_payment
        invoice_name = create_invoice_from_payment(payment_name)
        
        frappe.db.commit()
        
        # Send confirmation email
        send_payment_confirmation(user, course_id, amount_total, currency, payment_intent_id or session_id)
        
        return {
            "success": True,
            "message": "Stripe checkout completed successfully",
            "payment": payment_name,
            "invoice": invoice_name,
            "user": user,
            "course": course_id
        }
        
    except Exception as e:
        frappe.log_error(f"Stripe checkout processing failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def handle_stripe_invoice_payment_succeeded(data):
    """Handle Stripe invoice.payment_succeeded event"""
    try:
        invoice = data.get('data', {}).get('object', {})
        
        invoice_id = invoice.get('id')
        payment_intent_id = invoice.get('payment_intent')
        amount_paid = invoice.get('amount_paid', 0) / 100
        currency = invoice.get('currency', 'usd').upper()
        customer_email = invoice.get('customer_email')
        
        metadata = invoice.get('metadata', {})
        
        frappe.logger().info(f"Processing Stripe invoice payment: {invoice_id}")
        
        # Extract course information from metadata
        course_id = metadata.get('course_id') or metadata.get('course')
        
        if not course_id or not customer_email:
            return {
                "success": False,
                "message": "Missing course_id or customer_email in Stripe invoice"
            }
        
        # Find user by email
        user = frappe.db.get_value("User", {"email": customer_email}, "name")
        if not user:
            return {
                "success": False,
                "message": f"User not found with email: {customer_email}"
            }
        
        # Create or update payment record
        payment_name = create_or_update_stripe_payment(
            user=user,
            course_id=course_id,
            amount=amount_paid,
            payment_id=payment_intent_id or invoice_id,
            currency=currency,
            metadata=metadata
        )
        
        # Auto-create invoice
        from lms.lms.doctype.lms_invoice.lms_invoice import create_invoice_from_payment
        invoice_name = create_invoice_from_payment(payment_name)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Stripe invoice payment processed successfully",
            "payment": payment_name,
            "invoice": invoice_name,
            "user": user,
            "course": course_id
        }
        
    except Exception as e:
        frappe.log_error(f"Stripe invoice payment processing failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


# Keep all your existing Razorpay, PayPal, and other functions from previous version
def handle_razorpay_webhook(data):
    """Handle Razorpay payment captured webhook"""
    try:
        payment_data = data.get('payload', {}).get('payment', {}).get('entity', {})
        
        payment_id = payment_data.get('id')
        order_id = payment_data.get('order_id')
        amount = payment_data.get('amount') / 100  # Razorpay amounts are in paise
        
        frappe.logger().info(f"Processing Razorpay payment: {payment_id}, order: {order_id}")
        
        # For Razorpay, we need to determine the user and course
        # In a real scenario, you would store this info when creating the order
        # For testing, we'll use default values
        
        # Use default user and course for testing
        user_email = "estifanoskefelegn@gmail.com"
        course_id = "business-analytics-for-beginners"
        
        user = frappe.db.get_value("User", {"email": user_email}, "name")
        if not user:
            return {
                "success": False,
                "message": f"User not found: {user_email}"
            }
        
        # Create new payment for Razorpay
        payment_name = create_razorpay_payment(
            user=user,
            course_id=course_id,
            amount=amount,
            payment_id=payment_id,
            order_id=order_id
        )
        
        # Create invoice
        invoice_result = create_invoice_directly(payment_name, course_id, user, amount)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Razorpay payment processed successfully",
            "payment": payment_name,
            "invoice": invoice_result.get("invoice"),
            "user": user,
            "course": course_id
        }
            
    except Exception as e:
        frappe.log_error(f"Razorpay webhook failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def create_razorpay_payment(user, course_id, amount, payment_id, order_id):
    """Create Razorpay payment record"""
    try:
        payment_data = {
            "doctype": "LMS Payment",
            "member": user,
            "payment_for_document_type": "LMS Course",
            "payment_for_document": course_id,
            "amount": amount,
            "currency": "INR",  # Razorpay typically uses INR
            "payment_received": 1,
            "payment_id": payment_id,
            "order_id": order_id,
            "billing_name": frappe.db.get_value("User", user, "full_name") or user,
            "address": "newuser-Billing"
        }
        
        payment = frappe.get_doc(payment_data)
        payment.insert(ignore_permissions=True)
        frappe.logger().info(f"Created new Razorpay payment: {payment.name}")
        return payment.name
        
    except Exception as e:
        frappe.log_error(f"Failed to create Razorpay payment: {str(e)}")
        raise e

def handle_paypal_webhook(data):
    """Handle PayPal payment capture completed webhook"""
    try:
        resource = data.get('resource', {})
        
        payment_id = resource.get('id')
        amount = float(resource.get('amount', {}).get('value', 0))
        custom_id = resource.get('custom_id')  # This could be course_id or order_id
        
        frappe.logger().info(f"Processing PayPal payment: {payment_id}, custom_id: {custom_id}")
        
        # For PayPal, we need to determine the user and course
        # Since PayPal doesn't always include user email in the webhook,
        # we might need to handle this differently
        
        if custom_id:
            # Try to treat custom_id as course_id and find a user
            # In a real scenario, you might store user info in custom_id or use a different approach
            
            # For testing, let's use the default user
            user_email = "estifanoskefelegn@gmail.com"
            user = frappe.db.get_value("User", {"email": user_email}, "name")
            
            if user:
                # Create new payment for PayPal
                payment_name = create_paypal_payment(
                    user=user,
                    course_id=custom_id,
                    amount=amount,
                    payment_id=payment_id,
                    custom_id=custom_id
                )
                
                # Create invoice
                invoice_result = create_invoice_directly(payment_name, custom_id, user, amount)
                
                frappe.db.commit()
                
                return {
                    "success": True,
                    "message": "PayPal payment processed successfully",
                    "payment": payment_name,
                    "invoice": invoice_result.get("invoice"),
                    "user": user,
                    "course": custom_id
                }
        
        return {
            "success": False,
            "message": "Could not process PayPal webhook - missing user information"
        }
        
    except Exception as e:
        frappe.log_error(f"PayPal webhook failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def create_paypal_payment(user, course_id, amount, payment_id, custom_id):
    """Create PayPal payment record"""
    try:
        payment_data = {
            "doctype": "LMS Payment",
            "member": user,
            "payment_for_document_type": "LMS Course",
            "payment_for_document": course_id,
            "amount": amount,
            "currency": "USD",  # PayPal typically uses USD
            "payment_received": 1,
            "payment_id": payment_id,
            "order_id": custom_id,  # Use custom_id as order_id
            "billing_name": frappe.db.get_value("User", user, "full_name") or user,
            "address": "newuser-Billing"
        }
        
        payment = frappe.get_doc(payment_data)
        payment.insert(ignore_permissions=True)
        frappe.logger().info(f"Created new PayPal payment: {payment.name}")
        return payment.name
        
    except Exception as e:
        frappe.log_error(f"Failed to create PayPal payment: {str(e)}")
        raise e

def handle_custom_webhook(data):
    """Handle custom webhook payloads"""
    try:
        payment_id = data.get('payment_id')
        order_id = data.get('order_id')
        course_id = data.get('course_id')
        user_email = data.get('user_email')
        amount = data.get('amount')
        
        frappe.logger().info(f"🔍 Custom webhook received - payment_id: {payment_id}, course_id: {course_id}, user_email: {user_email}, amount: {amount}")
        
        # Debug: Check if user exists
        user = frappe.db.get_value("User", {"email": user_email}, "name")
        frappe.logger().info(f"🔍 User lookup by email '{user_email}': {user}")
        
        if not user:
            return {
                "success": False,
                "message": f"User not found: {user_email}"
            }
        
        # Debug: Check if course exists
        course_exists = frappe.db.exists("LMS Course", course_id)
        frappe.logger().info(f"🔍 Course '{course_id}' exists: {course_exists}")
        
        if not course_exists:
            return {
                "success": False, 
                "message": f"Course not found: {course_id}"
            }
        
        # Use the existing address we found
        address = "newuser-Billing"
        frappe.logger().info(f"🔍 Using address: {address}")
        
        # Create new payment (source field is NOT required, so we don't include it)
        frappe.logger().info(f"🔍 Creating new payment for user: {user}, course: {course_id}")
        
        payment_data = {
            "doctype": "LMS Payment",
            "member": user,
            "payment_for_document_type": "LMS Course",
            "payment_for_document": course_id,
            "amount": amount,
            "currency": "INR",
            "payment_received": 1,
            "payment_id": payment_id,
            "order_id": order_id or payment_id,
            "billing_name": frappe.db.get_value("User", user, "full_name") or user,
            "address": address  # Add the required address field
            # Don't include source field since it's not required
        }
        
        payment = frappe.get_doc(payment_data)
        payment.insert(ignore_permissions=True)
        payment_name = payment.name
        frappe.logger().info(f"✅ Created new payment: {payment_name}")
        
        # Create invoice directly without using the problematic helper function
        invoice_result = create_invoice_directly(payment_name, course_id, user, amount)
        
        frappe.logger().info(f"✅ Invoice creation result: {invoice_result}")
        
        if invoice_result.get("success"):
            invoice_name = invoice_result.get("invoice")
            frappe.db.commit()
            
            return {
                "success": True,
                "message": "Custom payment processed successfully",
                "payment": payment_name,
                "invoice": invoice_name,
                "user": user,
                "course": course_id
            }
        else:
            return {
                "success": False,
                "message": f"Invoice creation failed: {invoice_result.get('error')}",
                "payment": payment_name
            }
        
    except Exception as e:
        frappe.log_error(f"Custom webhook failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "traceback": frappe.get_traceback()
        }

def create_invoice_directly(payment_name, course_id, user, amount):
    """Create invoice directly without using the helper function"""
    try:
        payment = frappe.get_doc("LMS Payment", payment_name)
        
        # Check if invoice already exists
        existing_invoice = frappe.db.exists("LMS Invoice", {"payment_reference": payment_name})
        if existing_invoice:
            return {"success": True, "invoice": existing_invoice}
        
        # Create invoice directly
        course_title = frappe.db.get_value("LMS Course", course_id, "title") or course_id
        
        invoice_data = {
            "doctype": "LMS Invoice",
            "customer": user,
            "payment_reference": payment_name,
            "course": course_id,
            "payment_for": f"Course: {course_title}",
            "amount": amount,
            "total_amount": amount,
            "invoice_date": frappe.utils.nowdate(),
            "status": "Paid",
            "order_id": payment.order_id,
            "payment_id": payment.payment_id,
            "currency": payment.currency,
            "billing_name": payment.billing_name,
            "address": payment.address
        }
        
        invoice = frappe.get_doc(invoice_data)
        invoice.insert(ignore_permissions=True)
        
        # Submit the invoice
        invoice.submit()
        
        return {"success": True, "invoice": invoice.name}
        
    except Exception as e:
        frappe.log_error(f"Direct invoice creation failed: {str(e)}")
        return {"success": False, "error": str(e)}

def handle_stripe_payment_intent_succeeded(data):
    """Handle Stripe payment_intent.succeeded event"""
    try:
        payment_intent = data.get('data', {}).get('object', {})
        
        payment_id = payment_intent.get('id')
        amount = payment_intent.get('amount') / 100  # Stripe amounts are in cents
        currency = payment_intent.get('currency', 'usd').upper()
        metadata = payment_intent.get('metadata', {})
        
        frappe.logger().info(f"Processing Stripe payment intent: {payment_id}")
        
        # Extract course and user information from metadata
        course_id = metadata.get('course_id') or metadata.get('course')
        user_email = metadata.get('user_email') or metadata.get('customer_email')
        
        if not course_id or not user_email:
            return {
                "success": False,
                "message": "Missing course_id or user_email in Stripe metadata"
            }
        
        # Find user by email
        user = frappe.db.get_value("User", {"email": user_email}, "name")
        if not user:
            return {
                "success": False,
                "message": f"User not found with email: {user_email}"
            }
        
        # Create or update payment record WITHOUT source field
        payment_name = create_or_update_stripe_payment(
            user=user,
            course_id=course_id,
            amount=amount,
            payment_id=payment_id,
            currency=currency,
            metadata=metadata
        )
        
        # Create invoice directly
        invoice_result = create_invoice_directly(payment_name, course_id, user, amount)
        
        frappe.db.commit()
        
        # Comment out email for now to avoid errors
        # send_payment_confirmation(user, course_id, amount, currency, payment_id)
        
        return {
            "success": True,
            "message": "Stripe payment processed successfully",
            "payment": payment_name,
            "invoice": invoice_result.get("invoice"),
            "user": user,
            "course": course_id
        }
        
    except Exception as e:
        frappe.log_error(f"Stripe payment intent processing failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist(allow_guest=True)
def webhook_test():
    """Test endpoint to verify webhook is working"""
    return {
        "success": True,
        "message": "Webhook endpoint is active",
        "timestamp": frappe.utils.now(),
        "supported_gateways": ["Stripe", "Razorpay", "PayPal", "Custom"]
    }
    
    
    