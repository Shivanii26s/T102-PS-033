
class StockReservation:

    def __init__(self):
        self.reservations = []

    def reserve_stock(self, product, quantity):

        reserved_quantity = sum(
            item["quantity"]
            for item in self.reservations
            if item["product_id"] == product.product_id
        )

        available_stock = product.quantity - reserved_quantity

        if quantity <= 0:
            print("Reservation quantity must be positive.")
            return False

        if quantity > available_stock:
            print("Insufficient stock available!")
            print(f"Available stock: {available_stock}")
            return False

        reservation = {
            "product_id": product.product_id,
            "product_name": product.name,
            "quantity": quantity
        }

        self.reservations.append(reservation)

        print(
            f"{quantity} units of {product.name} "
            "reserved successfully!"
        )

        return True

    def view_reservations(self):

        print("\n========== STOCK RESERVATIONS ==========")

        if not self.reservations:
            print("No reservations found.")
            return

        for item in self.reservations:
            print(
                f"Product: {item['product_name']} | "
                f"Reserved: {item['quantity']} units"
            )

    def available_stock(self, product):

        reserved = sum(
            item["quantity"]
            for item in self.reservations
            if item["product_id"] == product.product_id
        )

        return product.quantity - reserved
