/**
 * Veyra API Client Service
 * Encapsulates all communication with the hardened Veyra FastAPI backend.
 */
import {
  ApiError,
  HealthResponse,
  HorizonPointResult,
  HorizonTimelineRequest,
  HorizonTimelineResult,
  ModelEvaluationResponse,
  PredictionRequest,
  PredictionResponse,
} from './types';

// Resolve base API URL from environment variable or fallback to empty string (same-origin relative URL)
const DEFAULT_BASE_URL =
  import.meta.env?.VITE_API_BASE_URL !== undefined && import.meta.env.VITE_API_BASE_URL !== ''
    ? import.meta.env.VITE_API_BASE_URL
    : '';


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
   * Evaluate bust risk across a multi-horizon timeline for a single location.
   * Concurrently requests predictions for each requested lead horizon from the same issue_time.
   */
  async predictHorizonTimeline(
    request: HorizonTimelineRequest
  ): Promise<HorizonTimelineResult> {
    const preset = request.preset || '7_DAY';
    const leads =
      request.custom_leads ||
      (preset === '16_DAY'
        ? [24, 48, 72, 96, 120, 144, 168, 192, 216, 240, 264, 288, 312, 336, 360, 384]
        : [24, 48, 72, 96, 120, 144, 168]);

    const baseIssueTime = request.issue_time || new Date().toISOString();
    const issueDate = new Date(baseIssueTime);

    // Build independent requests with deterministic valid_time calculation
    const promises = leads.map(async (leadHours) => {
      const validDate = new Date(issueDate.getTime() + leadHours * 3600 * 1000);
      const validTimeIso = validDate.toISOString();

      const predReq: PredictionRequest = {
        location: request.location,
        variable: request.variable,
        issue_time: baseIssueTime,
        valid_time: validTimeIso,
      };

      const result = await this.predictForecastBust(predReq);

      let status: 'SUCCESS' | 'ABSTAINED' | 'ERROR' = 'ERROR';
      let errorMessage: string | undefined = undefined;

      if (result.data) {
        if (result.data.abstain) {
          status = 'ABSTAINED';
        } else {
          status = 'SUCCESS';
        }
      } else if (result.error) {
        status = 'ERROR';
        errorMessage = result.error.message || result.error.error;
      }

      const point: HorizonPointResult = {
        lead_hours: leadHours,
        lead_days: parseFloat((leadHours / 24).toFixed(1)),
        valid_time: validTimeIso,
        response: result.data || null,
        status,
        error_message: errorMessage,
      };

      return point;
    });

    const settled = await Promise.allSettled(promises);

    const points: HorizonPointResult[] = settled.map((res, idx) => {
      if (res.status === 'fulfilled') {
        return res.value;
      }
      const leadHours = leads[idx];
      const validDate = new Date(issueDate.getTime() + leadHours * 3600 * 1000);
      return {
        lead_hours: leadHours,
        lead_days: parseFloat((leadHours / 24).toFixed(1)),
        valid_time: validDate.toISOString(),
        response: null,
        status: 'ERROR',
        error_message: res.reason instanceof Error ? res.reason.message : 'Unknown evaluation error',
      };
    });

    const successfulCount = points.filter((p) => p.status === 'SUCCESS').length;
    const abstainedCount = points.filter((p) => p.status === 'ABSTAINED').length;
    const errorCount = points.filter((p) => p.status === 'ERROR').length;

    return {
      location: request.location,
      variable: request.variable || 'temperature_2m',
      issue_time: baseIssueTime,
      preset,
      points,
      successful_count: successfulCount,
      abstained_count: abstainedCount,
      error_count: errorCount,
    };
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
