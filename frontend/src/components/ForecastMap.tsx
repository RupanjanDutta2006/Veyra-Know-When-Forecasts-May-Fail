import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';

// Fix default marker icon issues in Vite
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
});

// Helper component to center map when coordinates update
function RecenterMap({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  useEffect(() => {
    if (lat != null && lng != null && !isNaN(lat) && !isNaN(lng)) {
      map.setView([lat, lng], 7);
    }
  }, [lat, lng, map]);
  return null;
}

interface ForecastMapProps {
  latitude?: number;
  longitude?: number;
  label?: string;
}

export const ForecastMap: React.FC<ForecastMapProps> = ({
  latitude = 28.6139,
  longitude = 77.2090,
  label = 'Location',
}) => {
  const validLat = typeof latitude === 'number' && !isNaN(latitude) ? latitude : 28.6139;
  const validLon = typeof longitude === 'number' && !isNaN(longitude) ? longitude : 77.2090;
  const position: [number, number] = [validLat, validLon];

  return (
    <div className="forecast-map-wrapper" role="region" aria-label="Geographic Location Map">
      <MapContainer
        center={position}
        zoom={6}
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%' }}
      >
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
};

export default ForecastMap;
