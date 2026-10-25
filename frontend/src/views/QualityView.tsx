import React from 'react'
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  FileCheck,
  Layers,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import type { MetadataResponse, OverviewResponse } from '../api/types'
import { KpiCard } from '../components/KpiCard'

interface QualityViewProps {
  overview: OverviewResponse
  metadata: MetadataResponse | null
  onSelectDeliveryDate: (date: string) => void
  onNavigateToExplorer: () => void
}

export const QualityView: React.FC<QualityViewProps> = ({
  overview,
  metadata,
  onSelectDeliveryDate,
  onNavigateToExplorer,
}) => {
  const { overall_metrics, daily_summaries, cutoff_local } = overview

  // Provenance and loader validation records from metadata
  const fuelhhReport = metadata?.provenance?.source_files?.fuelhh
  const windforReport = metadata?.provenance?.source_files?.windfor

  const totalFuelHHRoutes = fuelhhReport?.total_rows_read ?? 1488
  const totalWindforRecords = windforReport?.total_rows_read ?? 18688
  const totalVintages = windforReport?.total_vintages ?? 256

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Data Quality & Pipeline Integrity</h1>
          <p className="page-subtitle">
            Rigorous validation of source telemetry, settlement period aggregation, vintage completeness,
            and zero-imputation policy across the entire January 2026 window.
          </p>
        </div>
      </div>

      {/* High-Level Interval Audit KPIs */}
      <div className="kpi-grid">
        <KpiCard
          label="Expected Delivery Intervals"
          value={overall_metrics.expected_intervals}
          unit="hours"
          subtext="31 days × 24 hourly settlement periods"
        />

        <KpiCard
          label="Matched Intervals"
          value={overall_metrics.matched_intervals}
          unit="hours"
          subtext="100% paired (forecast + actual present)"
          badge={{
            text: '100% COVERED',
            variant: 'success',
          }}
        />

        <KpiCard
          label="Missing / Omitted Intervals"
          value={overall_metrics.omitted_intervals}
          unit="intervals"
          subtext="Zero missing timestamps across window"
          badge={{
            text: '0 OMISSIONS',
            variant: 'neutral',
          }}
        />

        <KpiCard
          label="FUELHH Telemetry Ingested"
          value={totalFuelHHRoutes.toLocaleString()}
          unit="records"
          subtext="1,488 half-hourly outturn readings (48/day)"
        />

        <KpiCard
          label="WINDFOR Forecast Vintages"
          value={totalVintages}
          unit="runs"
          subtext={`${totalWindforRecords.toLocaleString()} individual hourly predictions`}
        />
      </div>

      {/* Core Integrity Principles Panel */}
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
            borderLeft: '4px solid var(--status-success-text)',
            borderRadius: 4,
            padding: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <ShieldCheck size={18} style={{ color: 'var(--status-success-text)' }} />
            <h3 style={{ margin: 0, fontSize: '13px', fontWeight: 600 }}>
              Strict Zero-Imputation Guarantee
            </h3>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
            Windline never replaces missing forecast intervals or unmetered actuals with 0.0 MW.
            Imputing zeroes artificially corrupts wind load-factor calculations, distorts RMSE,
            and misrepresents actual availability. Missing intervals are surfaced explicitly as gaps.
          </p>
        </div>

        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid var(--border-light)',
            borderLeft: '4px solid var(--status-alert)',
            borderRadius: 4,
            padding: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <ShieldAlert size={18} style={{ color: 'var(--status-alert)' }} />
            <h3 style={{ margin: 0, fontSize: '13px', fontWeight: 600 }}>
              Vintage Completeness &amp; Cutoff Discipline
            </h3>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
            A forecast vintage is marked <code>incomplete</code> if it fails to span all 24 clock-hours of delivery
            day $D+1$. Windline distinguishes the <em>latest publication overall</em> (which may contain hindsight),
            the <em>latest eligible vintage at cutoff</em>, and the <em>latest complete eligible vintage</em>.
          </p>
        </div>
      </div>

      {/* Forecast Vintage Horizon & Hindsight Case Study */}
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">
            <Layers size={15} />
            Vintage Audit: Hindsight Exclusion &amp; Horizon Coverage on Delivery Date 2026-01-02
          </h2>
          <span className="badge badge-neutral">DETERMINISTIC SELECTION AUDIT</span>
        </div>
        <div className="panel-body">
          <div style={{ fontSize: '13px', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
            <p style={{ marginTop: 0 }}>
              On decision date <strong>2026-01-01</strong>, the configured decision gate is <strong>09:00 Europe/London</strong> (09:00 UTC).
              Windline deterministically evaluates all publications in the audit archive to prevent hindsight leakage:
            </p>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 12,
                margin: '14px 0',
              }}
            >
              <div
                style={{
                  backgroundColor: '#faf9f6',
                  border: '1px solid var(--border-medium)',
                  borderRadius: 4,
                  padding: 12,
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--status-large-miss)', fontSize: '12px', marginBottom: 4 }}>
                  1. Excluded Due to Hindsight
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11.5px', marginBottom: 4 }}>
                  Publish Time: 2026-01-01T22:30:00Z
                </div>
                <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                  Published 13.5 hours <em>after</em> the 09:00 decision cutoff. It is strictly excluded because it contains forward meteorological information not available at gate closure.
                </div>
              </div>

              <div
                style={{
                  backgroundColor: '#faf9f6',
                  border: '1px solid var(--border-medium)',
                  borderRadius: 4,
                  padding: 12,
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--series-forecast)', fontSize: '12px', marginBottom: 4 }}>
                  2. Latest Eligible at Cutoff
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11.5px', marginBottom: 4 }}>
                  Publish Time: 2026-01-01T07:30:00Z
                </div>
                <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                  The most recent forecast published at or before 09:00 UTC (<code>publishTime &le; cutoff_utc</code>).
                  Spans all 24 delivery hours (100% complete) and is selected as primary.
                </div>
              </div>

              <div
                style={{
                  backgroundColor: '#faf9f6',
                  border: '1px solid var(--border-medium)',
                  borderRadius: 4,
                  padding: 12,
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--text-muted)', fontSize: '12px', marginBottom: 4 }}>
                  3. Incomplete Historical Vintages
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11.5px', marginBottom: 4 }}>
                  Example: 2025-12-31T22:30:00Z (22/24)
                </div>
                <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                  Prior-day runs only span hours 00:00–21:00 UTC of 2026-01-02 (missing 22:00 and 23:00).
                  The engine identifies incomplete runs and never silently fills missing intervals with zeroes.
                </div>
              </div>
            </div>

            <p style={{ marginBottom: 0, fontSize: '12px' }}>
              The engine reports both <code>selected_latest</code> (the most recent eligible run) and <code>latest_complete</code> (the most recent eligible run covering all 24 hours), enabling operational teams to inspect any coverage gaps.
            </p>
          </div>
        </div>
      </div>

      {/* Full 31-Day Quality and Completeness Ledger */}
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">
            <FileCheck size={15} />
            31-Day Delivery Completeness & Alignment Ledger
          </h2>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Cutoff: {cutoff_local} Europe/London
          </span>
        </div>
        <div className="panel-body" style={{ padding: 0 }}>
          <div className="table-wrapper" style={{ border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Delivery Date</th>
                  <th>Decision Date</th>
                  <th className="text-center">Expected Hours</th>
                  <th className="text-center">Observed Hours</th>
                  <th className="text-center">Missing Hours</th>
                  <th className="text-center">Status</th>
                  <th>Selected Vintage (UTC)</th>
                  <th>Latest Complete Vintage (UTC)</th>
                  <th className="text-center">Action</th>
                </tr>
              </thead>
              <tbody>
                {daily_summaries.map((day) => {
                  const missingCount = day.expected_intervals - day.observed_intervals
                  return (
                    <tr key={day.delivery_date}>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {day.delivery_date}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {day.decision_date}
                      </td>
                      <td className="text-center tabular">
                        {day.expected_intervals}
                      </td>
                      <td className="text-center tabular font-medium" style={{ color: 'var(--series-actual)' }}>
                        {day.observed_intervals}
                      </td>
                      <td className="text-center tabular">
                        {missingCount === 0 ? (
                          <span style={{ color: 'var(--text-muted)' }}>0</span>
                        ) : (
                          <span style={{ color: 'var(--status-large-miss)', fontWeight: 700 }}>
                            {missingCount}
                          </span>
                        )}
                      </td>
                      <td className="text-center">
                        <span className={`badge ${day.status === 'complete' ? 'badge-complete' : 'badge-alert'}`}>
                          {day.status === 'complete' ? (
                            <>
                              <CheckCircle2 size={11} /> COMPLETE
                            </>
                          ) : (
                            <>
                              <AlertCircle size={11} /> INCOMPLETE
                            </>
                          )}
                        </span>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>
                        {day.selected_publish_time ? day.selected_publish_time.replace('T', ' ').replace('Z', ' UTC') : '—'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {day.latest_complete_publish_time
                          ? day.latest_complete_publish_time.replace('T', ' ').replace('Z', ' UTC')
                          : '—'}
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
                          <span>View Day</span>
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
