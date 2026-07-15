from django.urls import path
from . import views

app_name = 'stationery'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('inventory/', views.inventory_list, name='inventory'),
    path('inventory/add/', views.add_product, name='add_product'),
    path('sale/new/', views.new_sale, name='new_sale'),
]