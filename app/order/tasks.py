from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_order_confirmation_email(order_id, user_email, user_first_name, items_data, total_price, discount):
    """Send an order confirmation email with pre-fetched data"""
    try:
        subject = f"Order Confirmation - Order #{order_id}"
        message = (
            f"Dear {user_first_name or user_email},\n\n"
            f"Thank you for your order! Here are the details:\n"
            f"Order ID: {order_id}\n"
            f"Total Price: ${total_price}\n"
            f"Discount: ${discount}\n"
            f"Items:\n"
            + "\n".join([f"- {item['product_name']} (Qty: {item['quantity']})" for item in items_data])
            + "\n\nBest regards,\nThe Order Team"
        )
        recipient_list = [user_email]
        
        logger.info(f"Sending confirmation email for order {order_id} to {recipient_list}")
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL or 'no-reply@orderapp.com',
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info(f"Confirmation email sent for order {order_id}")
    except Exception as e:
        logger.error(f"Failed to send email for order {order_id}: {str(e)}")