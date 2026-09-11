import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useEffect } from 'react';

// Fix default marker icon issues in Vite
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
});

// Helper component to center map when coordinates update
function RecenterMap({ lat, lng }) {
  const map = useMap();
  useEffect(() => {
    if (lat != null && lng != null && !isNaN(lat) && !isNaN(lng)) {
      map.setView([lat, lng], 7);
    }
  }, [lat, lng, map]);
  return null;
}

export default function ForecastMap({ latitude = 28.6139, longitude = 77.2090, label = 'Location' }) {
  const validLat = typeof latitude === 'number' && !isNaN(latitude) ? latitude : 28.6139;
  const validLon = typeof longitude === 'number' && !isNaN(longitude) ? longitude : 77.2090;
  const position = [validLat, validLon];

  return (
    <div className="forecast-map-wrapper">
      <MapContainer center={position} zoom={6} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Marker position={position}>
          <Popup>
            <div style={{ fontWeight: 600 }}>{label}</div>
            <div style={{ fontSize: '0.8rem', color: '#555' }}>
              [{validLat.toFixed(4)}°, {validLon.toFixed(4)}°]
            </div>
          </Popup>
        </Marker>
        <RecenterMap lat={validLat} lng={validLon} />
      </MapContainer>
    </div>
  );
}
