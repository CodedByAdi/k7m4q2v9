import React from 'react'
import {
  ArrowRight,
  BarChart2,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import type { DeliveryDaySummary, MetricsBlock } from '../api/types'
import { KpiCard } from '../components/KpiCard'

interface AccuracyViewProps {
  metrics: MetricsBlock
  days: DeliveryDaySummary[]
  onSelectDeliveryDate: (date: string) => void
  onNavigateToExplorer: () => void
}

export const AccuracyView: React.FC<AccuracyViewProps> = ({
  metrics,
  days,
  onSelectDeliveryDate,
  onNavigateToExplorer,
}) => {
  // Sort days by MAE descending to identify largest miss days
  const sortedByError = [...days]
    .filter((d) => d.mae !== null)
    .sort((a, b) => (b.mae ?? 0) - (a.mae ?? 0))

  const topMissDays = sortedByError.slice(0, 5)

  // Bias counts
  const overforecastDays = days.filter((d) => (d.bias ?? 0) > 0)
  const underforecastDays = days.filter((d) => (d.bias ?? 0) < 0)

  // Max over/under
  const maxOverDay = [...days].sort((a, b) => (b.bias ?? 0) - (a.bias ?? 0))[0]
  const maxUnderDay = [...days].sort((a, b) => (a.bias ?? 0) - (b.bias ?? 0))[0]

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Accuracy & Bias Distribution</h1>
          <p className="page-subtitle">
            Statistical decomposition of forecast deviations, persistent volumetric bias, and extreme event days.
            Evaluated on real GB wind generation outturns across January 2026.
          </p>
        </div>
      </div>

      {/* KPI Highlights */}
      <div className="kpi-grid">
        <KpiCard
          label="Net Window Bias"
          value={metrics.bias !== null ? `${metrics.bias > 0 ? '+' : ''}${metrics.bias.toLocaleString()}` : null}
          unit="MW"
          subtext="Mean hourly error across all 744 intervals"
          badge={{
            text: (metrics.bias ?? 0) >= 0 ? 'OVERFORECAST' : 'UNDERFORECAST',
            variant: (metrics.bias ?? 0) >= 0 ? 'positive' : 'negative',
          }}
        />

        <KpiCard
          label="Overforecast Days"
          value={overforecastDays.length}
          unit={`/ ${days.length} days`}
          subtext={`Peak overforecast: +${maxOverDay?.bias?.toLocaleString() ?? 0} MW (${maxOverDay?.delivery_date ?? '—'})`}
          badge={{
            text: `${Math.round((overforecastDays.length / days.length) * 100)}% OF DAYS`,
            variant: 'positive',
          }}
        />

        <KpiCard
          label="Underforecast Days"
          value={underforecastDays.length}
          unit={`/ ${days.length} days`}
          subtext={`Peak underforecast: ${maxUnderDay?.bias?.toLocaleString() ?? 0} MW (${maxUnderDay?.delivery_date ?? '—'})`}
          badge={{
            text: `${Math.round((underforecastDays.length / days.length) * 100)}% OF DAYS`,
            variant: 'negative',
          }}
        />

        <KpiCard
          label="Peak Single-Day MAE"
          value={sortedByError[0]?.mae?.toLocaleString() ?? '—'}
          unit="MW"
          subtext={`Recorded on delivery date: ${sortedByError[0]?.delivery_date ?? '—'}`}
          badge={{
            text: 'EXTREME EVENT',
            variant: 'neutral',
          }}
        />
      </div>

      {/* Operational Caveat */}
      <div
        style={{
          backgroundColor: '#ffffff',
          border: '1px solid var(--border-light)',
          borderLeft: '4px solid var(--brand-forest)',
          borderRadius: 4,
          padding: '12px 16px',
          marginBottom: 20,
          fontSize: '12px',
          color: 'var(--text-secondary)',
          lineHeight: 1.6,
        }}
      >
        <strong style={{ color: 'var(--text-primary)' }}>Analytical Scope:</strong>{' '}
        Forecast errors may be relevant to procurement decisions, but this application evaluates wind forecast accuracy only.
        It does not calculate electricity demand, residual load, full procurement requirements, market clearing prices, or financial exposure.
        Neither system surplus nor electricity shortfalls can be inferred from wind generation data alone.
      </div>

      {/* Bias Direction Definitions */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid var(--border-light)',
            borderTop: '3px solid var(--series-forecast)',
            borderRadius: 4,
            padding: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <TrendingUp size={16} style={{ color: 'var(--series-forecast)' }} />
            <h3 style={{ margin: 0, fontSize: '13px', fontWeight: 600 }}>
              Positive Signed Error: Overforecast (Forecast &gt; Actual)
            </h3>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
            The forecast was higher than actual wind output ($f_i &gt; a_i$).
            This indicates that the day-ahead projection over-estimated outturn wind generation for the delivery hour.
            Total system balance and commercial outcomes cannot be determined without corresponding demand and fleet dispatch data.
          </p>
        </div>

        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid var(--border-light)',
            borderTop: '3px solid var(--status-negative-bias)',
            borderRadius: 4,
            padding: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <TrendingDown size={16} style={{ color: 'var(--status-negative-bias)' }} />
            <h3 style={{ margin: 0, fontSize: '13px', fontWeight: 600 }}>
              Negative Signed Error: Underforecast (Forecast &lt; Actual)
            </h3>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
            The forecast was lower than actual wind output ($f_i &lt; a_i$).
            This indicates that the day-ahead projection under-estimated outturn wind generation for the delivery hour.
            Physical power flows and financial cashouts depend on broader market fundamentals not modelled here.
          </p>
        </div>
      </div>

      {/* Top 5 Extreme Forecast Deviation Days */}
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">
            <BarChart2 size={15} />
            Top Extreme Deviation Delivery Days (Ranked by MAE)
          </h2>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Inspecting the tail of forecast uncertainty
          </span>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          <div className="table-wrapper" style={{ border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Delivery Date</th>
                  <th>Decision Date</th>
                  <th>Selected Publication</th>
                  <th className="text-right">Daily MAE (MW)</th>
                  <th className="text-right">Daily RMSE (MW)</th>
                  <th className="text-right">Signed Bias (MW)</th>
                  <th className="text-right">WAPE (%)</th>
                  <th className="text-center">Action</th>
                </tr>
              </thead>
              <tbody>
                {topMissDays.map((day, idx) => {
                  const isDayOver = (day.bias ?? 0) >= 0
                  return (
                    <tr key={day.delivery_date}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-muted)' }}>
                        #{idx + 1}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {day.delivery_date}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {day.decision_date}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {day.selected_publish_time ? day.selected_publish_time.substring(11, 16) + ' UTC' : '—'}
                      </td>
                      <td className="text-right tabular font-bold" style={{ color: 'var(--status-large-miss)' }}>
                        {day.mae !== null ? day.mae.toLocaleString() : '—'}
                      </td>
                      <td className="text-right tabular font-medium">
                        {day.rmse !== null ? day.rmse.toLocaleString() : '—'}
                      </td>
                      <td className="text-right tabular font-medium">
                        <span style={{ color: isDayOver ? 'var(--status-positive-bias)' : 'var(--status-negative-bias)' }}>
                          {isDayOver ? '+' : ''}
                          {day.bias !== null ? day.bias.toLocaleString() : '—'}
                        </span>
                      </td>
                      <td className="text-right tabular font-medium">
                        {day.wape !== null ? `${day.wape}%` : '—'}
                      </td>
                      <td className="text-center">
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            onSelectDeliveryDate(day.delivery_date)
                            onNavigateToExplorer()
                          }}
                        >
                          <span>Inspect Profile</span>
                          <ArrowRight size={11} />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
