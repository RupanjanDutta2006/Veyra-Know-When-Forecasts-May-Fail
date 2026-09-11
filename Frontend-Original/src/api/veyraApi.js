import { apiRequest } from './client';

export function getHealth() {
  return apiRequest('/v1/health', { timeout: 4000 });
}

export function predictLocation(payload) {
  const body = typeof payload === 'string' ? { location: payload } : payload;
  return apiRequest('/v1/predict', {
    method: 'POST',
    body: JSON.stringify(body),
    timeout: 20000,
  });
}

export function predictBatch(locations, variable = 'temperature_2m') {
  const locList = Array.isArray(locations)
    ? locations.map((loc) => (typeof loc === 'string' ? loc.trim() : (loc.name || loc.location || '').trim())).filter(Boolean)
    : [String(locations).trim()];

  return apiRequest('/v1/predict/batch', {
    method: 'POST',
    body: JSON.stringify({
      locations: locList,
      variable,
    }),
    timeout: 120000, // 2-minute allowance for full 25-station synoptic grid batch
  });
}

export function getModelEvaluation(model = 'v3') {
  return apiRequest(`/v1/model/evaluation?model=${model}`, { timeout: 6000 });
}

export function getDashboardIntelligence(payload) {
  const body = typeof payload === 'string' ? { location: payload } : payload;
  return apiRequest('/v1/dashboard/intelligence', {
    method: 'POST',
    body: JSON.stringify(body),
    timeout: 25000,
  });
}
