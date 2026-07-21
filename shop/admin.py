from django.contrib import admin

from .models import Move, Product, Receipt, Setting


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "cost_usd", "price_usd", "stock"]
    list_filter = ["category"]
    search_fields = ["name"]


@admin.register(Move)
class MoveAdmin(admin.ModelAdmin):
    list_display = ["date", "product_name", "type", "qty", "note", "receipt_no"]
    list_filter = ["type"]


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ["no", "date", "customer", "total_usd", "total_lbp", "voided"]


admin.site.register(Setting)
