import React from 'react'
import { Download } from 'lucide-react'
import { apiClient } from '../api/client'

interface ContextBarProps {
  cutoff: string
  totalDays: number
}

export const ContextBar: React.FC<ContextBarProps> = ({ cutoff, totalDays }) => {
  const exportUrl = apiClient.getExportCsvUrl(cutoff)

  return (
    <aside className="context-bar" aria-label="Dataset Context and Summary">
      <div className="context-info">
        <div className="context-pill">
          <span className="label">Evaluation Scope:</span>
          <span className="value">January 2026 Historical Benchmark</span>
        </div>

        <div className="context-pill">
          <span className="label">Decision Window:</span>
          <span className="value">2026-01-01 – 2026-01-31</span>
        </div>

        <div className="context-pill">
          <span className="label">Delivery Window:</span>
          <span className="value">2026-01-02 – 2026-02-01 ({totalDays} days)</span>
        </div>

        <div className="context-pill">
          <span className="label">Resolution:</span>
          <span className="value">Hourly Series (HH Averaged)</span>
        </div>
      </div>

      <div>
        <a
          href={exportUrl}
          download={`windline_january_2026_cutoff_${cutoff.replace(':', '')}.csv`}
          className="btn btn-secondary btn-sm"
          title="Export complete 744-interval hourly comparison table as CSV"
        >
          <Download size={13} />
          <span>Export Full-Window CSV</span>
        </a>
      </div>
    </aside>
  )
}
