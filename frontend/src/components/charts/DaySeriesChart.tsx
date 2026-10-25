import React, { useState } from 'react'
import type { HourlyIntervalComparison } from '../../api/types'

interface DaySeriesChartProps {
  intervals: HourlyIntervalComparison[]
  height?: number
}

export const DaySeriesChart: React.FC<DaySeriesChartProps> = ({
  intervals,
  height = 360,
}) => {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  if (!intervals || intervals.length === 0) {
    return (
      <div className="state-box">
        <p>No hourly interval data available for chart rendering.</p>
      </div>
    )
  }

  // Dimensions
  const svgWidth = 1000
  const svgHeight = height
  const margin = { top: 20, right: 30, bottom: 40, left: 60 }
  const chartWidth = svgWidth - margin.left - margin.right
  const chartHeight = svgHeight - margin.top - margin.bottom

  // Find max generation for scale
  const allValues: number[] = []
  intervals.forEach((i) => {
    if (i.forecast_mw !== null) allValues.push(i.forecast_mw)
    if (i.actual_mw !== null) allValues.push(i.actual_mw)
  })

  const rawMax = allValues.length > 0 ? Math.max(...allValues) : 10000
  // Round up to clean thousand
  const yMax = Math.ceil((rawMax * 1.1) / 1000) * 1000
  const yMin = 0

  // Coordinates mapping
  const getX = (index: number) => {
    return margin.left + (index / (intervals.length - 1)) * chartWidth
  }

  const getY = (val: number | null) => {
    if (val === null) return chartHeight + margin.top
    const normalized = (val - yMin) / (yMax - yMin)
    return margin.top + (1 - normalized) * chartHeight
  }

  // Generate paths
  const forecastPoints = intervals
    .map((d, i) => (d.forecast_mw !== null ? `${getX(i)},${getY(d.forecast_mw)}` : null))
    .filter(Boolean)
  const forecastPath = forecastPoints.length > 0 ? `M ${forecastPoints.join(' L ')}` : ''

  const actualPoints = intervals
    .map((d, i) => (d.actual_mw !== null ? `${getX(i)},${getY(d.actual_mw)}` : null))
    .filter(Boolean)
  const actualPath = actualPoints.length > 0 ? `M ${actualPoints.join(' L ')}` : ''

  // Area path for actuals
  let actualAreaPath = ''
  if (actualPoints.length > 0) {
    const firstX = getX(0)
    const lastX = getX(intervals.length - 1)
    const bottomY = margin.top + chartHeight
    actualAreaPath = `M ${firstX},${bottomY} L ${actualPoints.join(' L ')} L ${lastX},${bottomY} Z`
  }

  // Y-axis ticks
  const yTicks = [0, yMax * 0.25, yMax * 0.5, yMax * 0.75, yMax]

  // Hover data
  const activeInterval = hoverIndex !== null ? intervals[hoverIndex] : null

  return (
    <div className="chart-container">
      <div className="chart-legend">
        <div className="legend-item">
          <span className="legend-indicator forecast" />
          <span style={{ fontWeight: 600, color: 'var(--series-forecast)' }}>
            WINDFOR Forecast (MW)
          </span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator actual" />
          <span style={{ fontWeight: 600, color: 'var(--series-actual)' }}>
            FUELHH Actual Hourly Mean (MW)
          </span>
        </div>
        <div style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          24 Hourly Intervals (UTC)
        </div>
      </div>

      <div style={{ position: 'relative' }}>
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          style={{ width: '100%', height: 'auto', overflow: 'visible', display: 'block' }}
          onMouseLeave={() => setHoverIndex(null)}
        >
          {/* Y Grid lines and labels */}
          {yTicks.map((tick) => {
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

          {/* Area under actuals */}
          {actualAreaPath && <path d={actualAreaPath} className="chart-actual-area" />}

          {/* Actual line */}
          {actualPath && <path d={actualPath} className="chart-actual-path" />}

          {/* Forecast line */}
          {forecastPath && <path d={forecastPath} className="chart-forecast-path" />}

          {/* Points for actuals */}
          {intervals.map((d, i) => {
            if (d.actual_mw === null) return null
            return (
              <circle
                key={`act-${i}`}
                cx={getX(i)}
                cy={getY(d.actual_mw)}
                r={hoverIndex === i ? 4 : 2.5}
                fill="#ffffff"
                stroke="var(--series-actual)"
                strokeWidth={hoverIndex === i ? 2.5 : 1.5}
              />
            )
          })}

          {/* Points for forecasts */}
          {intervals.map((d, i) => {
            if (d.forecast_mw === null) return null
            return (
              <circle
                key={`fc-${i}`}
                cx={getX(i)}
                cy={getY(d.forecast_mw)}
                r={hoverIndex === i ? 4 : 2.5}
                fill="#ffffff"
                stroke="var(--series-forecast)"
                strokeWidth={hoverIndex === i ? 2.5 : 1.5}
              />
            )
          })}

          {/* X Axis ticks & labels (every 2 or 3 hours) */}
          {intervals.map((d, i) => {
            const x = getX(i)
            const showLabel = i % 3 === 0 || i === intervals.length - 1
            const timeLabel = d.startTime.substring(11, 16)
            return (
              <g key={`x-${i}`}>
                <line
                  x1={x}
                  y1={margin.top + chartHeight}
                  x2={x}
                  y2={margin.top + chartHeight + 4}
                  stroke="var(--border-medium)"
                />
                {showLabel && (
                  <text
                    x={x}
                    y={margin.top + chartHeight + 18}
                    textAnchor="middle"
                    className="chart-axis-text"
                  >
                    {timeLabel}
                  </text>
                )}
              </g>
            )
          })}

          {/* Hover Crosshair line */}
          {hoverIndex !== null && (
            <line
              x1={getX(hoverIndex)}
              y1={margin.top}
              x2={getX(hoverIndex)}
              y2={margin.top + chartHeight}
              className="chart-hover-line"
            />
          )}

          {/* Interactive touch/mouse overlay rectangles */}
          {intervals.map((_, i) => {
            const widthPerItem = chartWidth / intervals.length
            return (
              <rect
                key={`hit-${i}`}
                x={getX(i) - widthPerItem / 2}
                y={margin.top}
                width={widthPerItem}
                height={chartHeight}
                fill="transparent"
                style={{ cursor: 'crosshair' }}
                onMouseEnter={() => setHoverIndex(i)}
              />
            )
          })}
        </svg>

        {/* Floating Tooltip */}
        {activeInterval && hoverIndex !== null && (
          <div
            className="chart-tooltip"
            style={{
              left: `${(getX(hoverIndex) / svgWidth) * 100}%`,
              top: `${(getY(activeInterval.actual_mw ?? activeInterval.forecast_mw ?? 0) / svgHeight) * 100}%`,
            }}
          >
            <div className="title">
              {String(hoverIndex).padStart(2, '0')}:00–{String((hoverIndex + 1) % 24).padStart(2, '0')}:00 UTC (SP {hoverIndex * 2 + 1} &amp; SP {hoverIndex * 2 + 2})
            </div>
            <div className="row">
              <span style={{ color: '#93c5fd' }}>WINDFOR Forecast:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                {activeInterval.forecast_mw !== null ? `${Math.round(activeInterval.forecast_mw).toLocaleString()} MW` : 'Missing'}
              </span>
            </div>
            <div className="row">
              <span style={{ color: '#6ee7b7' }}>Actual Hourly Mean:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                {activeInterval.actual_mw !== null ? `${Math.round(activeInterval.actual_mw).toLocaleString()} MW` : 'Missing'}
              </span>
            </div>
            {activeInterval.signed_error_mw !== null && (
              <div className="row" style={{ borderTop: '1px solid rgba(255,255,255,0.15)', paddingTop: 4, marginTop: 4 }}>
                <span style={{ color: activeInterval.signed_error_mw > 0 ? '#60a5fa' : '#fbbf24' }}>
                  {activeInterval.signed_error_mw > 0 ? 'Overforecast (+):' : 'Underforecast (-):'}
                </span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                  {activeInterval.signed_error_mw > 0 ? '+' : ''}
                  {Math.round(activeInterval.signed_error_mw).toLocaleString()} MW
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
