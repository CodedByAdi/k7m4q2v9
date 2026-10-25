import React from 'react'
import { X, CheckCircle2, AlertTriangle } from 'lucide-react'
import type { VintagesAuditResponse } from '../api/types'

interface VintagesModalProps {
  data: VintagesAuditResponse | null
  onClose: () => void
}

export const VintagesModal: React.FC<VintagesModalProps> = ({ data, onClose }) => {
  if (!data) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(10, 31, 20, 0.6)',
        backdropFilter: 'blur(2px)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="vintages-modal-title"
    >
      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: 4,
          border: '1px solid var(--border-medium)',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
          maxWidth: 860,
          width: '100%',
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div>
            <h3 id="vintages-modal-title" className="panel-title">
              Eligible Forecast Vintages Audit — Delivery: {data.delivery_date}
            </h3>
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
              Decision Date: {data.decision_date} | Cutoff: {data.cutoff_local} Europe/London ({data.cutoff_utc} UTC)
            </p>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onClose}
            aria-label="Close modal"
          >
            <X size={14} />
          </button>
        </div>

        <div style={{ padding: 20, overflowY: 'auto' }}>
          <div
            style={{
              padding: 12,
              backgroundColor: '#faf9f6',
              border: '1px solid var(--border-light)',
              borderRadius: 4,
              fontSize: '12px',
              color: 'var(--text-secondary)',
              marginBottom: 16,
            }}
          >
            <strong>Vintage Selection Policy:</strong> Forecast publications must have{' '}
            <code>publishTime &le; cutoff_utc</code>. The primary selected forecast is the most recent
            eligible publication containing records for delivery date {data.delivery_date}. If it is incomplete,
            it is flagged and not silently replaced by an older publication.
          </div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Publication Timestamp (UTC)</th>
                  <th className="text-center">Total Horizon</th>
                  <th className="text-center">Delivery Hours Covered</th>
                  <th className="text-center">Completeness</th>
                  <th>Classification / Role</th>
                </tr>
              </thead>
              <tbody>
                {data.eligible_vintages.map((v) => {
                  return (
                    <tr
                      key={v.publish_time}
                      style={{
                        backgroundColor: v.is_selected_latest
                          ? 'rgba(29, 78, 216, 0.05)'
                          : undefined,
                      }}
                    >
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {v.publish_time}
                      </td>
                      <td className="text-center tabular">{v.total_intervals} hrs</td>
                      <td className="text-center tabular font-semibold">
                        {v.delivery_intervals_covered} / 24 hrs
                      </td>
                      <td className="text-center">
                        {v.is_complete ? (
                          <span className="badge badge-complete">
                            <CheckCircle2 size={11} /> 100% Complete
                          </span>
                        ) : (
                          <span className="badge badge-incomplete">
                            <AlertTriangle size={11} /> Incomplete ({Math.round(v.coverage_ratio * 100)}%)
                          </span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          {v.is_selected_latest && (
                            <span className="badge badge-over" style={{ backgroundColor: '#1d4ed8', color: '#ffffff' }}>
                              Primary Selected (Latest Available)
                            </span>
                          )}
                          {v.is_latest_complete && (
                            <span className="badge badge-complete">
                              Latest Complete Vintage
                            </span>
                          )}
                          {!v.is_selected_latest && !v.is_latest_complete && (
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                              Eligible Prior Run
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
        </div>

        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border-light)', backgroundColor: '#faf9f6', display: 'flex', justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
