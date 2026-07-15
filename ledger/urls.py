from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.overview, name='overview'),
    path('payments/new/', views.new_payment, name='new_payment'),
    path('payments/<int:pk>/edit/', views.new_payment, name='edit_payment'),
    path('payments/<int:pk>/delete/', views.delete_payment, name='delete_payment'),
    path('ledger/', views.ledger, name='ledger'),
    path('ledger/export/', views.export_csv, name='export_csv'),
    path('services/', views.services, name='services'),
    path('services/<int:pk>/edit/', views.edit_service, name='edit_service'),
    path('services/<int:pk>/delete/', views.delete_service, name='delete_service'),
    path('login/', auth_views.LoginView.as_view(template_name='ledger/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
