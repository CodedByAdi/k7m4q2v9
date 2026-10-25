import React from 'react'
import {
  AlertTriangle,
  BookOpen,
  Clock,
  Code2,
  Database,
  ExternalLink,
  Layers,
  Scale,
} from 'lucide-react'
import type { MetadataResponse } from '../api/types'

interface MethodologyViewProps {
  metadata: MetadataResponse | null
  cutoff: string
}

export const MethodologyView: React.FC<MethodologyViewProps> = ({ metadata, cutoff }) => {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Methodology & Market Specification</h1>
          <p className="page-subtitle">
            Formal technical specification of the Windline analysis engine, time conventions,
            aggregation mathematics, forecast selection policy, and verified Elexon telemetry provenance.
          </p>
        </div>
      </div>

      {/* Overview Card */}
      <div
        style={{
          backgroundColor: '#ffffff',
          border: '1px solid var(--border-light)',
          borderLeft: '4px solid var(--brand-forest)',
          borderRadius: 4,
          padding: '16px 20px',
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <BookOpen size={18} style={{ color: 'var(--brand-forest)' }} />
          <h2 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>
            Institutional Evaluation Scope
          </h2>
        </div>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.7, margin: 0 }}>
          Windline evaluates the accuracy of National Grid ESO day-ahead wind generation forecasts
          produced for Great Britain (GB). The study isolates the decision window from{' '}
          <strong>2026-01-01 to 2026-01-31</strong> (31 decision cutoffs) and corresponding delivery dates{' '}
          <strong>2026-01-02 to 2026-02-01</strong> (31 delivery days, 744 hourly settlement intervals).
          All forecast selections are deterministic and strictly enforced without hindsight.
        </p>
      </div>

      {/* Grid of Core Technical Principles */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: 20,
          marginBottom: 24,
        }}
      >
        {/* Cutoff Assumption */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">
              <Clock size={15} />
              Decision Cutoff: 09:00 Europe/London
            </h3>
            <span className="badge badge-neutral">CONFIGURABLE ASSUMPTION</span>
          </div>
          <div className="panel-body" style={{ fontSize: '12.5px', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            <p style={{ marginTop: 0 }}>
              The default cutoff is set to <strong>{cutoff} Europe/London</strong>.
              In GB wholesale power markets, day-ahead auction gate closure occurs at 11:00 GMT (EPEX SPOT)
              and 12:00 GMT (Nord Pool).
            </p>
            <p>
              However, commercial energy procurement desks, portfolio optimizers, and asset dispatchers
              require early-morning forecast freezes to run asset commitment models and formulate bidding curves.
              Windline treats 09:00 as an <em>operational desk assumption</em> rather than a regulatory hard gate.
              Only forecasts published with <code>publishTime &le; cutoff_utc</code> are eligible.
            </p>
          </div>
        </div>

        {/* Resolution & Aggregation */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">
              <Scale size={15} />
              Hourly Temporal Aggregation
            </h3>
            <span className="badge badge-neutral">ARITHMETIC MEAN</span>
          </div>
          <div className="panel-body" style={{ fontSize: '12.5px', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            <p style={{ marginTop: 0 }}>
              <strong>Actuals (FUELHH):</strong> Reported half-hourly across 48 settlement periods (SP 1–48)
              in MW average power.
            </p>
            <p>
              <strong>Forecasts (WINDFOR):</strong> Published hourly on the hour (24 intervals per delivery day).
            </p>
            <div
              style={{
                backgroundColor: '#faf9f6',
                border: '1px solid var(--border-medium)',
                borderRadius: 4,
                padding: '10px 14px',
                fontFamily: 'var(--font-mono)',
                fontSize: '11.5px',
                margin: '8px 0',
              }}
            >
              Actual_Hour[h] = (SP[2h - 1] + SP[2h]) / 2.0
            </div>
            <p style={{ marginBottom: 0 }}>
              Both half-hours must be valid and unmetered data is never fabricated.
              This aligns time series on identical 60-minute boundaries.
            </p>
          </div>
        </div>

        {/* Vintage Selection Policy */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">
              <Layers size={15} />
              Single Consistent Vintage Policy
            </h3>
            <span className="badge badge-neutral">NO VINTAGE STITCHING</span>
          </div>
          <div className="panel-body" style={{ fontSize: '12.5px', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            <p style={{ marginTop: 0 }}>
              Forecast runs are never spliced across multiple publication timestamps.
              Stitching hours 00:00–12:00 from run A and hours 13:00–23:00 from run B creates an artificial,
              discontinuous forecast that never existed in the meteorological model.
            </p>
            <p style={{ marginBottom: 0 }}>
              Windline selects the latest complete eligible publication vintage available prior to the cutoff
              to represent the physical asset schedule available to the procurement desk.
            </p>
          </div>
        </div>

        {/* Unresolved Publication Discrepancy */}
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">
              <AlertTriangle size={15} style={{ color: 'var(--status-alert)' }} />
              Unresolved Publication Schedule Discrepancy
            </h3>
            <span className="badge badge-alert">UNRESOLVED DISCREPANCY</span>
          </div>
          <div className="panel-body" style={{ fontSize: '12.5px', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            <p style={{ marginTop: 0 }}>
              <strong>Documented Update Times:</strong> Public Elexon materials list forecast update schedules
              at nominal times <strong>03:30, 05:30, 08:30</strong> (the source documentation does not explicitly label a timezone for these update times).
            </p>
            <p>
              <strong>Audited API Telemetry:</strong> Audited API records across the January window consistently arrive with <code>publishTime</code> timestamps
              at <strong>02:30Z, 04:30Z, 07:30Z</strong> (explicit UTC timestamps with trailing <code>Z</code>).
            </p>
            <p style={{ marginBottom: 0 }}>
              The backend evaluates each recorded <code>publishTime</code> as an ISO 8601 timezone-aware timestamp against the configured cutoff (<code>publishTime &le; cutoff_utc</code>).
              This discrepancy remains <strong>unresolved</strong> between public narrative materials and the live BMRS API pipeline.
            </p>
          </div>
        </div>
      </div>

      {/* Mathematical Metrics Formulation */}
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">
            <Code2 size={15} />
            Mathematical Metric Definitions & Exclusion of MAPE
          </h2>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Standard Power Systems Engineering Error Formulations
          </span>
        </div>
        <div className="panel-body">
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: 16,
              marginBottom: 16,
            }}
          >
            <div style={{ backgroundColor: '#faf9f6', padding: 14, borderRadius: 4, border: '1px solid var(--border-medium)' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: 4 }}>
                Mean Absolute Error (MAE)
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--brand-forest)', marginBottom: 6 }}>
                MAE = (1 / N) * ∑ |f_i - a_i|
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Average absolute magnitude of hourly forecast deviations in MW.
              </div>
            </div>

            <div style={{ backgroundColor: '#faf9f6', padding: 14, borderRadius: 4, border: '1px solid var(--border-medium)' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: 4 }}>
                Root Mean Squared Error (RMSE)
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--brand-forest)', marginBottom: 6 }}>
                RMSE = sqrt((1 / N) * ∑ (f_i - a_i)²)
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Quadratic loss metric that penalizes large individual forecast deviations in MW.
              </div>
            </div>

            <div style={{ backgroundColor: '#faf9f6', padding: 14, borderRadius: 4, border: '1px solid var(--border-medium)' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: 4 }}>
                Signed Mean Bias
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--brand-forest)', marginBottom: 6 }}>
                Bias = (1 / N) * ∑ (f_i - a_i)
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Persistent directional error in MW. Positive values indicate systematic overforecasting.
              </div>
            </div>

            <div style={{ backgroundColor: '#faf9f6', padding: 14, borderRadius: 4, border: '1px solid var(--border-medium)' }}>
              <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: 4 }}>
                Weighted Abs. Percentage Error (WAPE)
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--brand-forest)', marginBottom: 6 }}>
                WAPE = (∑ |f_i - a_i| / ∑ a_i) * 100%
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Volume-weighted relative error. Normalized against aggregate wind generation.
              </div>
            </div>
          </div>

          <div
            style={{
              backgroundColor: '#ffffff',
              border: '1px solid var(--border-medium)',
              borderLeft: '4px solid var(--status-large-miss)',
              borderRadius: 4,
              padding: '12px 16px',
            }}
          >
            <strong style={{ fontSize: '12.5px', color: 'var(--status-large-miss)' }}>
              Why MAPE is Strictly Prohibited:
            </strong>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0', lineHeight: 1.6 }}>
              Mean Absolute Percentage Error (MAPE) computes <code>(1 / N) * ∑ (|f_i - a_i| / a_i)</code>.
              During low-wind periods or summer calms where generation approaches zero, division by <code>a_i</code> produces
              arbitrarily massive percentage spikes (e.g., a 10 MW miss on 5 MW actual yields 200% error).
              In professional energy analytics, MAPE is considered statistically invalid for renewable generation;
              WAPE is the recognized industry standard.
            </p>
          </div>
        </div>
      </div>

      {/* Data Source Provenance & Licensing */}
      <div className="panel">
        <div className="panel-header">
          <h2 className="panel-title">
            <Database size={15} />
            Data Source Provenance & Licensing
          </h2>
          <a
            href="https://data.elexon.co.uk/bmrs/api/v1"
            target="_blank"
            rel="noreferrer"
            className="btn btn-secondary btn-sm"
          >
            <span>Elexon OpenAPI Portal</span>
            <ExternalLink size={12} />
          </a>
        </div>
        <div className="panel-body" style={{ fontSize: '12.5px', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          <p style={{ marginTop: 0 }}>
            All telemetry used by Windline is sourced directly from the official{' '}
            <strong>{metadata?.data_provider ?? 'Elexon Insights Solution (BMRS)'}</strong> API (
            <code>{metadata?.api_base_url ?? 'https://data.elexon.co.uk/bmrs/api/v1'}</code>).
            Elexon is the balancing and settlement code company for the electricity system of Great Britain.
          </p>
          <ul style={{ paddingLeft: 20, margin: '8px 0' }}>
            <li>
              <strong>FUELHH:</strong> Half-Hourly Generation by Fuel Type (Endpoint: <code>/generation/actual/per-fuel-type</code>).
              Filtered strictly to <code>fuelType=WIND</code>.
            </li>
            <li>
              <strong>WINDFOR:</strong> Wind Generation Forecast and Outturn (Endpoint: <code>/forecast/generation/wind</code>).
              Each forecast publication is an immutable vintage containing national generation projections.
            </li>
            <li>
              <strong>Time Standard:</strong> All internal timestamps are ISO 8601 in UTC with explicit <code>Z</code> suffix.
            </li>
            <li>
              <strong>Licensing &amp; Attribution:</strong> Contains BMRS data &copy; Elexon Limited copyright and database right 2026. Sourced under the{' '}
              <a
                href="https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/"
                target="_blank"
                rel="noreferrer"
                style={{ color: 'var(--brand-forest)', textDecoration: 'underline' }}
              >
                BMRS Open Data Licence
              </a>
              . Elexon Limited does not endorse or approve Windline or its analytical findings.
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
