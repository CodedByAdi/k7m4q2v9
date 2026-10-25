"""Live verification of the unified Windline server (API + Frontend SPA)."""

import csv
import io
import json
import urllib.request
import sys

BASE_URL = "http://127.0.0.1:8000"

# Direct loopback connection without environment proxy interference
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))

def test_health():
    print("=== CHECK 1: /api/health ===")
    with urllib.request.urlopen(f"{BASE_URL}/api/health") as resp:
        assert resp.getcode() == 200
        data = json.loads(resp.read().decode())
        print(f"Status: {resp.getcode()}")
        print(f"Payload: {data}")
        assert data["status"] == "healthy"
        assert data["app_name"] == "Windline"
        print("PASS: /api/health OK\n")

def test_overview():
    print("=== CHECK 2: /api/overview ===")
    with urllib.request.urlopen(f"{BASE_URL}/api/overview?cutoff=09:00") as resp:
        assert resp.getcode() == 200
        data = json.loads(resp.read().decode())
        overall = data["overall_metrics"]
        print(f"Status: {resp.getcode()}")
        print(f"Total delivery days: {data['total_delivery_days']}")
        print(f"Auditable days: {data['auditable_days']}")
        print(f"Expected intervals: {overall['expected_intervals']}")
        print(f"Matched intervals: {overall['matched_intervals']}")
        print(f"Omitted intervals: {overall['omitted_intervals']}")
        print(f"Coverage: {overall['coverage'] * 100:.1f}%")
        print(f"MAE: {overall['mae']:.2f} MW")
        print(f"RMSE: {overall['rmse']:.2f} MW")
        print(f"Bias: {overall['bias']:.2f} MW")
        print(f"WAPE: {overall['wape']:.2f}%")
        assert data["total_delivery_days"] == 31
        assert overall["expected_intervals"] == 744
        assert overall["matched_intervals"] == 744
        assert overall["coverage"] == 1.0
        # WAPE must be returned in percentage points (18.07%), not a decimal ratio (0.1807) or multiplied twice (1807%)
        assert overall["wape"] == 18.07
        print("PASS: /api/overview reproduces all 31 days and 744 intervals\n")

def test_frontend_root():
    print("=== CHECK 3: GET / (React SPA) ===")
    with urllib.request.urlopen(f"{BASE_URL}/") as resp:
        assert resp.getcode() == 200
        ctype = resp.headers.get("Content-Type")
        body = resp.read().decode("utf-8")
        print(f"Status: {resp.getcode()}")
        print(f"Content-Type: {ctype}")
        print(f"HTML Title: {'Windline' in body}")
        root_div_present = '<div id="root"></div>' in body
        print(f"Root Div: {root_div_present}")
        assert "text/html" in ctype
        assert '<div id="root"></div>' in body
        print("PASS: Root endpoint serves React SPA index.html\n")

def test_frontend_assets():
    print("=== CHECK 4: Direct Frontend Static Asset URLs ===")
    from pathlib import Path
    dist_assets = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "assets"
    css_files = list(dist_assets.glob("*.css"))
    js_files = list(dist_assets.glob("*.js"))
    assert len(css_files) > 0, "No built CSS asset found in frontend/dist/assets"
    assert len(js_files) > 0, "No built JS asset found in frontend/dist/assets"

    css_name = css_files[0].name
    js_name = js_files[0].name

    # CSS asset
    css_url = f"{BASE_URL}/assets/{css_name}"
    with urllib.request.urlopen(css_url) as resp:
        assert resp.getcode() == 200
        ctype = resp.headers.get("Content-Type")
        size = len(resp.read())
        print(f"CSS ({css_name}) Status: {resp.getcode()}, Type: {ctype}, Size: {size} bytes")
        assert "text/css" in ctype

    # JS asset
    js_url = f"{BASE_URL}/assets/{js_name}"
    with urllib.request.urlopen(js_url) as resp:
        assert resp.getcode() == 200
        ctype = resp.headers.get("Content-Type")
        size = len(resp.read())
        print(f"JS ({js_name}) Status: {resp.getcode()}, Type: {ctype}, Size: {size} bytes")
        assert "javascript" in ctype or "text/plain" in ctype
    print("PASS: Static frontend assets served cleanly\n")

def test_delivery_selection():
    print("=== CHECK 5: Delivery Day Detail (/api/deliveries/2026-01-02) ===")
    with urllib.request.urlopen(f"{BASE_URL}/api/deliveries/2026-01-02?cutoff=09:00") as resp:
        assert resp.getcode() == 200
        data = json.loads(resp.read().decode())
        print(f"Delivery date: {data['delivery_date']}")
        print(f"Decision date: {data['decision_date']}")
        print(f"Selected vintage publishTime: {data['selected_vintage']['publish_time']}")
        print(f"Hourly series count: {len(data['intervals'])}")
        print(f"MAE: {data['metrics']['mae']:.2f} MW")
        assert data["delivery_date"] == "2026-01-02"
        assert len(data["intervals"]) == 24
        print("PASS: Delivery day detail endpoint verified\n")

def test_csv_export():
    print("=== CHECK 6: CSV Export & 744 Comparison Row Audit ===")
    with urllib.request.urlopen(f"{BASE_URL}/api/export.csv?cutoff=09:00") as resp:
        assert resp.getcode() == 200
        ctype = resp.headers.get("Content-Type")
        content = resp.read().decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(content)))
        print(f"Status: {resp.getcode()}")
        print(f"Content-Type: {ctype}")
        print(f"Total exported rows: {len(rows)}")
        print(f"Columns: {list(rows[0].keys())}")
        print(f"Sample row 1: date={rows[0]['deliveryDate']} time={rows[0]['startTime']} forecast={rows[0]['forecast']} actual={rows[0]['actual']}")
        print(f"Sample row 744: date={rows[-1]['deliveryDate']} time={rows[-1]['startTime']} forecast={rows[-1]['forecast']} actual={rows[-1]['actual']}")
        assert len(rows) == 744
        assert "text/csv" in ctype
        print("PASS: 744 hourly comparison records present and verified\n")

if __name__ == "__main__":
    try:
        test_health()
        test_overview()
        test_frontend_root()
        test_frontend_assets()
        test_delivery_selection()
        test_csv_export()
        print("***************************************************")
        print("ALL 6 LIVE ENDPOINT & DATA INTEGRITY CHECKS PASSED!")
        print("***************************************************")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)
