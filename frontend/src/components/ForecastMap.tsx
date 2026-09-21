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
  latitude?: number | null;
  longitude?: number | null;
  label?: string;
}

export const ForecastMap: React.FC<ForecastMapProps> = ({
  latitude,
  longitude,
  label = 'Location',
}) => {
  const hasValidCoordinates =
    typeof latitude === 'number' &&
    typeof longitude === 'number' &&
    !isNaN(latitude) &&
    !isNaN(longitude);

  const centerLat = hasValidCoordinates ? latitude : 28.6139;
  const centerLon = hasValidCoordinates ? longitude : 77.2090;
  const position: [number, number] = [centerLat, centerLon];

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
        {hasValidCoordinates && (
          <>
            <Marker position={position}>
              <Popup>
                <div style={{ fontWeight: 600 }}>{label}</div>
                <div style={{ fontSize: '0.8rem', color: '#555' }}>
                  [{centerLat.toFixed(4)}°, {centerLon.toFixed(4)}°]
                </div>
              </Popup>
            </Marker>
            <RecenterMap lat={centerLat} lng={centerLon} />
          </>
        )}
      </MapContainer>
    </div>
  );
};

export default ForecastMap;
