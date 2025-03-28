# app/order_app/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, ProductViewSet, PromoCodeViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'promo-codes', PromoCodeViewSet, basename='promo-code')

urlpatterns = [
    path('', include(router.urls)),
]