import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { Database, Play, Download, CheckCircle, XCircle, Loader } from 'lucide-react'
import ConnectionForm from './components/ConnectionForm'
import AgentSelector from './components/AgentSelector'
import ProgressConsole from './components/ProgressConsole'
import ReportViewer from './components/ReportViewer'

const API_BASE = '/api'

function App() {
  const [step, setStep] = useState('connection') // connection, analyze, results
  const [connectionConfig, setConnectionConfig] = useState(null)
  const [selectedAgents, setSelectedAgents] = useState([])
  const [auditId, setAuditId] = useState(null)
  const [auditStatus, setAuditStatus] = useState(null)
  const [logs, setLogs] = useState([])
  const [results, setResults] = useState(null)
  const [isConnecting, setIsConnecting] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  // Conectar al WebSocket cuando tengamos un auditId
  useEffect(() => {
    if (!auditId) return

    const ws = new WebSocket(`ws://localhost:8000/ws/${auditId}`)

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'log') {
        setLogs(prev => [...prev, data.message])
      } else if (data.type === 'status') {
        setAuditStatus(data.status)
      }
    }

    ws.onerror = () => {
      console.log('WebSocket error, falling back to polling')
      // Fallback a polling si WebSocket falla
      startPolling()
    }

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close()
      }
    }
  }, [auditId])

  // Polling de respaldo
  const startPolling = () => {
    const interval = setInterval(async () => {
      if (!auditId) {
        clearInterval(interval)
        return
      }

      try {
        const response = await axios.get(`${API_BASE}/status/${auditId}`)
        const status = response.data

        setAuditStatus(status.status)

        if (status.progress && status.progress.logs) {
          setLogs(status.progress.logs.map(l => l.message))
        }

        if (status.status === 'completado' || status.status === 'error') {
          clearInterval(interval)
          setIsAnalyzing(false)

          if (status.status === 'completado') {
            loadResults()
          }
        }
      } catch (error) {
        console.error('Error polling status:', error)
      }
    }, 2000)

    return () => clearInterval(interval)
  }

  const handleTestConnection = async (config) => {
    setIsConnecting(true)
    try {
      const response = await axios.post(`${API_BASE}/connect`, {
        connection: config
      })

      if (response.data.success) {
        setConnectionConfig(config)
        setStep('analyze')
        return { success: true, data: response.data.info }
      }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Error al conectar'
      }
    } finally {
      setIsConnecting(false)
    }
  }

  const handleStartAnalysis = async (schemas) => {
    setIsAnalyzing(true)
    setLogs([])

    try {
      const response = await axios.post(`${API_BASE}/analyze`, {
        connection: connectionConfig,
        schemas: schemas,
        agents: selectedAgents
      })

      setAuditId(response.data.audit_id)
      setStep('results')
    } catch (error) {
      console.error('Error starting analysis:', error)
      setIsAnalyzing(false)
      alert('Error al iniciar análisis: ' + (error.response?.data?.detail || error.message))
    }
  }

  const loadResults = async () => {
    try {
      const response = await axios.get(`${API_BASE}/results/${auditId}`)
      setResults(response.data)
    } catch (error) {
      console.error('Error loading results:', error)
    }
  }

  const handleDownload = async (format) => {
    try {
      const response = await axios.get(`${API_BASE}/download/${auditId}/${format}`, {
        responseType: 'blob'
      })

      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url

      const extensions = { markdown: 'md', html: 'html', json: 'json' }
      link.setAttribute('download', `reporte_pma_${auditId}.${extensions[format]}`)

      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (error) {
      console.error('Error downloading report:', error)
      alert('Error al descargar reporte')
    }
  }

  const handleReset = () => {
    setStep('connection')
    setConnectionConfig(null)
    setAuditId(null)
    setAuditStatus(null)
    setLogs([])
    setResults(null)
    setIsAnalyzing(false)
  }

  return (
    <div className="min-h-screen bg-dark-bg">
      {/* Header */}
      <header className="bg-dark-card border-b border-dark-border">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center gap-3">
            <Database className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="text-2xl font-bold text-white">PMA-Agent</h1>
              <p className="text-sm text-gray-400">Analizador Multi-Agente de PostgreSQL</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-8">
        {/* Steps Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-center gap-4">
            <StepIndicator
              number={1}
              label="Conexión"
              active={step === 'connection'}
              completed={step !== 'connection'}
            />
            <div className="w-16 h-0.5 bg-dark-border"></div>
            <StepIndicator
              number={2}
              label="Análisis"
              active={step === 'analyze'}
              completed={step === 'results'}
            />
            <div className="w-16 h-0.5 bg-dark-border"></div>
            <StepIndicator
              number={3}
              label="Resultados"
              active={step === 'results'}
              completed={false}
            />
          </div>
        </div>

        {/* Content Based on Step */}
        {step === 'connection' && (
          <ConnectionForm
            onTestConnection={handleTestConnection}
            isConnecting={isConnecting}
          />
        )}

        {step === 'analyze' && (
          <div className="max-w-4xl mx-auto space-y-6">
            <AgentSelector
              selected={selectedAgents}
              onChange={setSelectedAgents}
            />

            <div className="bg-dark-card rounded-lg border border-dark-border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Database className="w-5 h-5 text-blue-500" />
                Configurar Análisis
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Esquemas a Analizar
                  </label>
                  <input
                    type="text"
                    placeholder="public, app (separados por coma)"
                    defaultValue="public"
                    id="schemas-input"
                    className="w-full px-4 py-2 bg-dark-bg border border-dark-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Ingrese los nombres de los esquemas separados por comas
                  </p>
                </div>

                <button
                  onClick={() => {
                    const schemasInput = document.getElementById('schemas-input').value
                    const schemas = schemasInput.split(',').map(s => s.trim()).filter(Boolean)
                    handleStartAnalysis(schemas)
                  }}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-6 rounded-lg flex items-center justify-center gap-2 transition-colors"
                >
                  <Play className="w-5 h-5" />
                  Ejecutar Auditoría
                </button>
              </div>
            </div>
          </div>
        )}

        {step === 'results' && (
          <div className="space-y-6">
            {/* Progress Console */}
            <ProgressConsole
              logs={logs}
              status={auditStatus}
              isAnalyzing={isAnalyzing}
            />

            {/* Action Buttons */}
            {auditStatus === 'completado' && (
              <div className="bg-dark-card rounded-lg border border-dark-border p-6">
                <h3 className="text-lg font-semibold mb-4">Descargar Reportes</h3>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={() => handleDownload('markdown')}
                    className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Markdown (.md)
                  </button>
                  <button
                    onClick={() => handleDownload('html')}
                    className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    HTML (.html)
                  </button>
                  <button
                    onClick={() => handleDownload('json')}
                    className="flex items-center gap-2 bg-orange-600 hover:bg-orange-700 text-white px-4 py-2 rounded-lg transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    JSON (.json)
                  </button>
                  <button
                    onClick={handleReset}
                    className="flex items-center gap-2 bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-lg transition-colors ml-auto"
                  >
                    Nuevo Análisis
                  </button>
                </div>
              </div>
            )}

            {/* Report Viewer */}
            {results && (
              <ReportViewer results={results} />
            )}
          </div>
        )}
      </main>
    </div>
  )
}

function StepIndicator({ number, label, active, completed }) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className={`
          w-10 h-10 rounded-full flex items-center justify-center font-semibold
          ${active ? 'bg-blue-600 text-white' : ''}
          ${completed ? 'bg-green-600 text-white' : ''}
          ${!active && !completed ? 'bg-dark-border text-gray-400' : ''}
        `}
      >
        {completed ? <CheckCircle className="w-6 h-6" /> : number}
      </div>
      <span className={`text-sm ${active ? 'text-white font-medium' : 'text-gray-400'}`}>
        {label}
      </span>
    </div>
  )
}

export default App
