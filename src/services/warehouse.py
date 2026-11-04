
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Zone:
    zone_id: str
    zone_name: str
    temp_class: str
    aisles: str


@dataclass
class Bin:
    bin_id: str
    zone_id: str
    aisle: int
    bin_no: int
    bin_type: str
    temp_class: str
    capacity_units: int
    max_weight_kg: float


class Warehouse:
    def __init__(self):
        self.zones = {}
        self.bins = {}

    def load_zones(self, file_path):
        with open(file_path, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                zone_id = row["zone_id"]

                if zone_id in self.zones:
                    raise ValueError(f"Duplicate zone ID: {zone_id}")

                self.zones[zone_id] = Zone(
                    zone_id=zone_id,
                    zone_name=row["zone_name"],
                    temp_class=row["temp_class"],
                    aisles=row["aisles"]
                )

    def load_bins(self, file_path):
        with open(file_path, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                bin_id = row["bin_id"]
                zone_id = row["zone_id"]

                if bin_id in self.bins:
                    raise ValueError(f"Duplicate bin ID: {bin_id}")

                if zone_id not in self.zones:
                    raise ValueError(
                        f"Bin {bin_id} references unknown zone {zone_id}"
                    )

                capacity = int(row["capacity_units"])
                weight = float(row["max_weight_kg"])

                if capacity <= 0 or weight <= 0:
                    raise ValueError(f"Invalid capacity for bin {bin_id}")

                if row["temp_class"] != self.zones[zone_id].temp_class:
                    raise ValueError(
                        f"Temperature mismatch for bin {bin_id}"
                    )

                self.bins[bin_id] = Bin(
                    bin_id=bin_id,
                    zone_id=zone_id,
                    aisle=int(row["aisle"]),
                    bin_no=int(row["bin_no"]),
                    bin_type=row["bin_type"],
                    temp_class=row["temp_class"],
                    capacity_units=capacity,
                    max_weight_kg=weight
                )

    def load_warehouse(self, zones_file, bins_file):
        self.load_zones(zones_file)
        self.load_bins(bins_file)

    def get_bin(self, bin_id):
        if bin_id not in self.bins:
            raise ValueError(f"Bin not found: {bin_id}")

        return self.bins[bin_id]

    def get_zone(self, zone_id):
        if zone_id not in self.zones:
            raise ValueError(f"Zone not found: {zone_id}")

        return self.zones[zone_id]
