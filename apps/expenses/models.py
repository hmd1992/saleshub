from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Expense(TimeStampedModel):
    CATEGORY_CHOICES = [
        ("rent", "إيجار"),
        ("salary", "رواتب"),
        ("transport", "نقل"),
        ("utilities", "خدمات"),
        ("marketing", "تسويق"),
        ("maintenance", "صيانة"),
        ("purchase_related", "مصاريف شراء"),
        ("other", "أخرى"),
    ]

    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="expenses",
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="other",
    )

    title = models.CharField(max_length=255)

    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    currency = models.ForeignKey(
        "currencies.Currency",
        on_delete=models.PROTECT,
        related_name="expenses",
        null=True,
        blank=True,
    )

    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=1,
    )

    amount_usd = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )

    expense_date = models.DateField()

    note = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_expenses",
    )

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        indexes = [
            models.Index(fields=["merchant", "expense_date"]),
            models.Index(fields=["merchant", "category"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.amount_usd}"

    def save(self, *args, **kwargs):
        amount = Decimal(self.amount or 0)
        rate = Decimal(self.exchange_rate or 1)

        self.amount_usd = (amount / rate).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        super().save(*args, **kwargs)