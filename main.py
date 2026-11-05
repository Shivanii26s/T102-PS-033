from movement import StockMovement
from reservation import StockReservation
from warehouse import WarehouseBin
from inventory import Product, Inventory
from picking import Picking


def main():
    warehouse = Inventory()

    product1 = Product(
        101, "Rice", 100,
        "2027-12-31", "A1", "2026-10-01"
    )

    product2 = Product(
        102, "Wheat", 50,
        "2027-10-15", "A2", "2026-09-15"
    )

    product3 = Product(
        103, "Sugar", 75,
        "2027-08-20", "A3", "2026-10-10"
    )

    warehouse.add_product(product1)
    warehouse.add_product(product2)
    warehouse.add_product(product3)

    warehouse.view_inventory()

    Picking.fifo(warehouse.products)
    Picking.fefo(warehouse.products)
        # Warehouse Bin Capacity Testing
    bin1 = WarehouseBin("A1", 200)

    bin1.add_stock("Rice", 100)
    bin1.add_stock("Wheat", 50)
    bin1.add_stock("Sugar", 75)

    bin1.display_bin()
        # Stock Reservation Testing
    reservation = StockReservation()

    reservation.reserve_stock(product1, 30)
    reservation.reserve_stock(product2, 20)

    reservation.view_reservations()

    print(
        "Available Rice Stock:",
        reservation.available_stock(product1)
    )
        # Stock Movement Testing
    movement = StockMovement()

    movement.move_stock(
        product1,
        10,
        "A1",
        "B1"
    )

    movement.view_movements()

    print("Rice Stock After Movement:", product1.quantity)


if __name__ == "__main__":
    main()
