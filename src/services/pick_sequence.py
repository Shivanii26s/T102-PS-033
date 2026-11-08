class PickSequenceService:
    """Orders pick allocations using an aisle-by-aisle serpentine walk."""

    def __init__(self, warehouse):
        self.warehouse = warehouse

    def sequence_pick_list(self, pick_list):
        """Return copied allocations sorted by route, annotated with direction."""
        allocations = []
        aisles = []

        for index, allocation in enumerate(pick_list):
            if "bin_id" not in allocation:
                raise ValueError("Each pick allocation must include a bin_id")
            bin_obj = self.warehouse.get_bin(allocation["bin_id"])
            allocations.append((index, allocation, bin_obj))
            aisles.append(bin_obj.aisle)

        if not allocations:
            return []

        first_aisle = min(aisles)
        ordered = []
        for index, allocation, bin_obj in allocations:
            direction = (
                "UP"
                if (bin_obj.aisle - first_aisle) % 2 == 0
                else "DOWN"
            )
            bin_order = bin_obj.bin_no if direction == "UP" else -bin_obj.bin_no
            ordered.append(
                (bin_obj.aisle, bin_order, index, allocation, direction)
            )

        ordered.sort(key=lambda item: item[:3])
        return [
            {**allocation, "walk_direction": direction}
            for _, _, _, allocation, direction in ordered
        ]
