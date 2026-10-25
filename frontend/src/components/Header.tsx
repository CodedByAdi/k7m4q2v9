import React from 'react'
import {
  Activity,
  BarChart3,
  Calendar,
  Compass,
  FileText,
  ShieldCheck,
} from 'lucide-react'

export type NavTab = 'overview' | 'explorer' | 'accuracy' | 'quality' | 'methodology'

interface HeaderProps {
  activeTab: NavTab
  onSelectTab: (tab: NavTab) => void
  cutoff: string
  onChangeCutoff: (cutoff: string) => void
  isOnline: boolean
}

const CUTOFF_OPTIONS = [
  { value: '07:00', label: '07:00 Europe/London' },
  { value: '08:00', label: '08:00 Europe/London' },
  { value: '09:00', label: '09:00 Europe/London (Default)' },
  { value: '10:00', label: '10:00 Europe/London' },
  { value: '11:00', label: '11:00 Europe/London' },
  { value: '12:00', label: '12:00 Europe/London' },
]

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onSelectTab,
  cutoff,
  onChangeCutoff,
  isOnline,
}) => {
  return (
    <header className="top-nav" role="banner">
      <div className="brand-section">
        <div className="brand-title">
          <Activity size={18} className="text-emerald-400" />
          <span>Windline</span>
        </div>
      </div>

      <nav className="nav-links" aria-label="Main Navigation">
        <button
          type="button"
          className={`nav-item ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => onSelectTab('overview')}
        >
          <BarChart3 size={15} />
          <span>Overview</span>
        </button>

        <button
          type="button"
          className={`nav-item ${activeTab === 'explorer' ? 'active' : ''}`}
          onClick={() => onSelectTab('explorer')}
        >
          <Compass size={15} />
          <span>Forecast Explorer</span>
        </button>

        <button
          type="button"
          className={`nav-item ${activeTab === 'accuracy' ? 'active' : ''}`}
          onClick={() => onSelectTab('accuracy')}
        >
          <Calendar size={15} />
          <span>Accuracy Analysis</span>
        </button>

        <button
          type="button"
          className={`nav-item ${activeTab === 'quality' ? 'active' : ''}`}
          onClick={() => onSelectTab('quality')}
        >
          <ShieldCheck size={15} />
          <span>Data Quality</span>
        </button>

        <button
          type="button"
          className={`nav-item ${activeTab === 'methodology' ? 'active' : ''}`}
          onClick={() => onSelectTab('methodology')}
        >
          <FileText size={15} />
          <span>Methodology</span>
        </button>
      </nav>

      <div className="top-controls">
        <div className="cutoff-selector">
          <label htmlFor="cutoff-select">Decision cutoff:</label>
          <select
            id="cutoff-select"
            value={cutoff}
            onChange={(e) => onChangeCutoff(e.target.value)}
            aria-label="Select decision cutoff time"
          >
            {CUTOFF_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1 text-xs" title={isOnline ? 'Backend Online' : 'Backend Connecting...'}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              backgroundColor: isOnline ? '#10b981' : '#f59e0b',
              display: 'inline-block',
            }}
          />
          <span style={{ color: '#d1dbd5', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
            {isOnline ? 'ELEXON-BMRS' : 'CONNECTING'}
          </span>
        </div>
      </div>
    </header>
  )
}
