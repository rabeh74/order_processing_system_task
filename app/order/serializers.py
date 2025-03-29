# app/order_app/serializers/order_serializer.py
from rest_framework import serializers
from .models import Order, OrderItem, Product, PromoCode
from django.db import transaction

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'stock' ,'created_at']
        read_only_fields = ['created_at']


class PromoCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromoCode
        fields = ['id', 'coupon_code', 'coupon_name', 'type', 'fixed_amount', 'discount_percentage', 
                  'max_discount_amount', 'start_at', 'ended_at', 'is_active', 'count']
        
    def validate(self, data):
        """Ensure fixed_amount or discount_percentage is provided based on type"""
        promo_type = data.get('type')
        fixed_amount = data.get('fixed_amount')
        discount_percentage = data.get('discount_percentage')

        if promo_type == 'FIXED' and fixed_amount is None:
            raise serializers.ValidationError({"fixed_amount": "This field is required for FIXED promo codes"})
        if promo_type == 'PERCENTAGE' and discount_percentage is None:
            raise serializers.ValidationError({"discount_percentage": "This field is required for PERCENTAGE promo codes"})
        if data.get('start_at') > data.get('ended_at'):
            raise serializers.ValidationError({"ended_at": "End date must be after start date"})
        return data


class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price']
        read_only_fields = ['price']
    
    def create(self, validated_data):
        price_of_product = validated_data['product'].price
        quantity = validated_data['quantity']
        
        if quantity > validated_data['product'].stock:
            raise serializers.ValidationError({"error": "Not enough stock for product"})
        
        validated_data['price'] = price_of_product * quantity
        order_item = OrderItem.objects.create(**validated_data)
        return order_item
    
    def update(self, instance, validated_data):
        if 'product' in validated_data:
            product = validated_data['product']
            if product.stock < validated_data['quantity']:
                raise serializers.ValidationError({"error": "Not enough stock for product"})
            
            validated_data['price'] = product.price * validated_data['quantity']

        instance.quantity = validated_data.get('quantity', instance.quantity)
        instance.price = validated_data.get('price', instance.price)
        instance.product = validated_data.get('product', instance.product)
        instance.save()
        return instance
        


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True , required=True)
    coupon_code = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'items', 'total_price', 'coupon_code', 'discount', 'created_at']
        read_only_fields = ['user', 'total_price', 'discount', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        coupon_code = validated_data.pop('coupon_code', None)
        order = Order.objects.create(user=validated_data['user'])

        self._create_order_items(order, items_data)
        
        if coupon_code:
            try:
                promo_code = PromoCode.objects.get(coupon_code=coupon_code)
                order.promo_code = promo_code
            except PromoCode.DoesNotExist:
                raise serializers.ValidationError({"error": "Invalid promo code"})

        order.update_total_price()
        order.save()
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        coupon_code = validated_data.pop('coupon_code', None)
    
        if items_data:
            self._add_quantity_to_product_stock(instance)
            self._create_order_items(instance, items_data)
            
        if coupon_code:
            try:
                promo_code = PromoCode.objects.get(coupon_code=coupon_code)
                instance.promo_code = promo_code
            except PromoCode.DoesNotExist:
                raise serializers.ValidationError({"error": "Invalid promo code"})
        
        instance.update_total_price()
        instance.save()
        return instance
    
    def delete(self, instance):
        self._add_quantity_to_product_stock(instance)
        instance.delete()
        
    def _create_order_items(self, order, items_data):
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']

            if quantity > product.stock:
                raise serializers.ValidationError({"error": "Not enough stock for product"})
            
            product.stock -= quantity
            product.save()
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price * quantity
            )
    
    def _add_quantity_to_product_stock(self, order):
        order_items = order.items.all()
        for order_item in order_items:
            product = order_item.product
            quantity = order_item.quantity

            product.stock += quantity
            product.save()

        order_items.delete()
        order.save()
