from django import forms
from .models import Expense


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            "category",
            "title",
            "amount",
            "currency",
            "exchange_rate",
            "expense_date",
            "note",
        ]

        widgets = {
            "expense_date": forms.DateInput(
                attrs={"type": "date"}
            )
        }