import React, { useEffect, useRef } from 'react'
import { Terminal, Loader, CheckCircle, XCircle } from 'lucide-react'

export default function ProgressConsole({ logs, status, isAnalyzing }) {
  const consoleRef = useRef(null)

  // Auto-scroll al final
  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight
    }
  }, [logs])

  const getStatusIcon = () => {
    switch (status) {
      case 'completado':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />
      default:
        return <Loader className="w-5 h-5 text-blue-500 animate-spin" />
    }
  }

  const getStatusText = () => {
    switch (status) {
      case 'iniciando':
        return 'Iniciando análisis...'
      case 'conectando':
        return 'Conectando a base de datos...'
      case 'analizando':
        return 'Ejecutando agentes...'
      case 'completado':
        return 'Análisis completado'
      case 'error':
        return 'Error en el análisis'
      default:
        return 'Preparando...'
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case 'completado':
        return 'text-green-400'
      case 'error':
        return 'text-red-400'
      default:
        return 'text-blue-400'
    }
  }

  return (
    <div className="bg-dark-card rounded-lg border border-dark-border overflow-hidden">
      {/* Header */}
      <div className="bg-dark-bg px-4 py-3 border-b border-dark-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-gray-400" />
          <span className="font-medium text-gray-300">Consola de Progreso</span>
        </div>
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <span className={`text-sm font-medium ${getStatusColor()}`}>
            {getStatusText()}
          </span>
        </div>
      </div>

      {/* Console */}
      <div
        ref={consoleRef}
        className="bg-gray-900 p-4 font-mono text-sm h-96 overflow-y-auto"
      >
        {logs.length === 0 ? (
          <div className="text-gray-500 italic">
            Esperando inicio del análisis...
          </div>
        ) : (
          logs.map((log, index) => (
            <LogLine key={index} message={log} index={index} />
          ))
        )}

        {isAnalyzing && (
          <div className="flex items-center gap-2 mt-2 text-blue-400">
            <Loader className="w-4 h-4 animate-spin" />
            <span className="animate-pulse">Procesando...</span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="bg-dark-bg px-4 py-2 border-t border-dark-border">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{logs.length} línea(s)</span>
          <span>Actualización en tiempo real</span>
        </div>
      </div>
    </div>
  )
}

function LogLine({ message, index }) {
  // Colorear según el contenido del mensaje
  const getColorClass = () => {
    if (message.includes('✅') || message.includes('completado') || message.includes('exitosa')) {
      return 'text-green-400'
    }
    if (message.includes('❌') || message.includes('Error') || message.includes('error')) {
      return 'text-red-400'
    }
    if (message.includes('⚙️') || message.includes('Ejecutando') || message.includes('Analizando')) {
      return 'text-blue-400'
    }
    if (message.includes('📊') || message.includes('📝') || message.includes('🔍')) {
      return 'text-yellow-400'
    }
    if (message.includes('🔌')) {
      return 'text-purple-400'
    }
    return 'text-gray-300'
  }

  return (
    <div className="flex gap-2 mb-1">
      <span className="text-gray-600 select-none">{String(index + 1).padStart(3, '0')}</span>
      <span className={getColorClass()}>{message}</span>
    </div>
  )
}
