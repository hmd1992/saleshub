from django.urls import path
from .views import (
    POSView,
    SaleListView,
    AddToCartView,
    AddToCartByBarcodeView,
    UpdateCartQuantityView,
    IncrementCartItemView,
    DecrementCartItemView,
    RemoveFromCartView,
    ClearCartView,
    CheckoutView,
    SaleDetailView,
    PaymentCreateView,
    SalePrintView,
    SyncStatusView,
    OfflinePOSShellView,
    SaleEditView
)

app_name = "sales"

urlpatterns = [
    path("pos/", POSView.as_view(), name="pos"),
    path("cart/add/<int:pk>/", AddToCartView.as_view(), name="cart_add"),
    path("cart/add-by-barcode/", AddToCartByBarcodeView.as_view(), name="cart_add_by_barcode"),
    path("cart/update/<int:pk>/", UpdateCartQuantityView.as_view(), name="cart_update"),
    path("cart/remove/<int:pk>/", RemoveFromCartView.as_view(), name="cart_remove"),
    path("cart/clear/", ClearCartView.as_view(), name="cart_clear"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("<int:pk>/", SaleDetailView.as_view(), name="detail"),
    path("<int:sale_pk>/payment/add/", PaymentCreateView.as_view(), name="payment_add"),
    path("cart/increment/<int:pk>/", IncrementCartItemView.as_view(), name="cart_increment"),
    path("cart/decrement/<int:pk>/", DecrementCartItemView.as_view(), name="cart_decrement"),
    path("", SaleListView.as_view(), name="list"),
    path("<int:pk>/print/", SalePrintView.as_view(), name="print"),
    path("sync-status/", SyncStatusView.as_view(), name="sync_status"),
    path("pos-offline-shell/", OfflinePOSShellView.as_view(), name="pos_offline_shell"),
    path("<int:pk>/edit/", SaleEditView.as_view(), name="edit"),
]