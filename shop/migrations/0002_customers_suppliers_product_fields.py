import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0001_initial"),
    ]

    operations = [
        # Add new fields to Product
        migrations.AddField(
            model_name="product",
            name="unit",
            field=models.CharField(blank=True, default="قطعة", max_length=50),
        ),
        migrations.AddField(
            model_name="product",
            name="wholesale_price_usd",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="product",
            name="low_stock_threshold",
            field=models.FloatField(default=5),
        ),
        migrations.AddField(
            model_name="product",
            name="expiry_date",
            field=models.DateField(blank=True, null=True),
        ),
        # Create Customer model
        migrations.CreateModel(
            name="Customer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("phone", models.CharField(blank=True, default="", max_length=30)),
                ("phone2", models.CharField(blank=True, default="", max_length=30)),
                ("customer_type", models.CharField(
                    choices=[("individual", "فرد"), ("restaurant", "مطعم"), ("trader", "تاجر جملة")],
                    default="individual", max_length=20,
                )),
                ("address", models.CharField(blank=True, default="", max_length=300)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("debt", models.FloatField(default=0)),
            ],
            options={"ordering": ["name"]},
        ),
        # Create Supplier model
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("company", models.CharField(blank=True, default="", max_length=200)),
                ("phone", models.CharField(blank=True, default="", max_length=30)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("debt", models.FloatField(default=0)),
            ],
            options={"ordering": ["name"]},
        ),
        # Modify Receipt: rename customer (CharField→FK), add new fields
        migrations.RenameField(
            model_name="receipt",
            old_name="customer",
            new_name="customer_name",
        ),
        migrations.AddField(
            model_name="receipt",
            name="customer",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="shop.customer",
            ),
        ),
        migrations.AddField(
            model_name="receipt",
            name="price_type",
            field=models.CharField(
                choices=[("retail", "مفرق"), ("wholesale", "جملة")],
                default="retail", max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="receipt",
            name="payment_method",
            field=models.CharField(
                choices=[("cash", "نقداً"), ("card", "بطاقة"), ("debt", "دين")],
                default="cash", max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="receipt",
            name="discount",
            field=models.FloatField(default=0),
        ),
        # Create Purchase model
        migrations.CreateModel(
            name="Purchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("no", models.IntegerField(unique=True)),
                ("date", models.CharField(max_length=10)),
                ("supplier_name", models.CharField(blank=True, default="", max_length=200)),
                ("payment_method", models.CharField(
                    choices=[("cash", "نقداً"), ("card", "بطاقة"), ("debt", "دين")],
                    default="cash", max_length=10,
                )),
                ("items_json", models.TextField(default="[]")),
                ("total_usd", models.FloatField(default=0)),
                ("notes", models.TextField(blank=True, default="")),
                ("supplier", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="shop.supplier",
                )),
            ],
            options={"ordering": ["no"]},
        ),
    ]
