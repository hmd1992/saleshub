from datetime import date
from apps.products.models import Product
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.views.generic import TemplateView
from django.db import models
from apps.sales.models import Sale, SaleItem
from apps.core.mixins import CashierOrAboveRequiredMixin
from apps.expenses.models import Expense
from decimal import Decimal
class DashboardView(LoginRequiredMixin,CashierOrAboveRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        staff_profile = getattr(self.request.user, "staff_profile", None)
        if not staff_profile or not staff_profile.merchant:
            context.update({
                "total_sales": 0,
                "total_profit": 0,
                "total_invoices": 0,
                "total_debt": 0,
                "top_products": [],
            })
            return context

        merchant = staff_profile.merchant
        today = date.today()
        low_stock_count = Product.objects.filter(
            merchant=merchant,
            is_active=True,
            stock_quantity__gt=0,
            stock_quantity__lte=models.F("reorder_level")
        ).count()

        out_of_stock_count = Product.objects.filter(
            merchant=merchant,
            is_active=True,
            stock_quantity__lte=0
        ).count()

        sales_today = Sale.objects.filter(
            merchant=merchant,
            created_at__date=today
        )

        total_sales = sales_today.aggregate(total=Sum("total_amount"))["total"] or 0
        total_profit = sales_today.aggregate(total=Sum("total_profit"))["total"] or 0
        total_expenses = Expense.objects.filter(
                merchant=merchant
            ).aggregate(
                total=Sum("amount_usd")
            )["total"] or 0
        net_profit = total_profit - total_expenses
        total_invoices = sales_today.count()

        total_debt = Sale.objects.filter(
            merchant=merchant,
            payment_status__in=["unpaid", "partially_paid"]
        ).aggregate(total=Sum("amount_due"))["total"] or 0

        top_products = (
            SaleItem.objects.filter(
                sale__merchant=merchant,
                sale__created_at__date=today
            )
            .values("product__name")
            .annotate(total_qty=Sum("quantity"))
            .order_by("-total_qty")[:5]
        )
        all_sales_profit = Sale.objects.filter(
            merchant=merchant
        ).aggregate(
            total=Sum("total_profit")
        )["total"] or Decimal("0")

        all_expenses = Expense.objects.filter(
            merchant=merchant
        ).aggregate(
            total=Sum("amount_usd")
        )["total"] or Decimal("0")

        net_profit_all = all_sales_profit - all_expenses
        context.update({
            "total_sales": total_sales,
            "total_profit": total_profit,
            "total_invoices": total_invoices,
            "total_debt": total_debt,
            "top_products": top_products,
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "all_sales_profit": all_sales_profit,
            "all_expenses": all_expenses,
            "net_profit_all": net_profit_all,
        })

        return context

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views import View


class ServiceWorkerView(View):
    def get(self, request, *args, **kwargs):
        js_content = render_to_string("service-worker.js")
        return HttpResponse(js_content, content_type="application/javascript")    