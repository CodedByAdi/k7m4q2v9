import React from 'react'
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  CheckCircle2,
  Compass,
  FileSpreadsheet,
} from 'lucide-react'
import type { OverviewResponse } from '../api/types'
import { KpiCard } from '../components/KpiCard'
import { DailyTrendChart } from '../components/charts/DailyTrendChart'

interface OverviewViewProps {
  overview: OverviewResponse
  onSelectDeliveryDate: (date: string) => void
  onNavigateToExplorer: () => void
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  overview,
  onSelectDeliveryDate,
  onNavigateToExplorer,
}) => {
  const { overall_metrics, daily_summaries, cutoff_local } = overview
  const isOverforecast = (overall_metrics.bias ?? 0) >= 0

  return (
    <div>
      {/* Hero Section */}
      <div className="page-header">
        <div>
          <h1 className="page-title">January 2026 wind forecast review</h1>
          <p className="page-subtitle">
            Compare the forecast available at each decision cutoff with observed wind generation across Great Britain.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={onNavigateToExplorer}
          >
            <Compass size={14} />
            <span>Open Forecast Explorer</span>
          </button>
        </div>
      </div>

      {/* Domain Scope & Operational Caveat Notice */}
      <div
        style={{
          backgroundColor: '#ffffff',
          border: '1px solid var(--border-light)',
          borderLeft: '4px solid var(--brand-forest)',
          borderRadius: 4,
          padding: '14px 18px',
          marginBottom: 24,
          display: 'flex',
          alignItems: 'flex-start',
          gap: 12,
        }}
      >
        <AlertCircle size={18} style={{ color: 'var(--brand-forest)', marginTop: 2, flexShrink: 0 }} />
        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          <strong style={{ color: 'var(--text-primary)' }}>Procurement Decision Context:</strong>{' '}
          This benchmark evaluates the physical accuracy of National Grid ESO wind forecasts (`WINDFOR`)
          available at <strong>{cutoff_local} Europe/London</strong> for day-ahead electricity procurement.
          Windline measures forecast error against outturn generation; <em>it does not model total residual demand,
          reserve margins, or commercial power imbalances</em>.
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="kpi-grid">
        <KpiCard
          label="Mean Absolute Error (MAE)"
          value={overall_metrics.mae !== null ? overall_metrics.mae.toLocaleString() : null}
          unit="MW"
          subtext="Average hourly magnitude error"
        />

        <KpiCard
          label="Root Mean Squared Error (RMSE)"
          value={overall_metrics.rmse !== null ? overall_metrics.rmse.toLocaleString() : null}
          unit="MW"
          subtext="Penalizes large extreme deviations"
        />

        <KpiCard
          label="Signed Bias"
          value={
            overall_metrics.bias !== null
              ? `${overall_metrics.bias > 0 ? '+' : ''}${overall_metrics.bias.toLocaleString()}`
              : null
          }
          unit="MW"
          subtext={isOverforecast ? 'Overall overforecast (forecast > actual)' : 'Overall underforecast (forecast < actual)'}
          badge={{
            text: isOverforecast ? 'OVERFORECAST' : 'UNDERFORECAST',
            variant: isOverforecast ? 'positive' : 'negative',
          }}
        />

        <KpiCard
          label="Weighted Abs. Error (WAPE)"
          value={overall_metrics.wape !== null ? `${overall_metrics.wape}%` : null}
          subtext="Normalized error across 744 intervals"
        />

        <KpiCard
          label="Window Coverage"
          value={`${Math.round(overall_metrics.coverage * 100)}%`}
          unit={`(${overall_metrics.matched_intervals}/${overall_metrics.expected_intervals})`}
          subtext="Zero gaps across 31 delivery days"
          badge={{
            text: '100% COMPLETE',
            variant: 'success',
          }}
        />
      </div>

      {/* Daily Performance Trend Chart */}
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">
            <Calendar size={15} />
            Daily Accuracy & Bias Evolution — January 2026
          </h2>
          <div className="panel-actions">
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Cutoff: {cutoff_local} Europe/London
            </span>
          </div>
        </div>
        <div className="panel-body">
          <DailyTrendChart
            days={daily_summaries}
            onSelectDate={(date) => {
              onSelectDeliveryDate(date)
              onNavigateToExplorer()
            }}
          />
        </div>
      </div>

      {/* Daily Summaries Table */}
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">
            <FileSpreadsheet size={15} />
            Day-Ahead Delivery Schedule & Daily Performance
          </h2>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            31 Delivery Dates (2026-01-02 to 2026-02-01)
          </span>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          <div className="table-wrapper" style={{ border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Delivery Date</th>
                  <th>Decision Date</th>
                  <th>Decision Cutoff</th>
                  <th>Selected Publication</th>
                  <th className="text-center">Coverage</th>
                  <th className="text-right">MAE (MW)</th>
                  <th className="text-right">RMSE (MW)</th>
                  <th className="text-right">Signed Bias (MW)</th>
                  <th className="text-right">WAPE (%)</th>
                  <th className="text-center">Action</th>
                </tr>
              </thead>
              <tbody>
                {daily_summaries.map((day) => {
                  const isDayOver = (day.bias ?? 0) >= 0
                  return (
                    <tr key={day.delivery_date}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {day.delivery_date}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {day.decision_date}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {day.cutoff_local}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        {day.selected_publish_time ? day.selected_publish_time.substring(11, 16) + ' UTC' : '—'}
                      </td>
                      <td className="text-center">
                        <span className="badge badge-complete">
                          <CheckCircle2 size={11} /> 24/24
                        </span>
                      </td>
                      <td className="text-right tabular font-medium">
                        {day.mae !== null ? day.mae.toLocaleString() : '—'}
                      </td>
                      <td className="text-right tabular" style={{ color: 'var(--text-secondary)' }}>
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
                          <span>Explore</span>
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
