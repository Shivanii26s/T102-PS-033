
from datetime import datetime


class StockMovement:

    def __init__(self):
        self.movements = []

    def move_stock(self, product, quantity, source_bin, destination_bin):

        if quantity <= 0:
            print("Invalid quantity!")
            return

        if quantity > product.quantity:
            print("Insufficient stock!")
            return

        movement = {
            "Product ID": product.product_id,
            "Product Name": product.name,
            "Quantity": quantity,
            "Source Bin": source_bin,
            "Destination Bin": destination_bin,
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        self.movements.append(movement)

        product.quantity -= quantity

        print(
            f"{quantity} units of {product.name} moved "
            f"from {source_bin} to {destination_bin} successfully!"
        )

    def view_movements(self):

        print("\n========== STOCK MOVEMENT HISTORY ==========")

        if not self.movements:
            print("No stock movements recorded.")
            return

        for movement in self.movements:
            for key, value in movement.items():
                print(f"{key}: {value}")

            print("------------------------------------")
