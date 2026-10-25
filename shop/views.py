"""
JSON API: POST /api/<name> with {"args": [...]} returns full app state.
"""
import json
from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import Customer, Move, Product, Purchase, Receipt, Setting, Supplier

DEFAULT_RATE = 89500


@login_required
def index(request):
    return render(request, "shop/index.html")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def get_all():
    return {
        "products": [p.as_dict() for p in Product.objects.all()],
        "moves": [m.as_dict() for m in Move.objects.order_by("-date", "-id")[:500]],
        "receipts": [r.as_dict() for r in Receipt.objects.order_by("-no")[:200]],
        "purchases": [p.as_dict() for p in Purchase.objects.order_by("-no")[:200]],
        "customers": [c.as_dict() for c in Customer.objects.all()],
        "suppliers": [s.as_dict() for s in Supplier.objects.all()],
        "settings": {
            "rate": Setting.get_num("rate", DEFAULT_RATE),
            "nextReceiptNo": int(Setting.get_num("nextReceiptNo", 1)),
            "nextPurchaseNo": int(Setting.get_num("nextPurchaseNo", 1)),
            "storeName": _setting_str("storeName", "خيرات البقاع الاخضر"),
            "whatsapp": _setting_str("whatsapp", ""),
        },
        "sheetUrl": "",
    }


def _setting_str(key, default=""):
    try:
        return Setting.objects.get(key=key).value
    except Setting.DoesNotExist:
        return default


def api_getAll():
    return get_all()


@transaction.atomic
def api_saveProduct(p):
    name = str(p.get("name", "")).strip()
    if not name:
        raise ValueError("اسم المنتج مطلوب")
    expiry = None
    raw_expiry = str(p.get("expiryDate", "") or "").strip()
    if raw_expiry:
        try:
            expiry = date.fromisoformat(raw_expiry)
        except ValueError:
            pass
    fields = {
        "name": name,
        "category": str(p.get("category", "")).strip() or "غير مصنف",
        "unit": str(p.get("unit", "")).strip() or "قطعة",
        "cost_usd": _num(p.get("costUSD")),
        "price_usd": _num(p.get("priceUSD")),
        "wholesale_price_usd": _num(p.get("wholesalePriceUSD")),
        "stock": _num(p.get("stock")),
        "low_stock_threshold": _num(p.get("lowStockThreshold") or 5),
        "expiry_date": expiry,
        "image": str(p.get("image", "")),
    }
    pid = str(p.get("id", "") or "")
    if pid:
        try:
            prod = Product.objects.select_for_update().get(id=int(pid))
        except (Product.DoesNotExist, ValueError):
            raise ValueError("المنتج غير موجود")
        diff = fields["stock"] - prod.stock
        for k, v in fields.items():
            setattr(prod, k, v)
        prod.save()
        if diff != 0:
            Move.objects.create(
                product=prod, product_name=prod.name,
                type="in" if diff > 0 else "out", qty=abs(diff),
                note="تعديل مخزون يدوي",
            )
    else:
        if Product.objects.filter(name=name).exists():
            raise ValueError("يوجد منتج بنفس الاسم")
        prod = Product.objects.create(**fields)
        if prod.stock > 0:
            Move.objects.create(
                product=prod, product_name=prod.name,
                type="in", qty=prod.stock, note="رصيد أولي",
            )
    return get_all()


@transaction.atomic
def api_deleteProduct(pid):
    Product.objects.filter(id=int(pid)).delete()
    return get_all()


@transaction.atomic
def api_saveProductsBulk(items):
    for p in items or []:
        try:
            prod = Product.objects.select_for_update().get(id=int(str(p.get("id"))))
        except (Product.DoesNotExist, ValueError, TypeError):
            continue
        name = str(p.get("name", "")).strip() or prod.name
        stock = _num(p.get("stock"))
        diff = stock - prod.stock
        prod.name = name
        prod.category = str(p.get("category", "")).strip() or "غير مصنف"
        prod.cost_usd = _num(p.get("costUSD"))
        prod.price_usd = _num(p.get("priceUSD"))
        prod.wholesale_price_usd = _num(p.get("wholesalePriceUSD"))
        prod.stock = stock
        prod.save()
        if diff != 0:
            Move.objects.create(
                product=prod, product_name=name,
                type="in" if diff > 0 else "out", qty=abs(diff),
                note="تعديل من الجدول",
            )
    return get_all()


@transaction.atomic
def api_importProducts(rows):
    created = updated = 0
    for r in rows or []:
        name = str(r.get("name", "")).strip()
        if not name:
            continue
        category = str(r.get("category", "")).strip() or "غير مصنف"
        cost = _num(r.get("costUSD"))
        price = _num(r.get("priceUSD"))
        wholesale = _num(r.get("wholesalePriceUSD"))
        raw_stock = r.get("stock")
        has_stock = raw_stock not in ("", None)
        prod = Product.objects.select_for_update().filter(name=name).first()
        if prod:
            old_stock = prod.stock
            prod.category = category
            prod.cost_usd = cost
            prod.price_usd = price
            prod.wholesale_price_usd = wholesale
            if has_stock:
                prod.stock = _num(raw_stock)
            prod.save()
            diff = prod.stock - old_stock
            if diff != 0:
                Move.objects.create(
                    product=prod, product_name=name,
                    type="in" if diff > 0 else "out", qty=abs(diff),
                    note="استيراد من ملف",
                )
            updated += 1
        else:
            prod = Product.objects.create(
                name=name, category=category, cost_usd=cost, price_usd=price,
                wholesale_price_usd=wholesale,
                stock=_num(raw_stock) if has_stock else 0,
            )
            if prod.stock > 0:
                Move.objects.create(
                    product=prod, product_name=name,
                    type="in", qty=prod.stock, note="استيراد من ملف",
                )
            created += 1
    out = get_all()
    out["created"] = created
    out["updated"] = updated
    return out


@transaction.atomic
def api_stockMove(product_id, mtype, qty, note=""):
    qty = _num(qty)
    if qty <= 0:
        raise ValueError("الكمية يجب أن تكون أكبر من صفر")
    if mtype not in ("in", "out"):
        raise ValueError("نوع الحركة غير صحيح")
    try:
        prod = Product.objects.select_for_update().get(id=int(product_id))
    except (Product.DoesNotExist, ValueError):
        raise ValueError("المنتج غير موجود")
    prod.stock = prod.stock + qty if mtype == "in" else prod.stock - qty
    prod.save()
    Move.objects.create(
        product=prod, product_name=prod.name, type=mtype, qty=qty,
        note=str(note or ""),
    )
    return get_all()


@transaction.atomic
def api_saveReceipt(r):
    items = (r or {}).get("items") or []
    if not items:
        raise ValueError("الفاتورة فارغة")
    rate = Setting.get_num("rate", DEFAULT_RATE)
    no = int(Setting.get_num("nextReceiptNo", 1))
    price_type = str(r.get("priceType", "retail"))
    payment_method = str(r.get("paymentMethod", "cash"))
    discount = _num(r.get("discount", 0))
    customer_id = str(r.get("customerId", "") or "")
    customer_name = str(r.get("customerName", "") or "")
    customer_obj = None

    if customer_id.isdigit():
        customer_obj = Customer.objects.select_for_update().filter(id=int(customer_id)).first()

    clean = []
    total_usd = 0.0
    for it in items:
        qty = _num(it.get("qty"))
        price = _num(it.get("priceUSD"))
        pid = str(it.get("productId", ""))
        clean.append({"productId": pid, "name": it.get("name", ""), "qty": qty, "priceUSD": price})
        total_usd += qty * price
        prod = Product.objects.select_for_update().filter(id=int(pid)).first() if pid.isdigit() else None
        if prod:
            prod.stock -= qty
            prod.save()
        Move.objects.create(
            product=prod, product_name=it.get("name", ""),
            type="out", qty=qty, note="بيع", receipt_no=str(no),
        )

    total_usd = max(0, total_usd - discount)
    Receipt.objects.create(
        no=no,
        date=str(r.get("date", ""))[:10],
        customer=customer_obj,
        customer_name=customer_name or (customer_obj.name if customer_obj else ""),
        rate=rate,
        currency=r.get("currency") or "both",
        price_type=price_type,
        payment_method=payment_method,
        discount=discount,
        items_json=json.dumps(clean, ensure_ascii=False),
        total_usd=total_usd,
        total_lbp=_num(r.get("totalLBP")) or round(total_usd * rate),
    )

    if payment_method == "debt" and customer_obj:
        customer_obj.debt += total_usd
        customer_obj.save()

    Setting.set("nextReceiptNo", no + 1)
    out = get_all()
    out["no"] = no
    return out


@transaction.atomic
def api_voidReceipt(no):
    try:
        rec = Receipt.objects.select_for_update().get(no=int(no))
    except Receipt.DoesNotExist:
        raise ValueError("الفاتورة غير موجودة")
    if rec.voided:
        raise ValueError("الفاتورة ملغاة أصلاً")
    rec.voided = True
    rec.save()
    for it in json.loads(rec.items_json or "[]"):
        qty = _num(it.get("qty"))
        pid = str(it.get("productId", ""))
        prod = Product.objects.select_for_update().filter(id=int(pid)).first() if pid.isdigit() else None
        if prod:
            prod.stock += qty
            prod.save()
        Move.objects.create(
            product=prod, product_name=it.get("name", ""),
            type="in", qty=qty, note=f"إلغاء فاتورة رقم {no}", receipt_no=str(no),
        )
    if rec.payment_method == "debt" and rec.customer_id:
        try:
            cust = Customer.objects.select_for_update().get(id=rec.customer_id)
            cust.debt = max(0, cust.debt - rec.total_usd)
            cust.save()
        except Customer.DoesNotExist:
            pass
    return get_all()


def api_saveSettings(s):
    rate = _num((s or {}).get("rate"))
    if rate <= 0:
        raise ValueError("سعر الصرف غير صحيح")
    Setting.set("rate", rate)
    store_name = str((s or {}).get("storeName", "") or "").strip()
    if store_name:
        Setting.set("storeName", store_name)
    whatsapp = str((s or {}).get("whatsapp", "") or "").strip()
    Setting.set("whatsapp", whatsapp)
    return get_all()


# ── Customer APIs ──────────────────────────────────────────────────────────────

@transaction.atomic
def api_saveCustomer(c):
    name = str(c.get("name", "")).strip()
    if not name:
        raise ValueError("اسم الزبون مطلوب")
    fields = {
        "name": name,
        "phone": str(c.get("phone", "") or "").strip(),
        "phone2": str(c.get("phone2", "") or "").strip(),
        "customer_type": str(c.get("customerType", "individual")),
        "address": str(c.get("address", "") or "").strip(),
        "notes": str(c.get("notes", "") or "").strip(),
    }
    cid = str(c.get("id", "") or "")
    if cid:
        try:
            cust = Customer.objects.select_for_update().get(id=int(cid))
        except (Customer.DoesNotExist, ValueError):
            raise ValueError("الزبون غير موجود")
        for k, v in fields.items():
            setattr(cust, k, v)
        cust.save()
    else:
        Customer.objects.create(**fields)
    return get_all()


@transaction.atomic
def api_deleteCustomer(cid):
    Customer.objects.filter(id=int(cid)).delete()
    return get_all()


@transaction.atomic
def api_adjustCustomerDebt(cid, amount, note=""):
    try:
        cust = Customer.objects.select_for_update().get(id=int(cid))
    except (Customer.DoesNotExist, ValueError):
        raise ValueError("الزبون غير موجود")
    cust.debt = max(0, cust.debt - _num(amount))
    cust.save()
    return get_all()


def api_getCustomerHistory(cid):
    receipts = Receipt.objects.filter(customer_id=int(cid), voided=False).order_by("-no")[:50]
    items_by_product = {}
    for rec in receipts:
        for it in json.loads(rec.items_json or "[]"):
            pid = it.get("productId", "")
            nm = it.get("name", "")
            key = pid or nm
            if key not in items_by_product:
                items_by_product[key] = {"productId": pid, "name": nm, "totalQty": 0, "count": 0}
            items_by_product[key]["totalQty"] += _num(it.get("qty"))
            items_by_product[key]["count"] += 1
    history = sorted(items_by_product.values(), key=lambda x: x["count"], reverse=True)
    return {
        "receipts": [r.as_dict() for r in receipts],
        "topItems": history[:10],
    }


# ── Supplier APIs ──────────────────────────────────────────────────────────────

@transaction.atomic
def api_saveSupplier(s):
    name = str(s.get("name", "")).strip()
    if not name:
        raise ValueError("اسم المورد مطلوب")
    fields = {
        "name": name,
        "company": str(s.get("company", "") or "").strip(),
        "phone": str(s.get("phone", "") or "").strip(),
        "notes": str(s.get("notes", "") or "").strip(),
    }
    sid = str(s.get("id", "") or "")
    if sid:
        try:
            supp = Supplier.objects.select_for_update().get(id=int(sid))
        except (Supplier.DoesNotExist, ValueError):
            raise ValueError("المورد غير موجود")
        for k, v in fields.items():
            setattr(supp, k, v)
        supp.save()
    else:
        Supplier.objects.create(**fields)
    return get_all()


@transaction.atomic
def api_deleteSupplier(sid):
    Supplier.objects.filter(id=int(sid)).delete()
    return get_all()


# ── Purchase APIs ──────────────────────────────────────────────────────────────

@transaction.atomic
def api_savePurchase(p):
    items = (p or {}).get("items") or []
    if not items:
        raise ValueError("فاتورة الشراء فارغة")
    no = int(Setting.get_num("nextPurchaseNo", 1))
    supplier_id = str(p.get("supplierId", "") or "")
    supplier_name = str(p.get("supplierName", "") or "")
    payment_method = str(p.get("paymentMethod", "cash"))
    supplier_obj = None
    if supplier_id.isdigit():
        supplier_obj = Supplier.objects.select_for_update().filter(id=int(supplier_id)).first()

    clean = []
    total_usd = 0.0
    for it in items:
        qty = _num(it.get("qty"))
        cost = _num(it.get("costUSD"))
        pid = str(it.get("productId", ""))
        clean.append({"productId": pid, "name": it.get("name", ""), "qty": qty, "costUSD": cost})
        total_usd += qty * cost
        prod = Product.objects.select_for_update().filter(id=int(pid)).first() if pid.isdigit() else None
        if prod:
            prod.stock += qty
            if cost > 0:
                prod.cost_usd = cost
            prod.save()
        Move.objects.create(
            product=prod, product_name=it.get("name", ""),
            type="in", qty=qty, note="شراء", receipt_no=str(no),
        )

    Purchase.objects.create(
        no=no,
        date=str(p.get("date", ""))[:10],
        supplier=supplier_obj,
        supplier_name=supplier_name or (supplier_obj.name if supplier_obj else ""),
        payment_method=payment_method,
        items_json=json.dumps(clean, ensure_ascii=False),
        total_usd=total_usd,
        notes=str(p.get("notes", "") or ""),
    )

    if payment_method == "debt" and supplier_obj:
        supplier_obj.debt += total_usd
        supplier_obj.save()

    Setting.set("nextPurchaseNo", no + 1)
    out = get_all()
    out["no"] = no
    return out


# ── Dashboard / Reports ────────────────────────────────────────────────────────

def api_getDashboard():
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    month_str = today.strftime("%Y-%m")

    today_receipts = Receipt.objects.filter(date=today_str, voided=False)
    month_receipts = Receipt.objects.filter(date__startswith=month_str, voided=False)

    def receipts_stats(qs):
        total = 0.0
        profit = 0.0
        count = qs.count()
        for rec in qs:
            items = json.loads(rec.items_json or "[]")
            for it in items:
                qty = _num(it.get("qty"))
                price = _num(it.get("priceUSD"))
                pid = str(it.get("productId", ""))
                total += qty * price
                if pid.isdigit():
                    prod = Product.objects.filter(id=int(pid)).first()
                    if prod:
                        profit += qty * (price - prod.cost_usd)
            total -= rec.discount
        return {"total": round(total, 2), "profit": round(profit, 2), "count": count}

    today_stats = receipts_stats(today_receipts)
    month_stats = receipts_stats(month_receipts)

    low_stock = [p.as_dict() for p in Product.objects.all() if p.stock <= p.low_stock_threshold]

    # daily sales for last 30 days
    days = []
    for i in range(29, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        recs = Receipt.objects.filter(date=d, voided=False)
        t = sum(_num(r.total_usd) for r in recs)
        days.append({"date": d, "total": round(t, 2), "count": recs.count()})

    total_inventory_cost = sum(p.stock * p.cost_usd for p in Product.objects.all())
    total_customers_debt = Customer.objects.aggregate(s=Sum("debt"))["s"] or 0
    total_suppliers_debt = Supplier.objects.aggregate(s=Sum("debt"))["s"] or 0

    return {
        "today": today_stats,
        "month": month_stats,
        "lowStock": low_stock,
        "dailySales": days,
        "totalInventoryCost": round(total_inventory_cost, 2),
        "totalCustomersDebt": round(total_customers_debt, 2),
        "totalSuppliersDebt": round(total_suppliers_debt, 2),
    }


def api_getReport(period, year, month):
    month = str(month).zfill(2)
    if period == "month":
        prefix = f"{year}-{month}"
        qs = Receipt.objects.filter(date__startswith=prefix, voided=False)
    else:
        qs = Receipt.objects.filter(date__startswith=str(year), voided=False)

    rows = []
    for rec in qs.order_by("date", "no"):
        items = json.loads(rec.items_json or "[]")
        total = _num(rec.total_usd)
        cost = 0.0
        for it in items:
            qty = _num(it.get("qty"))
            pid = str(it.get("productId", ""))
            if pid.isdigit():
                prod = Product.objects.filter(id=int(pid)).first()
                if prod:
                    cost += qty * prod.cost_usd
        rows.append({
            "no": rec.no,
            "date": rec.date,
            "customerName": rec.customer_name or (rec.customer.name if rec.customer else ""),
            "totalUSD": round(total, 2),
            "cost": round(cost, 2),
            "profit": round(total - cost, 2),
            "paymentMethod": rec.payment_method,
        })

    grand_total = sum(r["totalUSD"] for r in rows)
    grand_cost = sum(r["cost"] for r in rows)
    return {
        "rows": rows,
        "grandTotal": round(grand_total, 2),
        "grandCost": round(grand_cost, 2),
        "grandProfit": round(grand_total - grand_cost, 2),
        "count": len(rows),
    }


# ── Dispatch ───────────────────────────────────────────────────────────────────

API_FUNCS = {
    "api_getAll": api_getAll,
    "api_saveProduct": api_saveProduct,
    "api_deleteProduct": api_deleteProduct,
    "api_saveProductsBulk": api_saveProductsBulk,
    "api_importProducts": api_importProducts,
    "api_stockMove": api_stockMove,
    "api_saveReceipt": api_saveReceipt,
    "api_voidReceipt": api_voidReceipt,
    "api_saveSettings": api_saveSettings,
    "api_saveCustomer": api_saveCustomer,
    "api_deleteCustomer": api_deleteCustomer,
    "api_adjustCustomerDebt": api_adjustCustomerDebt,
    "api_getCustomerHistory": api_getCustomerHistory,
    "api_saveSupplier": api_saveSupplier,
    "api_deleteSupplier": api_deleteSupplier,
    "api_savePurchase": api_savePurchase,
    "api_getDashboard": api_getDashboard,
    "api_getReport": api_getReport,
}


@login_required
@require_POST
def api(request, name):
    func = API_FUNCS.get(name)
    if not func:
        return JsonResponse({"error": "دالة غير معروفة"}, status=404)
    try:
        args = json.loads(request.body or b"{}").get("args", [])
        return JsonResponse(func(*args))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:  # noqa: BLE001
        return JsonResponse({"error": f"خطأ في الخادم: {e}"}, status=500)
