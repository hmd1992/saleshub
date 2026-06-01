from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView
from django.core.exceptions import PermissionDenied
from apps.core.mixins import ManagerOrOwnerRequiredMixin
from django.http import HttpResponseRedirect
from .models import Expense
from .forms import ExpenseForm
from decimal import Decimal
from django.db.models import Sum
from django.views.generic import ListView, CreateView, UpdateView,DeleteView

from decimal import Decimal
from io import BytesIO

from django.db.models import Sum, Count, Avg, Max
from django.http import HttpResponse
from django.views.generic import TemplateView
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

def get_user_merchant(request, view=None):
    staff_profile = getattr(request.user, "staff_profile", None)
    merchant = getattr(staff_profile, "merchant", None)

    if merchant is None and view is not None:
        merchant = view.get_merchant()

    return merchant

class ExpenseListView(ManagerOrOwnerRequiredMixin, ListView):
    model = Expense
    template_name = "expenses/list.html"
    context_object_name = "expenses"

    def get_merchant_for_user(self):
        staff_profile = getattr(self.request.user, "staff_profile", None)
        merchant = getattr(staff_profile, "merchant", None)

        if merchant is None:
            merchant = self.get_merchant()

        return merchant

    def get_queryset(self):
        merchant = self.get_merchant_for_user()

        if merchant is None:
            return Expense.objects.none()

        return Expense.objects.filter(
            merchant=merchant
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        total_expenses = self.get_queryset().aggregate(
            total=Sum("amount_usd")
        )["total"] or Decimal("0")

        context["total_expenses"] = total_expenses
        context["expenses_count"] = self.get_queryset().count()

        return context

class ExpenseCreateView(ManagerOrOwnerRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "expenses/create.html"
    success_url = reverse_lazy("expenses:list")

    def form_valid(self, form):
        staff_profile = getattr(self.request.user, "staff_profile", None)
        merchant = getattr(staff_profile, "merchant", None)

        if merchant is None:
            merchant = self.get_merchant()

        if merchant is None:
            raise PermissionDenied("لا يمكن إضافة مصروف بدون متجر مرتبط بالمستخدم.")

        expense = form.save(commit=False)
        expense.merchant = merchant
        expense.created_by = self.request.user
        expense.save()
        self.object = expense

        messages.success(self.request, "تمت إضافة المصروف بنجاح.")

        return HttpResponseRedirect(self.get_success_url())
    
class ExpenseUpdateView(ManagerOrOwnerRequiredMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "expenses/edit.html"
    success_url = reverse_lazy("expenses:list")

    def get_queryset(self):
        staff_profile = getattr(self.request.user, "staff_profile", None)
        merchant = getattr(staff_profile, "merchant", None)

        if merchant is None:
            merchant = self.get_merchant()

        if merchant is None:
            return Expense.objects.none()

        return Expense.objects.filter(merchant=merchant)

    def form_valid(self, form):
        expense = form.save(commit=False)

        staff_profile = getattr(self.request.user, "staff_profile", None)
        merchant = getattr(staff_profile, "merchant", None)

        if merchant is None:
            merchant = self.get_merchant()

        if merchant is None:
            raise PermissionDenied("لا يمكن تعديل مصروف بدون متجر مرتبط بالمستخدم.")

        expense.merchant = merchant
        expense.save()

        messages.success(self.request, "تم تعديل المصروف بنجاح.")

        return HttpResponseRedirect(self.get_success_url())    

class ExpenseDeleteView(ManagerOrOwnerRequiredMixin, DeleteView):
    model = Expense
    template_name = "expenses/delete.html"
    success_url = reverse_lazy("expenses:list")

    def get_queryset(self):
        staff_profile = getattr(self.request.user, "staff_profile", None)
        merchant = getattr(staff_profile, "merchant", None)

        if merchant is None:
            merchant = self.get_merchant()

        if merchant is None:
            return Expense.objects.none()

        return Expense.objects.filter(merchant=merchant)

    def form_valid(self, form):
        messages.success(self.request, "تم حذف المصروف بنجاح.")
        return super().form_valid(form)    
    

class ExpenseReportView(ManagerOrOwnerRequiredMixin, TemplateView):
    template_name = "expenses/report.html"

    def get_queryset(self):
        merchant = get_user_merchant(self.request, self)

        if merchant is None:
            return Expense.objects.none()

        date_from = self.request.GET.get("date_from", "").strip()
        date_to = self.request.GET.get("date_to", "").strip()
        category = self.request.GET.get("category", "").strip()

        expenses = Expense.objects.filter(
            merchant=merchant
        ).select_related(
            "currency", "created_by"
        ).order_by("-expense_date", "-created_at")

        if date_from:
            expenses = expenses.filter(expense_date__gte=date_from)

        if date_to:
            expenses = expenses.filter(expense_date__lte=date_to)

        if category:
            expenses = expenses.filter(category=category)

        return expenses

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expenses = self.get_queryset()

        summary = expenses.aggregate(
            total_expenses=Sum("amount_usd"),
            expenses_count=Count("id"),
            avg_expense=Avg("amount_usd"),
            max_expense=Max("amount_usd"),
        )

        category_summary = (
            expenses.values("category")
            .annotate(
                total=Sum("amount_usd"),
                count=Count("id"),
            )
            .order_by("-total")
        )

        context.update({
            "expenses": expenses[:300],
            "total_expenses": summary["total_expenses"] or Decimal("0"),
            "expenses_count": summary["expenses_count"] or 0,
            "avg_expense": summary["avg_expense"] or Decimal("0"),
            "max_expense": summary["max_expense"] or Decimal("0"),
            "category_summary": category_summary,
            "date_from": self.request.GET.get("date_from", "").strip(),
            "date_to": self.request.GET.get("date_to", "").strip(),
            "selected_category": self.request.GET.get("category", "").strip(),
            "category_choices": Expense.CATEGORY_CHOICES,
        })

        return context

class ExpenseReportExportExcelView(ManagerOrOwnerRequiredMixin, TemplateView):
    def get_queryset(self):
        merchant = get_user_merchant(self.request, self)

        if merchant is None:
            return Expense.objects.none()

        date_from = self.request.GET.get("date_from", "").strip()
        date_to = self.request.GET.get("date_to", "").strip()
        category = self.request.GET.get("category", "").strip()

        expenses = Expense.objects.filter(
            merchant=merchant
        ).select_related(
            "currency", "created_by"
        ).order_by("-expense_date", "-created_at")

        if date_from:
            expenses = expenses.filter(expense_date__gte=date_from)

        if date_to:
            expenses = expenses.filter(expense_date__lte=date_to)

        if category:
            expenses = expenses.filter(category=category)

        return expenses

    def get(self, request, *args, **kwargs):
        expenses = self.get_queryset()

        wb = Workbook()
        ws = wb.active
        ws.title = "Expenses Report"

        headers = [
            "Date",
            "Title",
            "Category",
            "Amount",
            "Currency",
            "Exchange Rate",
            "Amount USD",
            "Created By",
            "Note",
        ]

        ws.append(headers)

        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        for expense in expenses:
            ws.append([
                expense.expense_date.strftime("%Y-%m-%d") if expense.expense_date else "",
                expense.title,
                expense.get_category_display(),
                float(expense.amount or 0),
                expense.currency.code if expense.currency else "",
                float(expense.exchange_rate or 0),
                float(expense.amount_usd or 0),
                expense.created_by.username if expense.created_by else "",
                expense.note or "",
            ])

        column_widths = {
            "A": 14,
            "B": 28,
            "C": 18,
            "D": 14,
            "E": 12,
            "F": 16,
            "G": 16,
            "H": 18,
            "I": 35,
        }

        for col, width in column_widths.items():
            ws.column_dimensions[col].width = width

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="expenses_report.xlsx"'

        return response        