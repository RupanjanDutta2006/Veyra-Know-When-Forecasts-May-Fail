/**
 * Veyra API Client Service
 * Encapsulates all communication with the hardened Veyra FastAPI backend.
 */
import {
  ApiError,
  HealthResponse,
  ModelEvaluationResponse,
  PredictionRequest,
  PredictionResponse,
} from './types';

// Resolve base API URL from environment variable or fallback to empty string (relative) / localhost
const DEFAULT_BASE_URL =
  import.meta.env?.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : window.location.port === '5173'
    ? '' // Use Vite proxy in development
    : 'http://127.0.0.1:8000';

export class VeyraApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = DEFAULT_BASE_URL) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  /**
   * Predict forecast bust probability for a given location and parameters.
   */
  async predictForecastBust(
    request: PredictionRequest,
    customRequestId?: string
  ): Promise<{ data?: PredictionResponse; error?: ApiError; requestId?: string }> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    };

    if (customRequestId) {
      headers['X-Request-ID'] = customRequestId;
    }

    try {
      const endpoint = `${this.baseUrl}/v1/predict`;
      const response = await fetch(endpoint, {
        method: 'POST',
        headers,
        body: JSON.stringify(request),
      });

      const responseRequestId =
        response.headers.get('x-request-id') || response.headers.get('X-Request-ID') || undefined;

      if (!response.ok) {
        const error = await this.parseErrorResponse(response, responseRequestId);
        return { error, requestId: responseRequestId };
      }

      const data: PredictionResponse = await response.json();
      return { data, requestId: responseRequestId };
    } catch (err: unknown) {
      return {
        error: {
          error: 'NETWORK_ERROR',
          message:
            err instanceof Error
              ? `Unable to connect to Veyra backend: ${err.message}`
              : 'Network request failed. Please check backend connection.',
          status_code: 0,
        },
      };
    }
  }

  /**
   * Check backend health and service status.
   */
  async getHealth(): Promise<{ data?: HealthResponse; error?: ApiError }> {
    try {
      const response = await fetch(`${this.baseUrl}/v1/health`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      });

      if (!response.ok) {
        const error = await this.parseErrorResponse(response);
        return { error };
      }

      const data: HealthResponse = await response.json();
      return { data };
    } catch (err: unknown) {
      return {
        error: {
          error: 'HEALTH_CHECK_FAILED',
          message: 'Backend server is unreachable.',
          status_code: 0,
        },
      };
    }
  }

  /**
   * Fetch active model evaluation metrics and calibration status.
   */
  async getModelEvaluation(): Promise<{ data?: ModelEvaluationResponse; error?: ApiError }> {
    try {
      const response = await fetch(`${this.baseUrl}/v1/model/evaluation`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      });

      if (!response.ok) {
        const error = await this.parseErrorResponse(response);
        return { error };
      }

      const data: ModelEvaluationResponse = await response.json();
      return { data };
    } catch (err: unknown) {
      return {
        error: {
          error: 'EVALUATION_FETCH_FAILED',
          message: 'Unable to fetch model evaluation metadata.',
          status_code: 0,
        },
      };
    }
  }

  /**
   * Helper to parse structured error payloads from FastAPI handlers.
   */
  private async parseErrorResponse(
    response: Response,
    headerRequestId?: string
  ): Promise<ApiError> {
    const statusCode = response.status;
    const retryAfterHeader = response.headers.get('Retry-After');
    let retryAfterSeconds: number | undefined;

    if (retryAfterHeader) {
      const parsed = parseInt(retryAfterHeader, 10);
      if (!isNaN(parsed) && parsed > 0) {
        retryAfterSeconds = parsed;
      }
    }

    try {
      const payload = await response.json();
      return {
        error: payload.error || (statusCode === 429 ? 'RATE_LIMIT_EXCEEDED' : 'API_ERROR'),
        message: payload.message || (typeof payload.detail === 'string' ? payload.detail : undefined),
        detail: payload.detail,
        retry_after_seconds: payload.retry_after_seconds || retryAfterSeconds,
        request_id: payload.request_id || headerRequestId,
        status_code: statusCode,
      };
    } catch {
      return {
        error: statusCode === 429 ? 'RATE_LIMIT_EXCEEDED' : `HTTP_${statusCode}`,
        message: `Server returned HTTP ${statusCode}`,
        retry_after_seconds: retryAfterSeconds,
        request_id: headerRequestId,
        status_code: statusCode,
      };
    }
  }
}

export const apiClient = new VeyraApiClient();
