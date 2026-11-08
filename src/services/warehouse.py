import csv
from dataclasses import dataclass


@dataclass(frozen=True)
class Zone:
    zone_id: str
    zone_name: str
    temp_class: str
    aisles: str


@dataclass(frozen=True)
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
    """Loads and validates warehouse master data from zones.csv and bins.csv."""
    def __init__(self):
        self.zones: dict[str, Zone] = {}
        self.bins: dict[str, Bin] = {}

    def load_zones(self, file_path):
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                zone_id = row["zone_id"].strip()
                if not zone_id or zone_id in self.zones:
                    raise ValueError(f"Missing or duplicate zone ID: {zone_id}")
                self.zones[zone_id] = Zone(zone_id, row["zone_name"].strip(),
                                           row["temp_class"].strip().upper(), row["aisles"].strip())

    def load_bins(self, file_path):
        allowed = {"PICK_FACE", "RESERVE", "QUARANTINE"}
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                bin_id, zone_id = row["bin_id"].strip(), row["zone_id"].strip()
                if not bin_id or bin_id in self.bins:
                    raise ValueError(f"Missing or duplicate bin ID: {bin_id}")
                if zone_id not in self.zones:
                    raise ValueError(f"Bin {bin_id} references unknown zone {zone_id}")
                bin_type = row["bin_type"].strip().upper()
                temp_class = row["temp_class"].strip().upper()
                capacity, weight = int(row["capacity_units"]), float(row["max_weight_kg"])
                if bin_type not in allowed:
                    raise ValueError(f"Invalid bin type {bin_type} for {bin_id}")
                if capacity <= 0 or weight <= 0:
                    raise ValueError(f"Invalid capacity for bin {bin_id}")
                if temp_class != self.zones[zone_id].temp_class:
                    raise ValueError(f"Temperature mismatch for bin {bin_id}")
                self.bins[bin_id] = Bin(bin_id, zone_id, int(row["aisle"]), int(row["bin_no"]),
                                        bin_type, temp_class, capacity, weight)

    def load_warehouse(self, zones_file, bins_file):
        self.load_zones(zones_file)
        self.load_bins(bins_file)
        return self

    def get_bin(self, bin_id):
        try:
            return self.bins[bin_id]
        except KeyError:
            raise ValueError(f"Bin not found: {bin_id}") from None

    def get_zone(self, zone_id):
        try:
            return self.zones[zone_id]
        except KeyError:
            raise ValueError(f"Zone not found: {zone_id}") from None

    def compatible_bins(self, temp_class, bin_types=None):
        types = set(bin_types or {"PICK_FACE", "RESERVE"})
        return [b for b in self.bins.values() if b.temp_class == temp_class.upper() and b.bin_type in types]
