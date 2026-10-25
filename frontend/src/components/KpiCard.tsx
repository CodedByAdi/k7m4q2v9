import React from 'react'

interface KpiCardProps {
  label: string
  value: string | number | null
  unit?: string
  subtext?: string
  badge?: {
    text: string
    variant: 'positive' | 'negative' | 'neutral' | 'success'
  }
}

export const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  unit,
  subtext,
  badge,
}) => {
  const displayValue = value === null || value === undefined ? '—' : value

  return (
    <div className="kpi-card" role="region" aria-label={label}>
      <div>
        <div className="kpi-label">
          <span>{label}</span>
          {badge && (
            <span
              className={`badge ${
                badge.variant === 'positive'
                  ? 'badge-over'
                  : badge.variant === 'negative'
                  ? 'badge-under'
                  : badge.variant === 'success'
                  ? 'badge-complete'
                  : 'badge-unavailable'
              }`}
            >
              {badge.text}
            </span>
          )}
        </div>
        <div className="kpi-value tabular">
          {displayValue}
          {unit && (
            <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-muted)', marginLeft: 4 }}>
              {unit}
            </span>
          )}
        </div>
      </div>
      {subtext && <div className="kpi-subtext">{subtext}</div>}
    </div>
  )
}
