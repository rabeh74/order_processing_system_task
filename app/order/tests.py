from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from order.models import Order, OrderItem, Product, PromoCode
from django.utils import timezone

User = get_user_model()

class OrderViewSetTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create a user for authentication
        self.user = User.objects.create_user(email='test@example.com', password='testpass123')
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        self.product1 = Product.objects.create(name='Laptop', price=100, stock=10)
        self.product2 = Product.objects.create(name='Mouse', price=30, stock=50)
        
        self.order = Order.objects.create(user=self.user, total_price=100.00, discount=0)
        self.order_item = OrderItem.objects.create(
                order=self.order,
                product=self.product1,
                quantity=5,
                price=self.product1.price * 5
            )
        self.promo_code = PromoCode.objects.create(
            coupon_code='SAVE10', coupon_name='Save $10', type='FIXED',
            fixed_amount=10.00, start_at=timezone.now(),
            ended_at=timezone.now() + timezone.timedelta(days=30),
            is_active=True, count=100
        )
        
        # URLs
        self.list_url = reverse('order-list')
        self.detail_url = reverse('order-detail', args=[self.order.id])

    def test_get_queryset_authenticated(self):
        """Test that get_queryset returns only the authenticated user's orders"""
        other_user = User.objects.create_user(email='other@example.com', password='otherpass123')
        Order.objects.create(user=other_user, total_price=100.00, discount=0)
        
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # Only the authenticated user's order
        self.assertEqual(response.data[0]['id'], self.order.id)

    def test_get_queryset_unauthenticated(self):
        """Test that unauthenticated users are denied access"""

        self.client.logout()  # Explicitly logout
        self.client.force_authenticate(user=None)  
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    
    def test_create_order_success(self):
        """Test successful order creation with items and promo code"""
        data = {
            'items': [
                {'product': self.product1.id, 'quantity': 2},
                {'product': self.product2.id, 'quantity': 1}
            ],
            'coupon_code': 'SAVE10'
        }
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 2) 
        order = Order.objects.get(id=response.data['id'])
        
        # Check price calculation
        expected_total_before_discount = (self.product1.price * 2) + (self.product2.price * 1)
        expected_discount = 10.00
        expected_total = expected_total_before_discount - expected_discount

        self.assertEqual(float(order.total_price), float(expected_total))
        self.assertEqual(float(order.discount), expected_discount)
        self.assertEqual(order.promo_code.coupon_code, 'SAVE10')
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.status , "PENDING")
        
        

    def test_create_order_invalid_data(self):
        """Test order creation with invalid data (e.g., missing items)"""
        data = {'promo_code': 'SAVE10'}  # No items
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('items', response.data)

    def test_create_order_invalid_promo_code(self):
        """Test order creation with an invalid promo code"""
        data = {
            'items': [{'product': self.product1.id, 'quantity': 1}],
            'coupon_code': 'INVALIDCODE'
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Invalid promo code')

    def test_update_order_full(self):
        """Test full update of an order (replacing items and promo code)"""
        
        new_promo_code = PromoCode.objects.create(
            coupon_code='SAVE50%', coupon_name='Save 50%', type='PERCENTAGE',
            discount_percentage=50, start_at=timezone.now(),
            ended_at=timezone.now() + timezone.timedelta(days=30),
            is_active=True, count=100, max_discount_amount=50.00
        )

        data = {
            'items': [{'product': self.product2.id, 'quantity': 3}],
            'coupon_code': new_promo_code.coupon_code
        }

        response = self.client.put(self.detail_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order = Order.objects.get(id=self.order.id)
        
        # Check updated items
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().product, self.product2)
        self.assertEqual(order.items.first().quantity, 3)
        
        # Check price calculation
        expected_total_before_discount = self.product2.price * 3
        expected_discount = min(expected_total_before_discount * 0.5, new_promo_code.max_discount_amount)
        expected_total = expected_total_before_discount - expected_discount
        
        self.assertEqual(float(order.total_price), float(expected_total))
        self.assertEqual(float(order.discount), expected_discount)
        self.assertEqual(order.promo_code.coupon_code, 'SAVE50%')

    def test_update_order_partial_items(self):
        """Test partial update of items without changing promo code"""
        data = {
            'items': [{'product': self.product2.id, 'quantity': 2}]
        }
        response = self.client.put(self.detail_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order = Order.objects.get(id=self.order.id)
        
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().product, self.product2)
        self.assertEqual(order.items.first().quantity, 2)
        self.assertEqual(float(order.total_price), float(self.product2.price * 2))
        self.assertEqual(float(order.discount), 0) 
        self.assertIsNone(order.promo_code)

    def test_update_order_invalid_promo_code(self):
        """Test update with an invalid promo code"""
        data = {
            'items': [{'product': self.product1.id, 'quantity': 1}],
            'coupon_code': 'INVALIDCODE'
        }
        response = self.client.put(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Invalid promo code')

    def test_retrieve_order(self):
        """Test retrieving an order"""
        OrderItem.objects.create(
            order=self.order,
            product=self.product1,
            quantity=1,
            price=self.product1.price
        )

        self.order.save()

        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.order.id)
        self.assertEqual(len(response.data['items']), 2)
    
    def test_list_orders(self):
        """Test listing all orders for the user"""
        Order.objects.create(user=self.user, total_price=50.00, discount=0)  
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) 

    def test_unauthorized_access(self):
        """Test that another user cannot access or update the order"""
        other_user = User.objects.create_user(email='other@example.com', password='otherpass123')
        self.client.force_authenticate(user=other_user)
        
        # Test retrieve
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Test update
        data = {'items': [{'product_id': self.product1.id, 'quantity': 1}]}
        response = self.client.put(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_order(self):
        """Test deleting an order"""
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Order.objects.count(), 0)
    
    def test_check_stock(self):
        """Test stock check during order creation"""
        data = {
            'items': [
                {'product': self.product1.id, 'quantity': 5},
                {'product': self.product2.id, 'quantity': 10}
            ]
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock, 5)
        self.assertEqual(self.product2.stock, 40)
    
    
    def test_update_order_stock_restoration(self):
        """Test that stock is restored when order items are updated"""
        initial_stock_product1 = self.product1.stock  # 10
        initial_stock_product2 = self.product2.stock  # 50
        
        data = {
            'items': [{'product': self.product2.id, 'quantity': 2}],
            'coupon_code': 'SAVE10'
        }
        response = self.client.put(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        
        self.assertEqual(self.product1.stock, initial_stock_product1 + self.order_item.quantity)  
        self.assertEqual(self.product2.stock, initial_stock_product2 - 2) 
    
    def test_delete_order(self):
        """Test deleting an order"""
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Order.objects.count(), 0)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, 15)
    

class ProductViewSetTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create users
        self.staff_user = User.objects.create_superuser(email='staff@example.com', password='staffpass123')
        self.regular_user = User.objects.create_user(email='user@example.com', password='userpass123')
        
        # Create initial product
        self.product = Product.objects.create(name='Laptop', price=999.99, stock=10)
        
        # URLs
        self.list_url = reverse('product-list')
        self.detail_url = reverse('product-detail', kwargs={'pk': self.product.pk})

    def test_list_products_anyone(self):
        """Test that anyone can list products"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_product_anyone(self):
        """Test that anyone can retrieve a product"""
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Laptop')

    def test_create_product_staff(self):
        """Test that staff can create a product"""
        self.client.force_authenticate(user=self.staff_user)
        data = {'name': 'Keyboard', 'price': 49.99, 'stock': 20}
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(response.data['name'], 'Keyboard')

    def test_create_product_non_staff(self):
        """Test that non-staff cannot create a product"""
        self.client.force_authenticate(user=self.regular_user)
        data = {'name': 'Monitor', 'price': 199.99, 'stock': 10}
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_product_staff(self):
        """Test that staff can update a product"""
        self.client.force_authenticate(user=self.staff_user)
        data = {'name': 'Laptop Updated', 'price': 1099.99, 'stock': 15}
        response = self.client.put(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Laptop Updated')
        self.assertEqual(float(self.product.price), 1099.99)

    def test_update_product_non_staff(self):
        """Test that non-staff cannot update a product"""
        self.client.force_authenticate(user=self.regular_user)
        data = {'name': 'Laptop Updated', 'price': 1099.99, 'stock': 15}
        response = self.client.put(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_list_products_with_only_stock(self):
        """Test that only products with stock are listed"""
        response = self.client.get(self.list_url)
        product2 = Product.objects.create(name='mobile', price=999.99, stock=0)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Laptop')




class PromoCodeViewSetTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Create users
        self.staff_user = User.objects.create_superuser(email='staff@example.com', password='staffpass123')
        self.regular_user = User.objects.create_user(email='user@example.com', password='userpass123')
        
        # Create initial promo code
        self.promo_code = PromoCode.objects.create(
            coupon_code='SAVE10',
            coupon_name='Save $10',
            type='FIXED',
            fixed_amount=10.00,
            start_at=timezone.now() - timezone.timedelta(days=1),
            ended_at=timezone.now() + timezone.timedelta(days=30),
            is_active=True,
            count=100
        )
        
        # URLs
        self.list_url = reverse('promo-code-list')
        self.detail_url = reverse('promo-code-detail', kwargs={'pk': self.promo_code.pk})

    def test_list_promo_codes_anyone(self):
        """Test that anyone can list promo codes without authentication"""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['coupon_code'], 'SAVE10')

    def test_retrieve_promo_code_anyone(self):
        """Test that anyone can retrieve a promo code without authentication"""
        self.client.force_authenticate(user=None)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['coupon_code'], 'SAVE10')

    def test_create_promo_code_staff(self):
        """Test that staff can create a promo code"""
        self.client.force_authenticate(user=self.staff_user)
        data = {
            'coupon_code': 'HALFOFF',
            'coupon_name': '50% Off',
            'type': 'PERCENTAGE',
            'discount_percentage': 50.00,
            'start_at': timezone.now().isoformat(),
            'ended_at': (timezone.now() + timezone.timedelta(days=15)).isoformat(),
            'is_active': True,
            'count': 50
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PromoCode.objects.count(), 2)
        self.assertEqual(response.data['coupon_code'], 'HALFOFF')

    def test_create_promo_code_non_staff(self):
        """Test that non-staff cannot create a promo code"""
        self.client.force_authenticate(user=self.regular_user)
        data = {
            'coupon_code': 'EXTRA20',
            'coupon_name': 'Extra $20',
            'type': 'FIXED',
            'fixed_amount': 20.00,
            'start_at': timezone.now().isoformat(),
            'ended_at': (timezone.now() + timezone.timedelta(days=10)).isoformat(),
            'is_active': True,
            'count': 10
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_promo_code_staff(self):
        """Test that staff can update a promo code"""
        self.client.force_authenticate(user=self.staff_user)
        data = {
            'coupon_code': 'SAVE10',
            'coupon_name': 'Save $15',
            'type': 'FIXED',
            'fixed_amount': 15.00,
            'start_at': timezone.now().isoformat(),
            'ended_at': (timezone.now() + timezone.timedelta(days=30)).isoformat(),
            'is_active': True,
            'count': 100
        }
        response = self.client.put(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.promo_code.refresh_from_db()
        self.assertEqual(self.promo_code.coupon_name, 'Save $15')
        self.assertEqual(float(self.promo_code.fixed_amount), 15.00)

    def test_update_promo_code_non_staff(self):
        """Test that non-staff cannot update a promo code"""
        self.client.force_authenticate(user=self.regular_user)
        data = {
            'coupon_code': 'SAVE10',
            'coupon_name': 'Save $20',
            'type': 'FIXED',
            'fixed_amount': 20.00,
            'start_at': timezone.now().isoformat(),
            'ended_at': (timezone.now() + timezone.timedelta(days=30)).isoformat(),
            'is_active': True,
            'count': 100
        }
        response = self.client.put(self.detail_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_promo_code_unauthenticated(self):
        """Test that unauthenticated users cannot create a promo code"""
        self.client.force_authenticate(user=None)
        data = {
            'coupon_code': 'EXTRA20',
            'coupon_name': 'Extra $20',
            'type': 'FIXED',
            'fixed_amount': 20.00,
            'start_at': timezone.now().isoformat(),
            'ended_at': (timezone.now() + timezone.timedelta(days=10)).isoformat(),
            'is_active': True,
            'count': 10
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)