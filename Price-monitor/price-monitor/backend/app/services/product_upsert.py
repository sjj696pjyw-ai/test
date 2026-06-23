"""Общая логика сохранения цен конкурента.

Используется и при первичном сборе (analysis_service.parse_competitor_site),
и при обновлении цен (price_update_service.update_competitor_prices), чтобы
не дублировать дедуп по имени, создание Product и запись PriceHistory.
"""
from ..models import PriceHistory, Product, db


def upsert_competitor_products(competitor_id, products_data, on_existing=None):
    """Дедуп товаров по имени, создание новых и обновление существующих.

    Для существующего товара: при изменении цены записываем PriceHistory со
    старой ценой и обновляем цену. Для нового — создаём Product.
    Коммит НЕ выполняется — это ответственность вызывающего кода.

    Параметры:
        competitor_id — id конкурента;
        products_data — список словарей {'name', 'price', 'currency'?};
        on_existing(product) — необязательный колбэк для каждого существующего
            товара (вызывается до записи истории цены), напр. чтобы зафиксировать
            цены связанных пользовательских товаров.

    Возвращает dict:
        products — список объектов Product (в порядке products_data),
        updated_count, created_count, not_found_count,
        price_changes — список изменений цены.
    """
    existing_products = {
        p.name.strip().lower(): p
        for p in Product.query.filter_by(competitor_id=competitor_id).all()
    }

    updated_count = 0
    created_count = 0
    price_changes = []
    products = []

    for prod_data in products_data:
        name = prod_data["name"].strip()
        key = name.lower()
        new_price = prod_data["price"]

        if key in existing_products:
            product = existing_products[key]
            old_price = product.price

            if on_existing is not None:
                on_existing(product)

            if old_price != new_price:
                db.session.add(
                    PriceHistory(
                        product_id=product.id,
                        price=old_price,
                        currency=product.currency,
                    )
                )
                product.price = new_price
                price_changes.append(
                    {
                        "product_id": product.id,
                        "product_name": product.name,
                        "old_price": old_price,
                        "new_price": new_price,
                    }
                )

            updated_count += 1
        else:
            product = Product(
                competitor_id=competitor_id,
                name=name,
                price=new_price,
                currency=prod_data.get("currency", "RUB"),
            )
            db.session.add(product)
            created_count += 1

        products.append(product)

    found_names = {p["name"].strip().lower() for p in products_data}
    not_found_count = sum(1 for n in existing_products if n not in found_names)

    return {
        "products": products,
        "updated_count": updated_count,
        "created_count": created_count,
        "not_found_count": not_found_count,
        "price_changes": price_changes,
    }
