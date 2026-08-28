# Veyra — Phase 1 / Builder 2 / Day 1

## Regional Location Resolution & Geocoding Registry

**Project Name:** Veyra — Know When Forecasts May Fail  
**Role:** Builder 2 (Scientific Meteorological Intelligence & ML Subsystem)  
**Component:** `backend/app/builder2/location_service.py`  

---

## 1. Objective

The objective of Builder 2 on Day 1 was to establish the geographical resolution foundation for meteorological forecasts, allowing transparent resolution of named cities, regional aliases, and direct coordinate queries.

---

## 2. Work Completed

1. **Named City Registry:** Built pre-configured geographic coordinate mapping for key global meteorological observation hubs:
   - `Delhi`: `(28.6139, 77.2090)`
   - `London`: `(51.5074, -0.1278)`
   - `Kolkata`: `(22.5726, 88.3639)`
   - `Mumbai`: `(19.0760, 72.8777)`
   - `Tokyo`: `(35.6762, 139.6503)`
   - `Paris`: `(48.8566, 2.3522)`
2. **Direct Coordinate Parsing:** Implemented robust parsing of raw `"lat,lon"` and `"lat, lon"` string inputs into validated floating-point coordinate pairs.
3. **Strict Bounding-Box Validation:** Enforced geographical boundaries:
   - Latitude: $-90.0 \le \text{lat} \le 90.0$
   - Longitude: $-180.0 \le \text{lon} \le 180.0$
4. **Controlled Abstention Rejection:** Queries for unrecognized locations (e.g. `"Atlantis"`) or invalid coordinates cleanly return `None`, enabling upstream orchestrator abstention without throwing unhandled exceptions.

---

## 3. Architecture & Implementation

```python
class RegionalLocationService:
    """Dynamic geographic resolution service supporting city names and coordinate pairs."""
    
    def resolve_location(self, query: str) -> Optional[Tuple[float, float, str]]:
        # 1. Check named city registry (case-insensitive)
        # 2. Check direct "lat,lon" coordinates
        # 3. Validate geographic bounding box
        # 4. Return (lat, lon, normalized_name) or None
```

---

## 4. Verification

- Tested against standard city names: Delhi, London, Kolkata, Mumbai, Tokyo, Paris.
- Tested against direct coordinate strings: `"51.5074, -0.1278"`, `"28.6139, 77.2090"`.
- Verified invalid coordinate rejection: `"999.0, 999.0"`, `"invalid_city"`.

---

## 5. Day Status

**STATUS: COMPLETE**

---

**Next:** [Day 2](./Day-2.md)
