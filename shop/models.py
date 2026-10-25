from django.db import models


class Setting(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.key}={self.value}"

    @classmethod
    def get_num(cls, key, default):
        try:
            return float(cls.objects.get(key=key).value)
        except (cls.DoesNotExist, ValueError):
            return default

    @classmethod
    def set(cls, key, value):
        cls.objects.update_or_create(key=key, defaults={"value": str(value)})


class Customer(models.Model):
    TYPE_CHOICES = [
        ("individual", "فرد"),
        ("restaurant", "مطعم"),
        ("trader", "تاجر جملة"),
    ]
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True, default="")
    phone2 = models.CharField(max_length=30, blank=True, default="")
    customer_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="individual")
    address = models.CharField(max_length=300, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    debt = models.FloatField(default=0)  # outstanding balance in USD

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def as_dict(self):
        from django.utils import timezone
        return {
            "id": str(self.id),
            "name": self.name,
            "phone": self.phone,
            "phone2": self.phone2,
            "customerType": self.customer_type,
            "address": self.address,
            "notes": self.notes,
            "debt": self.debt,
            "createdAt": timezone.localtime(self.created_at).strftime("%Y-%m-%d"),
        }


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    debt = models.FloatField(default=0)  # amount we owe them

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def as_dict(self):
        from django.utils import timezone
        return {
            "id": str(self.id),
            "name": self.name,
            "company": self.company,
            "phone": self.phone,
            "notes": self.notes,
            "debt": self.debt,
            "createdAt": timezone.localtime(self.created_at).strftime("%Y-%m-%d"),
        }


class Product(models.Model):
    name = models.CharField(max_length=200, unique=True)
    category = models.CharField(max_length=100, default="غير مصنف", blank=True)
    unit = models.CharField(max_length=50, blank=True, default="قطعة")
    cost_usd = models.FloatField(default=0)
    price_usd = models.FloatField(default=0)
    wholesale_price_usd = models.FloatField(default=0)
    stock = models.FloatField(default=0)
    low_stock_threshold = models.FloatField(default=5)
    expiry_date = models.DateField(null=True, blank=True)
    image = models.TextField(blank=True, default="")  # compressed JPEG data-URL

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def as_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "category": self.category or "غير مصنف",
            "unit": self.unit or "قطعة",
            "costUSD": self.cost_usd,
            "priceUSD": self.price_usd,
            "wholesalePriceUSD": self.wholesale_price_usd,
            "stock": self.stock,
            "lowStockThreshold": self.low_stock_threshold,
            "expiryDate": self.expiry_date.strftime("%Y-%m-%d") if self.expiry_date else "",
            "image": self.image,
            "lowStock": self.stock <= self.low_stock_threshold,
        }


class Move(models.Model):
    TYPE_CHOICES = [("in", "دخول"), ("out", "خروج")]
    date = models.DateTimeField(auto_now_add=True)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=200)
    type = models.CharField(max_length=3, choices=TYPE_CHOICES)
    qty = models.FloatField()
    note = models.CharField(max_length=300, blank=True, default="")
    receipt_no = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        ordering = ["date", "id"]

    def as_dict(self):
        from django.utils import timezone
        local = timezone.localtime(self.date)
        return {
            "id": str(self.id),
            "date": local.strftime("%Y-%m-%dT%H:%M:%S"),
            "productId": str(self.product_id) if self.product_id else "",
            "productName": self.product_name,
            "type": self.type,
            "qty": self.qty,
            "note": self.note,
            "receiptNo": self.receipt_no,
        }


class Receipt(models.Model):
    PAYMENT_CHOICES = [("cash", "نقداً"), ("card", "بطاقة"), ("debt", "دين")]
    PRICE_CHOICES = [("retail", "مفرق"), ("wholesale", "جملة")]

    no = models.IntegerField(unique=True)
    date = models.CharField(max_length=10)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL)
    customer_name = models.CharField(max_length=200, blank=True, default="")
    rate = models.FloatField()
    currency = models.CharField(max_length=10, default="both")
    price_type = models.CharField(max_length=10, choices=PRICE_CHOICES, default="retail")
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="cash")
    discount = models.FloatField(default=0)  # in USD
    items_json = models.TextField(default="[]")
    total_usd = models.FloatField(default=0)
    total_lbp = models.FloatField(default=0)
    voided = models.BooleanField(default=False)

    class Meta:
        ordering = ["no"]

    def __str__(self):
        return f"فاتورة {self.no}"

    def as_dict(self):
        return {
            "no": self.no,
            "date": self.date,
            "customerId": str(self.customer_id) if self.customer_id else "",
            "customerName": self.customer_name or (self.customer.name if self.customer else ""),
            "rate": self.rate,
            "currency": self.currency,
            "priceType": self.price_type,
            "paymentMethod": self.payment_method,
            "discount": self.discount,
            "itemsJson": self.items_json,
            "totalUSD": self.total_usd,
            "totalLBP": self.total_lbp,
            "voided": "1" if self.voided else "",
        }


class Purchase(models.Model):
    """Purchase invoice from a supplier — adds stock."""
    PAYMENT_CHOICES = [("cash", "نقداً"), ("card", "بطاقة"), ("debt", "دين")]

    no = models.IntegerField(unique=True)
    date = models.CharField(max_length=10)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL)
    supplier_name = models.CharField(max_length=200, blank=True, default="")
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="cash")
    items_json = models.TextField(default="[]")
    total_usd = models.FloatField(default=0)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["no"]

    def as_dict(self):
        return {
            "no": self.no,
            "date": self.date,
            "supplierId": str(self.supplier_id) if self.supplier_id else "",
            "supplierName": self.supplier_name or (self.supplier.name if self.supplier else ""),
            "paymentMethod": self.payment_method,
            "itemsJson": self.items_json,
            "totalUSD": self.total_usd,
            "notes": self.notes,
        }
