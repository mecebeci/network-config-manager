from django.urls import path

from . import views

urlpatterns = [
    # Backup
    path('backup/', views.backup_page, name='backup'),
    path('backup/run/', views.backup_run, name='backup_run'),
    path('devices/<int:pk>/backups/', views.device_backups, name='device_backups'),
    path('backups/<int:pk>/', views.backup_detail, name='backup_detail'),
    path('backups/<int:pk>/download/', views.backup_download, name='backup_download'),
]
