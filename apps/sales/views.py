from decimal import Decimal
from django import forms
from django.forms import modelformset_factory
from django.db import transaction
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import UpdateView

from apps.inventory.models import InventoryTransaction
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView, DetailView, CreateView
from decimal import Decimal, ROUND_HALF_UP
from apps.core.mixins import MerchantRequiredMixin
from apps.customers.models import Customer
from apps.inventory.models import InventoryTransaction
from apps.products.models import Product
from django.template.loader import render_to_string
from django.http import JsonResponse
from apps.currencies.models import Currency
from apps.currencies.services import get_active_exchange_rate
from django.db.models import Q
from django.views.generic import ListView   

from .cart import (
    add_to_cart,
    cart_totals,
    clear_cart,
    get_cart,
    remove_from_cart,
    update_quantity,
    increment_quantity,
    decrement_quantity,
)
from .forms import PaymentForm
from .models import Sale, SaleItem, Payment
from .services import generate_invoice_number

from apps.core.mixins import (
    MerchantRequiredMixin,
    CashierOrAboveRequiredMixin,
    ManagerOrOwnerRequiredMixin,
    OwnerRequiredMixin,
)
class SaleItemEditForm(forms.ModelForm):
    class Meta:
        model = SaleItem
        fields = ["quantity"]

        widgets = {
            "quantity": forms.NumberInput(attrs={
                "class": "form-control",
                "min": 1,
            })
        }

class POSView(LoginRequiredMixin, MerchantRequiredMixin, TemplateView):
    template_name = "sales/pos.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        merchant = self.get_merchant()
        q = self.request.GET.get("q", "").strip()

        products = Product.objects.filter(merchant=merchant, is_active=True)
        if q:
            from django.db.models import Q
            products = products.filter(
                Q(name__icontains=q) |
                Q(sku__icontains=q) |
                Q(barcode__icontains=q)
            )

        cart = get_cart(self.request.session)
        context["products"] = products[:20]
        context["query"] = q
        context["cart"] = cart
        context["totals"] = cart_totals(cart)
        context["customers"] = Customer.objects.filter(merchant=merchant, is_active=True).order_by("name")
        return context

class AjaxCartResponseMixin:
    def render_cart_response(self, request):
        cart = get_cart(request.session)
        totals = cart_totals(cart)
        merchant = self.get_merchant()

        html_cart_items = render_to_string(
            "sales/partials/cart_items.html",
            {"cart": cart},
            request=request,
        )

        html_cart_summary = render_to_string(
            "sales/partials/cart_summary.html",
            {"cart": cart, "totals": totals},
            request=request,
        )

        html_checkout = render_to_string(
            "sales/partials/checkout_card.html",
            {
                "cart": cart,
                "totals": totals,
                "customers": Customer.objects.filter(
                    merchant=merchant,
                    is_active=True
                ).order_by("name"),
            },
            request=request,
        )

        return JsonResponse({
            "ok": True,
            "cart_items_html": html_cart_items,
            "cart_summary_html": html_cart_summary,
            "checkout_html": html_checkout,
            "cart_count": sum(item["quantity"] for item in cart.values()),
        })    


class AddToCartView(LoginRequiredMixin, MerchantRequiredMixin, AjaxCartResponseMixin, View):
    def post(self, request, pk):
        merchant = self.get_merchant()
        product = get_object_or_404(Product, pk=pk, merchant=merchant, is_active=True)

        cart = get_cart(request.session)
        current_qty = cart.get(str(product.id), {}).get("quantity", 0)

        if product.stock_quantity <= current_qty:
            return JsonResponse({
                "ok": False,
                "message": f"لا يمكن إضافة المزيد من المنتج {product.name}. المخزون المتاح هو {product.stock_quantity}."
            }, status=400)

        add_to_cart(request.session, product)
        return self.render_cart_response(request)

class AddToCartByBarcodeView(LoginRequiredMixin, CashierOrAboveRequiredMixin, AjaxCartResponseMixin, View):
    def post(self, request):
        merchant = self.get_merchant()
        barcode = request.POST.get("barcode", "").strip()

        if not barcode:
            return JsonResponse({"ok": False, "message": "لم يتم إرسال باركود."}, status=400)

        product = Product.objects.filter(
            merchant=merchant,
            barcode=barcode,
            is_active=True
        ).first()

        if not product:
            return JsonResponse({"ok": False, "message": "لا يوجد منتج مطابق لهذا الباركود."}, status=404)

        cart = get_cart(request.session)
        current_qty = cart.get(str(product.id), {}).get("quantity", 0)

        if product.stock_quantity <= current_qty:
            return JsonResponse({
                "ok": False,
                "message": f"لا يمكن إضافة المزيد من المنتج {product.name}. المخزون المتاح هو {product.stock_quantity}."
            }, status=400)

        add_to_cart(request.session, product)
        return self.render_cart_response(request)

class UpdateCartQuantityView(LoginRequiredMixin, MerchantRequiredMixin, View):
    def post(self, request, pk):
        quantity = request.POST.get("quantity")
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return HttpResponseBadRequest("قيمة غير صحيحة.")

        update_quantity(request.session, pk, quantity)
        return redirect("sales:pos")


class IncrementCartItemView(LoginRequiredMixin, MerchantRequiredMixin, AjaxCartResponseMixin, View):
    def post(self, request, pk):
        merchant = self.get_merchant()
        product = get_object_or_404(Product, pk=pk, merchant=merchant, is_active=True)

        cart = get_cart(request.session)
        current_qty = cart.get(str(product.id), {}).get("quantity", 0)

        if product.stock_quantity <= current_qty:
            return JsonResponse({
                "ok": False,
                "message": f"لا يمكن زيادة الكمية. المخزون المتاح للمنتج {product.name} هو {product.stock_quantity}."
            }, status=400)

        increment_quantity(request.session, pk)
        return self.render_cart_response(request)


class DecrementCartItemView(LoginRequiredMixin, MerchantRequiredMixin, AjaxCartResponseMixin, View):
    def post(self, request, pk):
        decrement_quantity(request.session, pk)
        return self.render_cart_response(request)


class RemoveFromCartView(LoginRequiredMixin, MerchantRequiredMixin, AjaxCartResponseMixin, View):
    def post(self, request, pk):
        remove_from_cart(request.session, pk)
        return self.render_cart_response(request)


class ClearCartView(LoginRequiredMixin, MerchantRequiredMixin, AjaxCartResponseMixin, View):
    def post(self, request):
        clear_cart(request.session)
        return self.render_cart_response(request)


class CheckoutView(LoginRequiredMixin, MerchantRequiredMixin, View):
    def post(self, request):
        merchant = self.get_merchant()
        cart = get_cart(request.session)

        if not cart:
            messages.error(request, "السلة فارغة.")
            return redirect("sales:pos")

        payment_type = request.POST.get("payment_type", "cash")
        customer_id = request.POST.get("customer")
        payment_currency_code = request.POST.get("payment_currency", "USD")
        notes = request.POST.get("notes", "").strip()
        discount_raw = request.POST.get("discount_amount", "0").strip()

        # قراءة الخصم والتحقق منه
        try:
            discount_amount = Decimal(discount_raw or "0")
        except Exception:
            messages.error(request, "قيمة الخصم غير صحيحة.")
            return redirect("sales:pos")

        if discount_amount < 0:
            messages.error(request, "الخصم لا يمكن أن يكون سالبًا.")
            return redirect("sales:pos")

        customer = None
        if customer_id:
            customer = Customer.objects.filter(merchant=merchant, pk=customer_id).first()

        if payment_type == "debt" and not customer:
            messages.error(request, "يجب اختيار عميل عند البيع بالدين.")
            return redirect("sales:pos")

        try:
            pricing_currency = Currency.objects.get(code="USD")
            payment_currency = Currency.objects.get(code=payment_currency_code)
            exchange_rate = get_active_exchange_rate("USD", payment_currency_code)
        except Currency.DoesNotExist:
            messages.error(request, "عملة الدفع غير موجودة.")
            return redirect("sales:pos")
        except Exception as e:
            messages.error(request, f"تعذر جلب سعر الصرف: {str(e)}")
            return redirect("sales:pos")

        # تحقق من المخزون
        product_ids = [int(pid) for pid in cart.keys()]
        products = Product.objects.filter(merchant=merchant, id__in=product_ids)
        products_map = {p.id: p for p in products}

        subtotal_before_discount = Decimal("0")

        for pid, item in cart.items():
            product = products_map.get(int(pid))
            if not product:
                messages.error(request, "يوجد منتج غير موجود في السلة.")
                return redirect("sales:pos")

            quantity = int(item["quantity"])
            unit_price = Decimal(item["price"])

            if product.stock_quantity < quantity:
                messages.error(request, f"المخزون غير كافٍ للمنتج: {product.name}")
                return redirect("sales:pos")

            subtotal_before_discount += unit_price * quantity

        # تحقق من منطق الخصم
        if discount_amount > subtotal_before_discount:
            messages.error(request, "الخصم لا يمكن أن يكون أكبر من قيمة الفاتورة.")
            return redirect("sales:pos")

        with transaction.atomic():
            sale = Sale.objects.create(
                merchant=merchant,
                customer=customer,
                invoice_number=generate_invoice_number(),
                payment_type=payment_type,
                payment_status="unpaid" if payment_type == "debt" else "paid",
                created_by=request.user,
                notes=notes,
                pricing_currency=pricing_currency,
                payment_currency=payment_currency,
                exchange_rate=exchange_rate,
                discount_amount=discount_amount,
            )

            for pid, item in cart.items():
                product = products_map[int(pid)]
                quantity = int(item["quantity"])
                unit_price = Decimal(item["price"])
                unit_cost = Decimal(item["cost"])

                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    unit_cost=unit_cost,
                )


                product.stock_quantity -= quantity
                product.save(update_fields=["stock_quantity"])

                InventoryTransaction.objects.create(
                    merchant=merchant,
                    product=product,
                    transaction_type="sale",
                    quantity=-quantity,
                    reference_sale=sale,
                    note=f"Sale {sale.invoice_number}",
                )

            # إعادة حساب الإجماليات بعد إضافة العناصر والخصم
            sale.recalculate_totals()
            sale.save()

            if payment_type == "cash":
                if customer:
                    # تسجيل دفعة تلقائية بالمبلغ النهائي بعد الخصم
                    Payment.objects.create(
                        sale=sale,
                        customer=customer,
                        merchant=merchant,
                        amount=sale.total_amount,  # القيمة المرجعية بالدولار بعد الخصم
                        original_amount=sale.total_amount_payment_currency,  # القيمة الفعلية بعملة الدفع
                        note="دفعة نقدية تلقائية",
                        created_by=request.user,
                        currency=payment_currency,
                        exchange_rate=exchange_rate,
                    )

                    sale.recalculate_totals()
                    sale.save()
                else:
                    # بيع نقدي بدون عميل
                    sale.amount_paid = sale.total_amount
                    sale.amount_due = Decimal("0.00")
                    sale.payment_status = "paid"
                    sale.save(update_fields=[
                        "subtotal",
                        "discount_amount",
                        "total_amount",
                        "total_cost",
                        "total_profit",
                        "amount_paid",
                        "amount_due",
                        "payment_status",
                        "total_amount_payment_currency",
                    ])

            else:
                # بيع بالدين: المبلغ المستحق هو الإجمالي بعد الخصم
                sale.recalculate_totals()
                sale.save()

            clear_cart(request.session)

        messages.success(request, f"تم حفظ الفاتورة {sale.invoice_number} بنجاح.")
        return redirect("sales:detail", pk=sale.pk)


class SaleDetailView(LoginRequiredMixin, MerchantRequiredMixin, DetailView):
    model = Sale
    template_name = "sales/detail.html"
    context_object_name = "sale"

    def get_queryset(self):
        return Sale.objects.filter(merchant=self.get_merchant()).prefetch_related("items__product", "payments")


class PaymentCreateView(LoginRequiredMixin, MerchantRequiredMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = "sales/payment_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.sale = get_object_or_404(
            Sale,
            pk=self.kwargs["sale_pk"],
            merchant=self.get_merchant()
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        currency = form.cleaned_data["currency"]
        amount_in_payment_currency = form.cleaned_data["amount"]

        exchange_rate = get_active_exchange_rate("USD", currency.code)

        amount_in_usd = (
            Decimal(amount_in_payment_currency) / Decimal(exchange_rate)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if amount_in_usd > self.sale.amount_due:
            form.add_error("amount", "قيمة الدفعة أكبر من المبلغ المستحق.")
            return self.form_invalid(form)

        form.instance.sale = self.sale
        form.instance.customer = self.sale.customer
        form.instance.merchant = self.sale.merchant
        form.instance.created_by = self.request.user
        form.instance.currency = currency
        form.instance.exchange_rate = exchange_rate
        form.instance.original_amount = amount_in_payment_currency
        form.instance.amount = amount_in_usd

        response = super().form_valid(form)

        self.sale.recalculate_totals()
        self.sale.save()

        messages.success(self.request, "تمت إضافة الدفعة بنجاح.")
        return response

    def get_success_url(self):
        return reverse_lazy("sales:detail", kwargs={"pk": self.sale.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sale"] = self.sale
        return context
    
class SaleListView(LoginRequiredMixin, MerchantRequiredMixin, ListView):
    model = Sale
    template_name = "sales/list.html"
    context_object_name = "sales"
    paginate_by = 20

    def get_queryset(self):
        merchant = self.get_merchant()

        q = self.request.GET.get("q", "").strip()
        payment_type = self.request.GET.get("payment_type", "").strip()
        payment_status = self.request.GET.get("payment_status", "").strip()

        qs = Sale.objects.filter(
            merchant=merchant
        ).select_related(
            "customer", "payment_currency", "pricing_currency"
        ).order_by("-created_at")

        if q:
            qs = qs.filter(
                Q(invoice_number__icontains=q) |
                Q(customer__name__icontains=q)
            )

        if payment_type:
            qs = qs.filter(payment_type=payment_type)

        if payment_status:
            qs = qs.filter(payment_status=payment_status)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "").strip()
        context["selected_payment_type"] = self.request.GET.get("payment_type", "").strip()
        context["selected_payment_status"] = self.request.GET.get("payment_status", "").strip()
        return context

class SalePrintView(LoginRequiredMixin, MerchantRequiredMixin, DetailView):
    model = Sale
    template_name = "sales/print_invoice.html"
    context_object_name = "sale"

    def get_queryset(self):
        return Sale.objects.filter(
            merchant=self.get_merchant()
        ).select_related(
            "customer", "pricing_currency", "payment_currency", "created_by"
        ).prefetch_related(
            "items__product", "payments"
        )


class SaleEditView(LoginRequiredMixin, ManagerOrOwnerRequiredMixin, DetailView):
    model = Sale
    template_name = "sales/edit.html"
    context_object_name = "sale"

    def get_queryset(self):
        return Sale.objects.filter(
            merchant=self.get_merchant()
        ).prefetch_related("items__product", "payments")

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        formset_class = modelformset_factory(
            SaleItem,
            form=SaleItemEditForm,
            extra=0,
            can_delete=False,
        )

        formset = formset_class(
            queryset=self.object.items.select_related("product").all()
        )

        return self.render_to_response(
            self.get_context_data(formset=formset)
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        formset_class = modelformset_factory(
            SaleItem,
            form=SaleItemEditForm,
            extra=0,
            can_delete=False,
        )

        formset = formset_class(
            request.POST,
            queryset=self.object.items.select_related("product").all()
        )

        if not formset.is_valid():
            return self.render_to_response(
                self.get_context_data(formset=formset)
            )

        with transaction.atomic():
            for form in formset:
                sale_item = form.save(commit=False)
                old_item = SaleItem.objects.select_for_update().get(pk=sale_item.pk)
                product = old_item.product

                old_qty = old_item.quantity
                new_qty = sale_item.quantity

                diff = new_qty - old_qty

                if diff == 0:
                    continue

                product = type(product).objects.select_for_update().get(pk=product.pk)

                if diff > 0:
                    if product.stock_quantity < diff:
                        form.add_error(
                            "quantity",
                            f"المخزون غير كافٍ. المتاح حاليًا: {product.stock_quantity}"
                        )
                        raise ValueError("Insufficient stock")

                    product.stock_quantity -= diff

                    InventoryTransaction.objects.create(
                        merchant=self.object.merchant,
                        product=product,
                        transaction_type="sale",
                        quantity=diff,
                        reference_sale=self.object,
                        note=f"تعديل فاتورة {self.object.invoice_number}: زيادة كمية البيع",
                    )

                else:
                    returned_qty = abs(diff)
                    product.stock_quantity += returned_qty

                    InventoryTransaction.objects.create(
                        merchant=self.object.merchant,
                        product=product,
                        transaction_type="adjustment_add",
                        quantity=returned_qty,
                        reference_sale=self.object,
                        note=f"تعديل فاتورة {self.object.invoice_number}: تخفيض كمية البيع",
                    )

                product.save(update_fields=["stock_quantity"])

                old_item.quantity = new_qty
                old_item.save()

            self.object.recalculate_totals()
            self.object.save()

        messages.success(request, "تم تعديل الفاتورة وتحديث المخزون بنجاح.")
        return redirect("sales:detail", pk=self.object.pk)

class SyncStatusView(LoginRequiredMixin, CashierOrAboveRequiredMixin, TemplateView):
    template_name = "sales/sync_status.html"    

class OfflinePOSShellView(LoginRequiredMixin, CashierOrAboveRequiredMixin, TemplateView):
    template_name = "sales/pos_offline_shell.html"


