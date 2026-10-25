import React, { useEffect, useState } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { apiClient } from './api/client'
import type { MetadataResponse, OverviewResponse } from './api/types'
import { ContextBar } from './components/ContextBar'
import { Header, type NavTab } from './components/Header'
import { AccuracyView } from './views/AccuracyView'
import { ExplorerView } from './views/ExplorerView'
import { MethodologyView } from './views/MethodologyView'
import { OverviewView } from './views/OverviewView'
import { QualityView } from './views/QualityView'

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>('overview')
  const [cutoff, setCutoff] = useState<string>('09:00')
  const [selectedDate, setSelectedDate] = useState<string>('2026-01-02')

  const [overview, setOverview] = useState<OverviewResponse | null>(null)
  const [metadata, setMetadata] = useState<MetadataResponse | null>(null)
  const [availableDates, setAvailableDates] = useState<string[]>([])

  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [isOnline, setIsOnline] = useState<boolean>(false)

  // Primary data fetch on mount and when cutoff gate changes
  const loadData = async (targetCutoff: string) => {
    setLoading(true)
    setError(null)
    try {
      // 1. Health check
      const health = await apiClient.getHealth()
      if (health.status === 'healthy') {
        setIsOnline(true)
      }

      // 2. Metadata (static reference parameters)
      const meta = await apiClient.getMetadata()
      setMetadata(meta)

      // 3. Overview data at target cutoff
      const overviewData = await apiClient.getOverview(targetCutoff)
      setOverview(overviewData)

      const dates = overviewData.daily_summaries.map((d) => d.delivery_date)
      setAvailableDates(dates)

      // Ensure selectedDate is valid within available dates
      if (!dates.includes(selectedDate) && dates.length > 0) {
        setSelectedDate(dates[0])
      }

      setLoading(false)
    } catch (err: any) {
      console.error('Failed to load Windline overview:', err)
      setError(
        err.message ||
          'Failed to connect to Windline backend service at http://127.0.0.1:8000. Ensure the FastAPI service is running.'
      )
      setIsOnline(false)
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData(cutoff)
  }, [cutoff])

  const handleCutoffChange = (newCutoff: string) => {
    setCutoff(newCutoff)
  }

  const handleSelectDateAndExplore = (date: string) => {
    setSelectedDate(date)
    setActiveTab('explorer')
  }

  return (
    <div className="app-container">
      {/* Top Application Header */}
      <Header
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        cutoff={cutoff}
        onChangeCutoff={handleCutoffChange}
        isOnline={isOnline}
      />

      {/* Dataset Scope & Export Context Bar */}
      <ContextBar cutoff={cutoff} totalDays={availableDates.length || 31} />

      {/* Main Content Area */}
      <main className="main-content" id="main-content" role="main">
        {loading && (
          <div className="state-box" style={{ minHeight: 400 }}>
            <div className="spinner" />
            <p style={{ marginTop: 16, fontSize: '14px', color: 'var(--text-secondary)' }}>
              Loading Windline analysis engine ({cutoff} Europe/London gate)...
            </p>
          </div>
        )}

        {!loading && error && (
          <div
            className="state-box"
            style={{
              minHeight: 400,
              color: 'var(--status-large-miss)',
              backgroundColor: '#fff',
              border: '1px solid var(--border-medium)',
              borderRadius: 4,
            }}
          >
            <AlertTriangle size={36} />
            <h2 style={{ fontSize: '18px', margin: '12px 0 6px', color: 'var(--text-primary)' }}>
              Backend Connection Error
            </h2>
            <p style={{ maxWidth: 500, fontSize: '13px', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
              {error}
            </p>
            <button
              type="button"
              className="btn btn-primary"
              style={{ marginTop: 16 }}
              onClick={() => loadData(cutoff)}
            >
              <RefreshCw size={14} />
              <span>Retry Connection</span>
            </button>
          </div>
        )}

        {!loading && !error && overview && (
          <>
            {activeTab === 'overview' && (
              <OverviewView
                overview={overview}
                onSelectDeliveryDate={setSelectedDate}
                onNavigateToExplorer={() => setActiveTab('explorer')}
              />
            )}

            {activeTab === 'explorer' && (
              <ExplorerView
                availableDates={availableDates}
                selectedDate={selectedDate}
                cutoff={cutoff}
                onSelectDate={setSelectedDate}
              />
            )}

            {activeTab === 'accuracy' && (
              <AccuracyView
                metrics={overview.overall_metrics}
                days={overview.daily_summaries}
                onSelectDeliveryDate={(date) => handleSelectDateAndExplore(date)}
                onNavigateToExplorer={() => setActiveTab('explorer')}
              />
            )}

            {activeTab === 'quality' && (
              <QualityView
                overview={overview}
                metadata={metadata}
                onSelectDeliveryDate={(date) => handleSelectDateAndExplore(date)}
                onNavigateToExplorer={() => setActiveTab('explorer')}
              />
            )}

            {activeTab === 'methodology' && (
              <MethodologyView metadata={metadata} cutoff={cutoff} />
            )}
          </>
        )}
      </main>

      {/* Footer */}
      <footer
        style={{
          borderTop: '1px solid var(--border-light)',
          padding: '24px 32px',
          backgroundColor: '#ffffff',
          color: 'var(--text-muted)',
          fontSize: '11.5px',
          lineHeight: 1.6,
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 16,
        }}
      >
        <div>
          <span style={{ fontWeight: 600, color: 'var(--brand-forest)' }}>WINDLINE</span> — GB Wind Forecast Desk &copy; 2026.
          Contains BMRS data &copy; Elexon Limited copyright and database right 2026. Sourced under the{' '}
          <a
            href="https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/"
            target="_blank"
            rel="noreferrer"
            style={{ color: 'var(--brand-forest)', textDecoration: 'underline' }}
          >
            BMRS Open Data Licence
          </a>
          . Elexon does not endorse Windline.
        </div>
        <div style={{ fontFamily: 'var(--font-mono)' }}>
          All times UTC unless explicitly specified as Europe/London. Zero imputation policy enforced.
        </div>
      </footer>
    </div>
  )
}

export default App
