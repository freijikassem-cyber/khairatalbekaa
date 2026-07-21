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


class Product(models.Model):
    name = models.CharField(max_length=200, unique=True)
    category = models.CharField(max_length=100, default="غير مصنف", blank=True)
    cost_usd = models.FloatField(default=0)
    price_usd = models.FloatField(default=0)
    stock = models.FloatField(default=0)
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
            "costUSD": self.cost_usd,
            "priceUSD": self.price_usd,
            "stock": self.stock,
            "image": self.image,
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
    no = models.IntegerField(unique=True)
    date = models.CharField(max_length=10)  # yyyy-mm-dd, chosen by the cashier
    customer = models.CharField(max_length=200, blank=True, default="")
    rate = models.FloatField()
    currency = models.CharField(max_length=10, default="both")
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
            "customer": self.customer,
            "rate": self.rate,
            "currency": self.currency,
            "itemsJson": self.items_json,
            "totalUSD": self.total_usd,
            "totalLBP": self.total_lbp,
            "voided": "1" if self.voided else "",
        }
