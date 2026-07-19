CART_SESSION_KEY = 'cart'


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if cart is None:
            cart = self.session[CART_SESSION_KEY] = {}
        self.cart = cart

    def add(self, source, source_id, name, unit_price, quantity=1):
        key = f"{source}:{source_id}"
        if key in self.cart:
            self.cart[key]['quantity'] += quantity
        else:
            self.cart[key] = {
                'source': source,
                'source_id': source_id,
                'name': name,
                'unit_price': str(unit_price),  # Decimal isn't JSON serializable
                'quantity': quantity,
            }
        self.save()

    def remove(self, key):
        if key in self.cart:
            del self.cart[key]
            self.save()

    def clear(self):
        self.session[CART_SESSION_KEY] = {}
        self.save()

    def save(self):
        self.session.modified = True

    def __iter__(self):
        for key, item in self.cart.items():
            yield key, item

    def total(self):
        from decimal import Decimal
        return sum(Decimal(item['unit_price']) * item['quantity'] for item in self.cart.values())

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())