from src.services.grn import GRNService


def write_csv(path, content):
    path.write_text(content, encoding="utf-8")
    return path


def test_load_grn_data_keeps_valid_rows_and_rejects_unknown_sku(tmp_path):
    sku_file = write_csv(tmp_path / "skus.csv",
        "sku_id,description,unit_weight_kg,temp_class,expiry_tracked,home_zone,pick_face_bin\n"
        "SKU-001,Rice,1.0,AMBIENT,false,ZN-A,BIN-1\n")
    grn_file = write_csv(tmp_path / "grn.csv",
        "grn_id,line_no,grn_ts,supplier_id,sku_id,lot_no,qty,mfg_date,expiry_date\n"
        "G1,1,2028-01-19 10:00:00,S1,SKU-001,L1,10,2027-01-01,\n"
        "G1,2,2028-01-19 10:00:00,S1,SKU-099,L2,5,2027-01-01,\n")
    service = GRNService()
    service.load_skus(sku_file)
    service.load_grn_lines(grn_file)
    assert len(service.grn_lines) == 1
    assert len(service.rejected_rows) == 1
    assert "Unknown SKU: SKU-099" in service.rejected_rows[0]["reason"]


def test_get_grn_lines_sorted():
    from datetime import datetime
    from src.services.grn import GRNLine
    service = GRNService()
    service.grn_lines[("G1", 2)] = GRNLine("G1", 2, datetime(2028, 1, 1), "S", "SKU-1", "L2", 1, None, None)
    service.grn_lines[("G1", 1)] = GRNLine("G1", 1, datetime(2028, 1, 1), "S", "SKU-1", "L1", 1, None, None)
    assert [x.line_no for x in service.get_grn_lines("G1")] == [1, 2]
