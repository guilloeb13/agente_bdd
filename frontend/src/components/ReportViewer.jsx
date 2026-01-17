import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { FileText, AlertCircle, TrendingUp, CheckCircle } from 'lucide-react'

export default function ReportViewer({ results }) {
  const [activeTab, setActiveTab] = useState('summary')

  if (!results) {
    return (
      <div className="bg-dark-card rounded-lg border border-dark-border p-8 text-center">
        <FileText className="w-12 h-12 text-gray-500 mx-auto mb-4" />
        <p className="text-gray-400">No hay resultados disponibles</p>
      </div>
    )
  }

  const findings = results.findings || []
  const recommendations = results.recommendations || []

  const criticalCount = findings.filter(f => f.severity === 'critical').length
  const highCount = findings.filter(f => f.severity === 'high').length
  const mediumCount = findings.filter(f => f.severity === 'medium').length
  const lowCount = findings.filter(f => f.severity === 'low').length

  return (
    <div className="bg-dark-card rounded-lg border border-dark-border overflow-hidden">
      {/* Tabs */}
      <div className="bg-dark-bg border-b border-dark-border flex gap-1 px-4">
        <TabButton
          active={activeTab === 'summary'}
          onClick={() => setActiveTab('summary')}
          icon={<TrendingUp className="w-4 h-4" />}
          label="Resumen"
        />
        <TabButton
          active={activeTab === 'findings'}
          onClick={() => setActiveTab('findings')}
          icon={<AlertCircle className="w-4 h-4" />}
          label={`Hallazgos (${findings.length})`}
        />
        <TabButton
          active={activeTab === 'recommendations'}
          onClick={() => setActiveTab('recommendations')}
          icon={<CheckCircle className="w-4 h-4" />}
          label={`Recomendaciones (${recommendations.length})`}
        />
      </div>

      {/* Content */}
      <div className="p-6 max-h-[600px] overflow-y-auto">
        {activeTab === 'summary' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold mb-2">Resumen del Análisis</h2>
              <p className="text-gray-400">
                ID de Auditoría: <code className="bg-dark-bg px-2 py-1 rounded">{results.audit_id}</code>
              </p>
              <p className="text-gray-400">
                Duración: {results.duration_seconds?.toFixed(2)} segundos
              </p>
            </div>

            {/* Severity Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <SeverityCard
                label="Crítico"
                count={criticalCount}
                color="red"
              />
              <SeverityCard
                label="Alto"
                count={highCount}
                color="orange"
              />
              <SeverityCard
                label="Medio"
                count={mediumCount}
                color="yellow"
              />
              <SeverityCard
                label="Bajo"
                count={lowCount}
                color="blue"
              />
            </div>

            {/* Metrics */}
            {results.metrics && (
              <div className="bg-dark-bg rounded-lg p-4">
                <h3 className="font-semibold mb-3">Métricas</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-400">Agentes completados:</span>
                    <span className="ml-2 font-medium">{results.metrics.agents_completed}</span>
                  </div>
                  <div>
                    <span className="text-gray-400">Total de hallazgos:</span>
                    <span className="ml-2 font-medium">{findings.length}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'findings' && (
          <div className="space-y-4">
            <h2 className="text-2xl font-bold mb-4">Hallazgos</h2>

            {findings.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <CheckCircle className="w-12 h-12 mx-auto mb-3 text-green-500" />
                <p>No se encontraron problemas</p>
              </div>
            ) : (
              findings.map((finding, index) => (
                <FindingCard key={index} finding={finding} />
              ))
            )}
          </div>
        )}

        {activeTab === 'recommendations' && (
          <div className="space-y-4">
            <h2 className="text-2xl font-bold mb-4">Recomendaciones</h2>

            {recommendations.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <p>No hay recomendaciones</p>
              </div>
            ) : (
              recommendations
                .sort((a, b) => b.priority - a.priority)
                .map((rec, index) => (
                  <RecommendationCard key={index} recommendation={rec} />
                ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function TabButton({ active, onClick, icon, label }) {
  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-2 px-4 py-3 border-b-2 transition-colors
        ${active
          ? 'border-blue-500 text-blue-400 font-medium'
          : 'border-transparent text-gray-400 hover:text-gray-300'
        }
      `}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}

function SeverityCard({ label, count, color }) {
  const colors = {
    red: 'bg-red-900/20 border-red-800 text-red-400',
    orange: 'bg-orange-900/20 border-orange-800 text-orange-400',
    yellow: 'bg-yellow-900/20 border-yellow-800 text-yellow-400',
    blue: 'bg-blue-900/20 border-blue-800 text-blue-400'
  }

  return (
    <div className={`rounded-lg border p-4 ${colors[color]}`}>
      <div className="text-2xl font-bold">{count}</div>
      <div className="text-sm opacity-80">{label}</div>
    </div>
  )
}

function FindingCard({ finding }) {
  const severityColors = {
    critical: 'bg-red-900/20 border-red-800 text-red-400',
    high: 'bg-orange-900/20 border-orange-800 text-orange-400',
    medium: 'bg-yellow-900/20 border-yellow-800 text-yellow-400',
    low: 'bg-blue-900/20 border-blue-800 text-blue-400',
    info: 'bg-gray-900/20 border-gray-800 text-gray-400'
  }

  return (
    <div className={`rounded-lg border p-4 ${severityColors[finding.severity]}`}>
      <div className="flex items-start justify-between gap-4 mb-2">
        <h3 className="font-semibold text-white">{finding.title}</h3>
        <span className="text-xs uppercase font-medium px-2 py-1 rounded bg-dark-bg">
          {finding.severity}
        </span>
      </div>

      <p className="text-sm opacity-90 mb-2">{finding.description}</p>

      {finding.affected_objects && finding.affected_objects.length > 0 && (
        <div className="text-xs opacity-75 mb-2">
          <strong>Afectados:</strong> {finding.affected_objects.join(', ')}
        </div>
      )}

      {finding.remediation && (
        <div className="mt-3 pt-3 border-t border-current/20">
          <strong className="text-xs">Remediación:</strong>
          <p className="text-sm mt-1 opacity-90">{finding.remediation}</p>
        </div>
      )}
    </div>
  )
}

function RecommendationCard({ recommendation }) {
  return (
    <div className="bg-dark-bg rounded-lg border border-dark-border p-4">
      <div className="flex items-start justify-between gap-4 mb-2">
        <h3 className="font-semibold text-white">{recommendation.title}</h3>
        <div className="flex items-center gap-2">
          <span className="text-xs bg-blue-900/30 text-blue-400 px-2 py-1 rounded">
            Prioridad: {recommendation.priority}/10
          </span>
        </div>
      </div>

      <p className="text-sm text-gray-400 mb-3">{recommendation.description}</p>

      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
        <div>
          <span className="text-gray-500">Esfuerzo:</span>
          <span className="ml-2 text-gray-300">{recommendation.effort}</span>
        </div>
        <div>
          <span className="text-gray-500">Impacto:</span>
          <span className="ml-2 text-gray-300">{recommendation.impact}</span>
        </div>
      </div>

      {recommendation.implementation && (
        <div className="mt-3 pt-3 border-t border-dark-border">
          <strong className="text-xs text-gray-400">Implementación:</strong>
          <pre className="text-xs mt-2 p-2 bg-gray-900 rounded overflow-x-auto">
            <code className="text-green-400">{recommendation.implementation}</code>
          </pre>
        </div>
      )}
    </div>
  )
}
