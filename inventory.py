from datetime import datetime

class Product:
    def __init__(self, product_id, name, quantity,
                 expiry_date, bin_location, received_date):

        self.product_id = product_id
        self.name = name
        self.quantity = quantity
        self.expiry_date = datetime.strptime(
            expiry_date, "%Y-%m-%d"
        ).date()
        self.bin_location = bin_location
        self.received_date = datetime.strptime(
            received_date, "%Y-%m-%d"
        ).date()


class Inventory:
    def __init__(self):
        self.products = []

    def add_product(self, product):
        self.products.append(product)
        print(f"{product.name} added successfully!")

    def view_inventory(self):
        print("\n========== INVENTORY ==========")

        if not self.products:
            print("Inventory is empty.")
            return

        for product in self.products:
            print(f"Product ID: {product.product_id}")
            print(f"Name: {product.name}")
            print(f"Quantity: {product.quantity}")
            print(f"Expiry Date: {product.expiry_date}")
            print(f"Bin Location: {product.bin_location}")
            print("-------------------------------")
