from django.urls import path
from . import views

app_name = 'customer'

urlpatterns = [
    path('', views.catalog, name='catalog'),
    path('cart/', views.view_cart, name='cart'),
    path('cart/add/<str:source>/<int:source_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<str:key>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.order_history, name='order_history'),
    path('orders/<int:pk>/', views.order_status, name='order_status'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]