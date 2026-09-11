export interface BenchmarkLocation {
  name: string;
  lat: number;
  lon: number;
  region: string;
  country: string;
}

export const BENCHMARK_LOCATIONS: BenchmarkLocation[] = [
  // =========================================================================
  // 25 Canonical Indian Meteorological Benchmark Stations
  // Authoritative registry: trained, backtested, and calibrated by ML eng.
  // =========================================================================
  { name: "Delhi", lat: 28.6139, lon: 77.2090, region: "National Capital Region", country: "India" },
  { name: "Kolkata", lat: 22.5726, lon: 88.3639, region: "West Bengal", country: "India" },
  { name: "Mumbai", lat: 19.0760, lon: 72.8777, region: "Maharashtra", country: "India" },
  { name: "Bengaluru", lat: 12.9716, lon: 77.5946, region: "Karnataka", country: "India" },
  { name: "Chennai", lat: 13.0827, lon: 80.2707, region: "Tamil Nadu", country: "India" },
  { name: "Hyderabad", lat: 17.3850, lon: 78.4867, region: "Telangana", country: "India" },
  { name: "Ahmedabad", lat: 23.0225, lon: 72.5714, region: "Gujarat", country: "India" },
  { name: "Pune", lat: 18.5204, lon: 73.8567, region: "Maharashtra", country: "India" },
  { name: "Jaipur", lat: 26.9124, lon: 75.7873, region: "Rajasthan", country: "India" },
  { name: "Lucknow", lat: 26.8467, lon: 80.9462, region: "Uttar Pradesh", country: "India" },
  { name: "Bhopal", lat: 23.2599, lon: 77.4126, region: "Madhya Pradesh", country: "India" },
  { name: "Nagpur", lat: 21.1458, lon: 79.0882, region: "Maharashtra", country: "India" },
  { name: "Bhubaneswar", lat: 20.2961, lon: 85.8245, region: "Odisha", country: "India" },
  { name: "Ranchi", lat: 23.3441, lon: 85.3096, region: "Jharkhand", country: "India" },
  { name: "Raipur", lat: 21.2514, lon: 81.6296, region: "Chhattisgarh", country: "India" },
  { name: "Guwahati", lat: 26.1445, lon: 91.7362, region: "Assam", country: "India" },
  { name: "Panaji", lat: 15.2993, lon: 73.8278, region: "Goa", country: "India" },
  { name: "Kochi", lat: 9.9312, lon: 76.2673, region: "Kerala", country: "India" },
  { name: "Thiruvananthapuram", lat: 8.5241, lon: 76.9366, region: "Kerala", country: "India" },
  { name: "Visakhapatnam", lat: 17.6868, lon: 83.2185, region: "Andhra Pradesh", country: "India" },
  { name: "Chandigarh", lat: 30.7333, lon: 76.7794, region: "Chandigarh", country: "India" },
  { name: "Dehradun", lat: 30.3165, lon: 78.0322, region: "Uttarakhand", country: "India" },
  { name: "Shimla", lat: 31.1048, lon: 77.1734, region: "Himachal Pradesh", country: "India" },
  { name: "Srinagar", lat: 34.0837, lon: 74.7973, region: "Jammu and Kashmir", country: "India" },
  { name: "Leh", lat: 34.1526, lon: 77.5771, region: "Ladakh", country: "India" },
];

// 25 Primary Calibrated Operational Benchmark Stations across India
export const INDIAN_BENCHMARK_25_STATIONS = BENCHMARK_LOCATIONS.map((l) => l.name);

