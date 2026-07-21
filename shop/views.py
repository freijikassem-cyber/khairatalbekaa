"""
JSON API mirroring the Apps Script backend: the frontend calls
POST /api/<name> with {"args": [...]} and gets back the full app state.
"""
import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import Move, Product, Receipt, Setting

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
        "moves": [m.as_dict() for m in Move.objects.all()],
        "receipts": [r.as_dict() for r in Receipt.objects.all()],
        "settings": {
            "rate": Setting.get_num("rate", DEFAULT_RATE),
            "nextReceiptNo": int(Setting.get_num("nextReceiptNo", 1)),
        },
        "sheetUrl": "",
    }


def api_getAll():
    return get_all()


@transaction.atomic
def api_saveProduct(p):
    name = str(p.get("name", "")).strip()
    if not name:
        raise ValueError("اسم المنتج مطلوب")
    fields = {
        "name": name,
        "category": str(p.get("category", "")).strip() or "غير مصنف",
        "cost_usd": _num(p.get("costUSD")),
        "price_usd": _num(p.get("priceUSD")),
        "stock": _num(p.get("stock")),
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
        raw_stock = r.get("stock")
        has_stock = raw_stock not in ("", None)
        prod = Product.objects.select_for_update().filter(name=name).first()
        if prod:
            old_stock = prod.stock
            prod.category = category
            prod.cost_usd = cost
            prod.price_usd = price
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
    Receipt.objects.create(
        no=no,
        date=str(r.get("date", ""))[:10],
        customer=str(r.get("customer", "")),
        rate=rate,
        currency=r.get("currency") or "both",
        items_json=json.dumps(clean, ensure_ascii=False),
        total_usd=total_usd,
        total_lbp=_num(r.get("totalLBP")) or round(total_usd * rate),
    )
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
    return get_all()


def api_saveSettings(s):
    rate = _num((s or {}).get("rate"))
    if rate <= 0:
        raise ValueError("سعر الصرف غير صحيح")
    Setting.set("rate", rate)
    return get_all()


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
    except Exception as e:  # noqa: BLE001 — surface unexpected errors to the UI
        return JsonResponse({"error": f"خطأ في الخادم: {e}"}, status=500)
