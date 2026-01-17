import React, { useState } from 'react'
import { Database, Loader, CheckCircle, XCircle } from 'lucide-react'

export default function ConnectionForm({ onTestConnection, isConnecting }) {
  const [config, setConfig] = useState({
    host: 'localhost',
    port: 5432,
    database: '',
    user: 'postgres',
    password: ''
  })

  const [connectionResult, setConnectionResult] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setConnectionResult(null)

    const result = await onTestConnection(config)

    if (result) {
      setConnectionResult(result)
    }
  }

  const handleChange = (field, value) => {
    setConfig(prev => ({ ...prev, [field]: value }))
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-dark-card rounded-lg border border-dark-border overflow-hidden">
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Database className="w-6 h-6" />
            Configurar Conexión
          </h2>
          <p className="text-blue-100 text-sm mt-1">
            Ingrese los datos de conexión a la base de datos PostgreSQL
          </p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Host
              </label>
              <input
                type="text"
                value={config.host}
                onChange={(e) => handleChange('host', e.target.value)}
                className="w-full px-4 py-2 bg-dark-bg border border-dark-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="localhost"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Puerto
              </label>
              <input
                type="number"
                value={config.port}
                onChange={(e) => handleChange('port', parseInt(e.target.value))}
                className="w-full px-4 py-2 bg-dark-bg border border-dark-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="5432"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Base de Datos
            </label>
            <input
              type="text"
              value={config.database}
              onChange={(e) => handleChange('database', e.target.value)}
              className="w-full px-4 py-2 bg-dark-bg border border-dark-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="nombre_database"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Usuario
            </label>
            <input
              type="text"
              value={config.user}
              onChange={(e) => handleChange('user', e.target.value)}
              className="w-full px-4 py-2 bg-dark-bg border border-dark-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="postgres"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Contraseña
            </label>
            <input
              type="password"
              value={config.password}
              onChange={(e) => handleChange('password', e.target.value)}
              className="w-full px-4 py-2 bg-dark-bg border border-dark-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="••••••••"
            />
          </div>

          {/* Connection Result */}
          {connectionResult && (
            <div
              className={`p-4 rounded-lg flex items-start gap-3 ${
                connectionResult.success
                  ? 'bg-green-900/20 border border-green-800'
                  : 'bg-red-900/20 border border-red-800'
              }`}
            >
              {connectionResult.success ? (
                <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
              ) : (
                <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              )}
              <div className="flex-1">
                <h4
                  className={`font-semibold ${
                    connectionResult.success ? 'text-green-300' : 'text-red-300'
                  }`}
                >
                  {connectionResult.success ? 'Conexión Exitosa' : 'Error de Conexión'}
                </h4>
                {connectionResult.success && connectionResult.data && (
                  <div className="text-sm text-gray-300 mt-2 space-y-1">
                    <p>Base de datos: {connectionResult.data.database}</p>
                    <p>Versión: {connectionResult.data.version}</p>
                    <p>
                      Tamaño: {(connectionResult.data.size_bytes / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                )}
                {connectionResult.error && (
                  <p className="text-sm text-red-300 mt-1">{connectionResult.error}</p>
                )}
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={isConnecting || !config.database}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-medium py-3 px-6 rounded-lg flex items-center justify-center gap-2 transition-colors"
          >
            {isConnecting ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Conectando...
              </>
            ) : (
              <>
                <Database className="w-5 h-5" />
                Probar Conexión
              </>
            )}
          </button>
        </form>
      </div>

      <div className="mt-4 p-4 bg-blue-900/20 border border-blue-800 rounded-lg">
        <p className="text-sm text-blue-300">
          <strong>💡 Nota:</strong> La conexión se probará de forma segura sin realizar cambios en la base de datos.
        </p>
      </div>
    </div>
  )
}
