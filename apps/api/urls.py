from django.urls import path
from .views import OfflineBootstrapView
from .views import OfflineBootstrapView, OfflineSyncSalesView

app_name = "api"

urlpatterns = [
    path("offline/bootstrap/", OfflineBootstrapView.as_view(), name="offline_bootstrap"),
    path("offline/sync-sales/", OfflineSyncSalesView.as_view(), name="offline_sync_sales"),
]
