# app/order_app/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Order, Product, PromoCode, OrderItem
from .serializers import OrderSerializer, ProductSerializer, PromoCodeSerializer
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
# from .tasks.email_tasks import send_order_confirmation_email

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        """Return orders for the authenticated user only"""
        return Order.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save(user=request.user)
        # send_order_confirmation_email.delay(order.id)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        """Update an existing order (e.g., items or promo code)"""
        order = self.get_object()  # Get the order instance
        serializer = self.get_serializer(order, data=request.data, partial=False, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data)
        
    
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    queryset = Product.objects.all()  
    filter_backends = [DjangoFilterBackend]

class PromoCodeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PromoCodeSerializer
    queryset = PromoCode.objects.filter(
        is_active=True,
        start_at__lte=timezone.now(),
        ended_at__gte=timezone.now()
    )
    filter_backends = [DjangoFilterBackend]
