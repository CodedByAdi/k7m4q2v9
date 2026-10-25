import React, { useState } from 'react'
import type { DeliveryDaySummary } from '../../api/types'

interface DailyTrendChartProps {
  days: DeliveryDaySummary[]
  selectedDate?: string
  onSelectDate?: (date: string) => void
  height?: number
}

export const DailyTrendChart: React.FC<DailyTrendChartProps> = ({
  days,
  selectedDate,
  onSelectDate,
  height = 280,
}) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  if (!days || days.length === 0) {
    return (
      <div className="state-box">
        <p>No daily performance data available.</p>
      </div>
    )
  }

  const svgWidth = 1000
  const svgHeight = height
  const margin = { top: 20, right: 30, bottom: 40, left: 60 }
  const chartWidth = svgWidth - margin.left - margin.right
  const chartHeight = svgHeight - margin.top - margin.bottom

  // Max MAE for scale
  const maxMae = Math.max(...days.map((d) => d.mae ?? 0), 3000)
  const yMax = Math.ceil((maxMae * 1.15) / 500) * 500

  const getX = (index: number) => {
    return margin.left + (index / (days.length - 1 || 1)) * chartWidth
  }

  const getY = (val: number | null) => {
    if (val === null) return margin.top + chartHeight
    const normalized = Math.max(0, Math.min(1, val / yMax))
    return margin.top + (1 - normalized) * chartHeight
  }

  const activeDay = hoverIndex !== null ? days[hoverIndex] : null

  return (
    <div className="chart-container">
      <div className="chart-legend">
        <div className="legend-item">
          <span
            style={{
              width: 10,
              height: 10,
              backgroundColor: 'var(--brand-forest)',
              borderRadius: 2,
              display: 'inline-block',
            }}
          />
          <span style={{ fontWeight: 600 }}>Daily MAE (MW)</span>
        </div>
        <div className="legend-item">
          <span
            style={{
              width: 8,
              height: 8,
              backgroundColor: '#1d4ed8',
              borderRadius: '50%',
              display: 'inline-block',
            }}
          />
          <span style={{ fontWeight: 600 }}>Signed Bias Indicator (MW)</span>
        </div>
        <div style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-muted)' }}>
          Click any day to open in Forecast Explorer
        </div>
      </div>

      <div style={{ position: 'relative' }}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          style={{ width: '100%', height: 'auto', display: 'block' }}
          onMouseLeave={() => setHoverIndex(null)}
        >
          {/* Y-axis grid */}
          {[0, yMax * 0.33, yMax * 0.66, yMax].map((tick) => {
            const y = getY(tick)
            return (
              <g key={tick}>
                <line
                  x1={margin.left}
                  y1={y}
                  x2={margin.left + chartWidth}
                  y2={y}
                  className="chart-grid-line"
                />
                <text
                  x={margin.left - 8}
                  y={y + 3}
                  textAnchor="end"
                  className="chart-axis-text"
                >
                  {Math.round(tick).toLocaleString()}
                </text>
              </g>
            )
          })}

          {/* Daily MAE Bars */}
          {days.map((d, i) => {
            if (d.mae === null) return null
            const xCenter = getX(i)
            const barWidth = Math.max(14, (chartWidth / days.length) * 0.65)
            const yVal = getY(d.mae)
            const barHeight = margin.top + chartHeight - yVal
            const isSelected = selectedDate === d.delivery_date
            const isHovered = hoverIndex === i

            return (
              <g
                key={`bar-${d.delivery_date}`}
                style={{ cursor: 'pointer' }}
                onClick={() => onSelectDate?.(d.delivery_date)}
              >
                <rect
                  x={xCenter - barWidth / 2}
                  y={yVal}
                  width={barWidth}
                  height={barHeight}
                  fill={
                    isSelected
                      ? 'var(--brand-forest)'
                      : isHovered
                      ? 'var(--brand-forest-light)'
                      : '#c8d6ce'
                  }
                  rx={2}
                  stroke={isSelected ? '#064e3b' : 'transparent'}
                  strokeWidth={isSelected ? 1.5 : 0}
                />
              </g>
            )
          })}

          {/* Signed Bias dots */}
          {days.map((d, i) => {
            if (d.bias === null) return null
            const x = getX(i)
            // Map bias relative to half-height or zero
            const absBiasRatio = Math.min(1, Math.abs(d.bias) / yMax)
            const dotY = margin.top + (1 - absBiasRatio) * chartHeight
            const isOver = d.bias >= 0

            return (
              <circle
                key={`bias-${d.delivery_date}`}
                cx={x}
                cy={dotY}
                r={hoverIndex === i ? 4.5 : 3}
                fill={isOver ? '#2563eb' : '#d97706'}
                stroke="#ffffff"
                strokeWidth={1.5}
                style={{ pointerEvents: 'none' }}
              />
            )
          })}

          {/* X-axis labels */}
          {days.map((d, i) => {
            const x = getX(i)
            const showLabel = i % 4 === 0 || i === days.length - 1
            const dayNum = d.delivery_date.substring(8, 10)
            const monthStr = d.delivery_date.substring(5, 7) === '01' ? 'Jan' : 'Feb'

            return (
              <g key={`x-${d.delivery_date}`}>
                {showLabel && (
                  <text
                    x={x}
                    y={margin.top + chartHeight + 16}
                    textAnchor="middle"
                    className="chart-axis-text"
                  >
                    {dayNum} {monthStr}
                  </text>
                )}
              </g>
            )
          })}

          {/* Hit test areas for hover */}
          {days.map((d, i) => {
            const widthPerItem = chartWidth / days.length
            return (
              <rect
                key={`hit-${d.delivery_date}`}
                x={getX(i) - widthPerItem / 2}
                y={margin.top}
                width={widthPerItem}
                height={chartHeight}
                fill="transparent"
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHoverIndex(i)}
                onClick={() => onSelectDate?.(d.delivery_date)}
              />
            )
          })}
        </svg>

        {/* Tooltip */}
        {activeDay && hoverIndex !== null && (
          <div
            className="chart-tooltip"
            style={{
              left: `${(getX(hoverIndex) / svgWidth) * 100}%`,
              top: `${(getY(activeDay.mae ?? 0) / svgHeight) * 100}%`,
            }}
          >
            <div className="title">Delivery: {activeDay.delivery_date}</div>
            <div className="row">
              <span>Decision Date:</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{activeDay.decision_date}</span>
            </div>
            <div className="row">
              <span>Daily MAE:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                {activeDay.mae !== null ? `${activeDay.mae.toLocaleString()} MW` : '—'}
              </span>
            </div>
            <div className="row">
              <span>Daily RMSE:</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>
                {activeDay.rmse !== null ? `${activeDay.rmse.toLocaleString()} MW` : '—'}
              </span>
            </div>
            <div className="row">
              <span>Signed Bias:</span>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  color: (activeDay.bias ?? 0) >= 0 ? '#93c5fd' : '#fde68a',
                  fontWeight: 600,
                }}
              >
                {(activeDay.bias ?? 0) > 0 ? '+' : ''}
                {activeDay.bias !== null ? `${activeDay.bias.toLocaleString()} MW` : '—'}
              </span>
            </div>
            <div className="row">
              <span>WAPE:</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>
                {activeDay.wape !== null ? `${activeDay.wape}%` : '—'}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
