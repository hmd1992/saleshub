from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from decimal import Decimal, ROUND_HALF_UP

from apps.core.models import TimeStampedModel
from uuid import uuid4

def generate_invoice_number():
    return f"INV-{uuid4().hex[:10].upper()}"

class Sale(TimeStampedModel):
    PAYMENT_TYPE_CHOICES = [
        ("cash", "Cash"),
        ("debt", "Debt"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("paid", "Paid"),
        ("unpaid", "Unpaid"),
        ("partially_paid", "Partially Paid"),
    ]

    pricing_currency = models.ForeignKey(
        "currencies.Currency",
        on_delete=models.PROTECT,
        related_name="sales_pricing_currency",
        null=True,
        blank=True
    )
    payment_currency = models.ForeignKey(
        "currencies.Currency",
        on_delete=models.PROTECT,
        related_name="sales_payment_currency",
        null=True,
        blank=True
    )
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=6, default=1)

    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="sales"
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales"
    )
    invoice_number = models.CharField(max_length=50, db_index=True, unique=True)
    offline_id = models.CharField(max_length=100, blank=True, null=True, unique=True, db_index=True)
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPE_CHOICES, default="cash")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="paid")

    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_profit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount_payment_currency = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sales"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.invoice_number

    def clean(self):
        if self.payment_type == "debt" and not self.customer:
            raise ValidationError("العميل مطلوب عند البيع بالدين.")

        if self.discount_amount < 0:
            raise ValidationError("الخصم لا يمكن أن يكون سالبًا.")

    def refresh_payment_status(self):
        if self.amount_due <= 0:
            self.payment_status = "paid"
        elif self.amount_paid > 0:
            self.payment_status = "partially_paid"
        else:
            self.payment_status = "unpaid"

    def recalculate_totals(self):
        items = self.items.all()

        subtotal = items.aggregate(total=Sum("line_total"))["total"] or Decimal("0")
        total_cost = items.aggregate(
            total=Sum(models.F("unit_cost") * models.F("quantity"))
        )["total"] or Decimal("0")

        subtotal = Decimal(subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_cost = Decimal(total_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        discount = Decimal(self.discount_amount or 0).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if discount < Decimal("0.00"):
            discount = Decimal("0.00")

        if discount > subtotal:
            discount = subtotal

        self.subtotal = subtotal
        self.discount_amount = discount
        self.total_amount = (subtotal - discount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        self.total_cost = total_cost
        self.total_profit = (self.total_amount - self.total_cost).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if self.payment_type == "cash":
            # الفاتورة النقدية تعتبر مسددة بالكامل دائمًا.
            self.amount_paid = self.total_amount
            self.amount_due = Decimal("0.00")
            self.payment_status = "paid"

        else:
            # فواتير الدين تعتمد على الدفعات المسجلة.
            paid = (
                self.payments.aggregate(total=Sum("amount"))["total"]
                or Decimal("0")
            )

            self.amount_paid = Decimal(paid).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            self.amount_due = (
                self.total_amount - self.amount_paid
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            # منع ظهور مبلغ مستحق سالب.
            if self.amount_due < Decimal("0.00"):
                self.amount_due = Decimal("0.00")

            self.refresh_payment_status()

        if self.exchange_rate and self.payment_currency and self.pricing_currency:
            self.total_amount_payment_currency = (
                self.total_amount * Decimal(self.exchange_rate)
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            self.total_amount_payment_currency = self.total_amount.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="items"
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="sale_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Sale Item"
        verbose_name_plural = "Sale Items"

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError("الكمية يجب أن تكون أكبر من صفر.")

    def save(self, *args, **kwargs):
        self.line_total = Decimal(self.quantity) * self.unit_price
        self.full_clean()
        super().save(*args, **kwargs)


class Payment(TimeStampedModel):
    currency = models.ForeignKey(
        "currencies.Currency",
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True
    )
    merchant = models.ForeignKey(
        "merchants.Merchant",
        on_delete=models.CASCADE,
        related_name="payments"
    )

    amount = models.DecimalField(max_digits=18, decimal_places=2)
    original_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.customer.name} - {self.amount}"

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("قيمة الدفعة يجب أن تكون أكبر من صفر.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)