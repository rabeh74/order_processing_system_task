# app/order/models.py
from django.db import models
from user.models import CustomUser
from django.utils import timezone

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Product(TimeStampedModel):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

class PromoCode(TimeStampedModel):
    PROMO_TYPE_CHOICES = (
        ('FIXED', 'Fixed Amount'),
        ('PERCENTAGE', 'Percentage'),
    )
    
    coupon_code = models.CharField(max_length=20, unique=True)
    coupon_name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=PROMO_TYPE_CHOICES)
    start_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    fixed_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    count = models.PositiveIntegerField(default=0, help_text="Number of times this can be used (0 = unlimited)")

    def __str__(self):
        return f"{self.coupon_name} ({self.coupon_code})"

    @property
    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and
            self.start_at <= now <= self.ended_at  
        )
    
    def get_discount(self , amount):
        """return discount amount"""
        if self.type == 'FIXED':
            return self.fixed_amount
        elif self.type == 'PERCENTAGE':
            return min((amount * self.discount_percentage) / 100, self.max_discount_amount)
        return 0

class Order(TimeStampedModel):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    total_price = models.DecimalField(max_digits=10, decimal_places=2 , default=0)
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def __str__(self):
        return f"Order {self.id} by {self.user.email}"
    
    def update_total_price(self):
        """Recalculate and save total_price"""
        self.total_price = sum(item.price for item in self.items.all())
        if self.promo_code and self.promo_code.is_valid:
            self.apply_discount()

    def apply_discount(self):
        """Apply discount if there's a promo code"""
        discount_amount = self.promo_code.get_discount(self.total_price)
        self.discount = discount_amount
        self.total_price = max(0, self.total_price - discount_amount)


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Order {self.order.id}"