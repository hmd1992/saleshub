from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path ,re_path
from apps.core.views import DashboardView
from apps.core.views import ServiceWorkerView
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("merchants/", include("apps.merchants.urls")),
    path("", include("apps.core.urls")),
    path("products/", include("apps.products.urls")),
    path("customers/", include("apps.customers.urls")),
    path("sales/", include("apps.sales.urls")),
    path("currencies/", include("apps.currencies.urls")),
    path("", DashboardView.as_view(), name="dashboard"),
    path("reports/", include("apps.reports.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("api/", include("apps.api.urls")),
    path("service-worker.js", ServiceWorkerView.as_view(), name="service_worker"),
    path("expenses/", include("apps.expenses.urls")),
]

urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]