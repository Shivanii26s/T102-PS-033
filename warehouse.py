
class WarehouseBin:

    def __init__(self, bin_id, capacity):
        self.bin_id = bin_id
        self.capacity = capacity
        self.products = {}

    def add_stock(self, product_name, quantity):
        current_stock = sum(self.products.values())

        if current_stock + quantity > self.capacity:
            print(f"Bin {self.bin_id} is full!")
            print("Cannot add stock. Capacity exceeded.")
            return False

        self.products[product_name] = (
            self.products.get(product_name, 0) + quantity
        )

        print(
            f"{quantity} units of {product_name} "
            f"added to Bin {self.bin_id}"
        )
        return True

    def display_bin(self):
        current_stock = sum(self.products.values())

        print(f"\n========== BIN {self.bin_id} ==========")
        print(f"Capacity: {self.capacity}")
        print(f"Used Space: {current_stock}")
        print(f"Available Space: {self.capacity - current_stock}")

        print("Products:")

        if not self.products:
            print("No products stored.")
        else:
            for name, quantity in self.products.items():
                print(f"{name}: {quantity} units")
