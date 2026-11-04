
from datetime import datetime


class Picking:

    # FIFO: First In, First Out
    @staticmethod
    def fifo(products):
        print("\n========== FIFO PICKING ==========")

        sorted_products = sorted(
            products,
            key=lambda p: p.received_date
        )

        for product in sorted_products:
            print(
                f"{product.name} - "
                f"Quantity: {product.quantity} - "
                f"Received: {product.received_date}"
            )

    # FEFO: First Expired, First Out
    @staticmethod
    def fefo(products):
        print("\n========== FEFO PICKING ==========")

        sorted_products = sorted(
            products,
            key=lambda p: p.expiry_date
        )

        for product in sorted_products:
            print(
                f"{product.name} - "
                f"Quantity: {product.quantity} - "
                f"Expiry: {product.expiry_date}"
            )
