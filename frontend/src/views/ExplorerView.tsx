import React, { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Download,
  Layers,
} from 'lucide-react'
import { apiClient } from '../api/client'
import type { DeliveryDayDetailResponse, VintagesAuditResponse } from '../api/types'
import { DaySeriesChart } from '../components/charts/DaySeriesChart'
import { KpiCard } from '../components/KpiCard'
import { VintagesModal } from '../components/VintagesModal'

interface ExplorerViewProps {
  availableDates: string[]
  selectedDate: string
  cutoff: string
  onSelectDate: (date: string) => void
}

export const ExplorerView: React.FC<ExplorerViewProps> = ({
  availableDates,
  selectedDate,
  cutoff,
  onSelectDate,
}) => {
  const [detail, setDetail] = useState<DeliveryDayDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [vintagesData, setVintagesData] = useState<VintagesAuditResponse | null>(null)
  const [isVintagesModalOpen, setIsVintagesModalOpen] = useState(false)

  // Fetch delivery day details when date or cutoff changes
  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    apiClient
      .getDeliveryDetail(selectedDate, cutoff)
      .then((data) => {
        if (active) {
          setDetail(data)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (active) {
          setError(err.message || 'Failed to load delivery day detail')
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [selectedDate, cutoff])

  const handleOpenVintagesModal = async () => {
    try {
      const data = await apiClient.getDeliveryVintages(selectedDate, cutoff)
      setVintagesData(data)
      setIsVintagesModalOpen(true)
    } catch (err: any) {
      alert(`Could not load vintages: ${err.message}`)
    }
  }

  // Previous and next date handlers
  const currentIndex = availableDates.indexOf(selectedDate)
  const hasPrev = currentIndex > 0
  const hasNext = currentIndex < availableDates.length - 1

  const handlePrev = () => {
    if (hasPrev) onSelectDate(availableDates[currentIndex - 1])
  }

  const handleNext = () => {
    if (hasNext) onSelectDate(availableDates[currentIndex + 1])
  }

  if (loading) {
    return (
      <div className="state-box">
        <div className="spinner" />
        <p>Loading forecast alignment for {selectedDate}...</p>
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="state-box" style={{ color: 'var(--status-large-miss)' }}>
        <AlertTriangle size={24} />
        <p><strong>Error:</strong> {error || 'Unable to retrieve delivery day'}</p>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => onSelectDate(availableDates[0] || '2026-01-02')}
        >
          Reset to Window Start (2026-01-02)
        </button>
      </div>
    )
  }

  const isDayOver = (detail.metrics.bias ?? 0) >= 0

  return (
    <div>
      {/* Date Selector & Navigation Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
          backgroundColor: '#ffffff',
          padding: '14px 20px',
          border: '1px solid var(--border-light)',
          borderRadius: 4,
          marginBottom: 20,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', gap: 4 }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handlePrev}
              disabled={!hasPrev}
              aria-label="Previous delivery day"
            >
              <ArrowLeft size={13} />
              <span>Prev Day</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleNext}
              disabled={!hasNext}
              aria-label="Next delivery day"
            >
              <span>Next Day</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <label htmlFor="delivery-select" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Delivery Date:
            </label>
            <select
              id="delivery-select"
              value={selectedDate}
              onChange={(e) => onSelectDate(e.target.value)}
              style={{
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                fontSize: '13px',
                padding: '5px 10px',
                borderRadius: 4,
                border: '1px solid var(--border-medium)',
                backgroundColor: '#faf9f6',
              }}
            >
              {availableDates.map((d) => (
                <option key={d} value={d}>
                  {d} (Decision: {new Date(new Date(d).getTime() - 86400000).toISOString().split('T')[0]})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleOpenVintagesModal}
          >
            <Layers size={13} />
            <span>Audit All Vintages</span>
          </button>

          <a
            href={apiClient.getExportCsvUrl(cutoff)}
            className="btn btn-secondary btn-sm"
            download
            title="Export complete 744-interval hourly comparison table across January 2026 as CSV"
          >
            <Download size={13} />
            <span>Export Full-Window CSV</span>
          </a>
        </div>
      </div>

      {/* Selected Day Context & KPIs */}
      <div className="kpi-grid">
        <KpiCard
          label="Delivery Schedule"
          value={detail.delivery_date}
          subtext={`Procured on decision date: ${detail.decision_date}`}
        />

        <KpiCard
          label="Selected Forecast Run"
          value={
            detail.selected_vintage
              ? detail.selected_vintage.publish_time.substring(11, 16) + ' UTC'
              : 'None'
          }
          subtext={`Cutoff: ${detail.cutoff_local} Europe/London`}
          badge={{
            text: detail.status === 'complete' ? 'COMPLETE VINTAGE' : 'INCOMPLETE',
            variant: detail.status === 'complete' ? 'success' : 'negative',
          }}
        />

        <KpiCard
          label="Daily MAE"
          value={detail.metrics.mae !== null ? detail.metrics.mae.toLocaleString() : null}
          unit="MW"
          subtext="Mean absolute error over 24 hours"
        />

        <KpiCard
          label="Daily Signed Bias"
          value={
            detail.metrics.bias !== null
              ? `${detail.metrics.bias > 0 ? '+' : ''}${detail.metrics.bias.toLocaleString()}`
              : null
          }
          unit="MW"
          subtext={isDayOver ? 'Overforecast on this day (f > a)' : 'Underforecast on this day (f < a)'}
          badge={{
            text: isDayOver ? '+ OVER' : '- UNDER',
            variant: isDayOver ? 'positive' : 'negative',
          }}
        />

        <KpiCard
          label="Daily WAPE"
          value={detail.metrics.wape !== null ? `${detail.metrics.wape}%` : null}
          subtext={`RMSE: ${detail.metrics.rmse ? detail.metrics.rmse.toLocaleString() + ' MW' : '—'}`}
        />
      </div>

      {/* Hourly Forecast vs Actual Chart */}
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">
            24-Hour Generation Profile — {detail.delivery_date}
          </h2>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Selected Vintage: {detail.selected_vintage?.publish_time || 'None'}
          </span>
        </div>
        <div className="panel-body">
          <DaySeriesChart intervals={detail.intervals} height={340} />
        </div>
      </div>

      {/* Hourly Intervals Table with Full Half-Hour Traceability */}
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">
            Hourly Comparison Intervals &amp; Settlement Period Traceability
          </h2>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            24 Hourly Intervals (UTC). Each hourly actual is the mean of two half-hourly FUELHH readings.
          </span>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          <div className="table-wrapper" style={{ border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Hourly Clock Interval (UTC)</th>
                  <th>Constituent Half-Hours (FUELHH)</th>
                  <th className="text-right">WINDFOR Forecast</th>
                  <th className="text-right">Actual Hourly Mean</th>
                  <th className="text-right">Signed Error (MW)</th>
                  <th className="text-right">Absolute Error (MW)</th>
                  <th>Interval Assessment</th>
                </tr>
              </thead>
              <tbody>
                {detail.intervals.map((interval, i) => {
                  const signedErr = interval.signed_error_mw
                  const isOver = (signedErr ?? 0) > 0
                  const isLargeMiss = (interval.absolute_error_mw ?? 0) >= 3000
                  const hourStart = String(i).padStart(2, '0')
                  const hourEnd = String((i + 1) % 24).padStart(2, '0')
                  const sp1 = i * 2 + 1
                  const sp2 = i * 2 + 2

                  return (
                    <tr
                      key={interval.startTime}
                      style={{
                        backgroundColor: isLargeMiss ? 'rgba(254, 242, 242, 0.4)' : undefined,
                      }}
                    >
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {hourStart}:00–{hourEnd}:00 UTC
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                        <div>
                          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>SP {sp1}</span> ({hourStart}:00–{hourStart}:30) &amp;{' '}
                          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>SP {sp2}</span> ({hourStart}:30–{hourEnd}:00)
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {interval.actual_half_hour_count}/2 readings aggregated
                        </div>
                      </td>
                      <td className="text-right tabular font-medium" style={{ color: 'var(--series-forecast)' }}>
                        {interval.forecast_mw !== null ? `${interval.forecast_mw.toLocaleString()} MW` : '—'}
                      </td>
                      <td className="text-right tabular font-medium" style={{ color: 'var(--series-actual)' }}>
                        <div>{interval.actual_mw !== null ? `${interval.actual_mw.toLocaleString()} MW` : '—'}</div>
                        <div style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>
                          Mean of SP {sp1} &amp; {sp2}
                        </div>
                      </td>
                      <td className="text-right tabular font-medium">
                        <span style={{ color: isOver ? 'var(--status-positive-bias)' : 'var(--status-negative-bias)' }}>
                          {isOver ? '+' : ''}
                          {signedErr !== null ? `${signedErr.toLocaleString()} MW` : '—'}
                        </span>
                      </td>
                      <td className="text-right tabular font-medium">
                        {interval.absolute_error_mw !== null ? `${interval.absolute_error_mw.toLocaleString()} MW` : '—'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                          <span className={`badge ${isOver ? 'badge-over' : 'badge-under'}`}>
                            {isOver ? 'Overforecast (f > a)' : 'Underforecast (f < a)'}
                          </span>
                          {isLargeMiss && (
                            <span
                              className="badge badge-alert"
                              title="Application-defined exploratory threshold to highlight large absolute deviations (≥ 3,000 MW); not an official market limit or quantified risk threshold."
                            >
                              Large absolute error ≥ 3,000 MW
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div
            style={{
              padding: '10px 16px',
              fontSize: '11px',
              color: 'var(--text-muted)',
              borderTop: '1px solid var(--border-light)',
              backgroundColor: '#faf9f6',
            }}
          >
            * Explanatory threshold note: &quot;Large absolute error ≥ 3,000 MW&quot; is an application-defined exploratory threshold to assist visual inspection of significant deviation intervals. It is not an official market limit, regulatory standard, or quantified financial risk threshold. Each hourly actual is the arithmetic mean of its two constituent half-hour settlement periods.
          </div>
        </div>
      </div>

      {/* Eligible Vintages Modal */}
      {isVintagesModalOpen && (
        <VintagesModal
          data={vintagesData}
          onClose={() => setIsVintagesModalOpen(false)}
        />
      )}
    </div>
  )
}
