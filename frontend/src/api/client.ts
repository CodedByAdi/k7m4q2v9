/**
 * Typed API client for Windline backend.
 * Single source of truth for all network requests.
 */

import type {
  DeliveriesListResponse,
  DeliveryDayDetailResponse,
  HealthResponse,
  MetadataResponse,
  OverviewResponse,
  VintagesAuditResponse,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

async function request<T>(endpoint: string): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  const response = await fetch(url, {
    headers: {
      Accept: 'application/json',
    },
  })

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`
    try {
      const errorJson = await response.json()
      if (errorJson && errorJson.detail) {
        errorMessage = typeof errorJson.detail === 'string'
          ? errorJson.detail
          : JSON.stringify(errorJson.detail)
      }
    } catch {
      // Non-JSON error body
    }
    throw new Error(errorMessage)
  }

  return response.json() as Promise<T>
}

export const apiClient = {
  getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/health')
  },

  getMetadata(): Promise<MetadataResponse> {
    return request<MetadataResponse>('/metadata')
  },

  getOverview(cutoff = '09:00'): Promise<OverviewResponse> {
    const params = new URLSearchParams({ cutoff })
    return request<OverviewResponse>(`/overview?${params.toString()}`)
  },

  getDeliveries(cutoff = '09:00'): Promise<DeliveriesListResponse> {
    const params = new URLSearchParams({ cutoff })
    return request<DeliveriesListResponse>(`/deliveries?${params.toString()}`)
  },

  getDeliveryDetail(deliveryDate: string, cutoff = '09:00'): Promise<DeliveryDayDetailResponse> {
    const params = new URLSearchParams({ cutoff })
    return request<DeliveryDayDetailResponse>(`/deliveries/${deliveryDate}?${params.toString()}`)
  },

  getDeliveryVintages(deliveryDate: string, cutoff = '09:00'): Promise<VintagesAuditResponse> {
    const params = new URLSearchParams({ cutoff })
    return request<VintagesAuditResponse>(`/deliveries/${deliveryDate}/vintages?${params.toString()}`)
  },

  getExportCsvUrl(cutoff = '09:00'): string {
    const params = new URLSearchParams({ cutoff })
    return `${API_BASE}/export.csv?${params.toString()}`
  },
}
