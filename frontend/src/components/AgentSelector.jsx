import React from 'react'
import { Shield, Database, Link, Search, Layers, Zap, List, BarChart, AlertTriangle, FileCode, CheckSquare } from 'lucide-react'

const AGENTS = [
  {
    id: 'security',
    name: 'Agente de Seguridad',
    description: 'Analiza roles, permisos y vulnerabilidades (OWASP/CIS)',
    icon: Shield,
    color: 'text-red-500'
  },
  {
    id: 'schema',
    name: 'Agente de Esquema',
    description: 'Revisa estructuras de tablas, tipos y convenciones',
    icon: Database,
    color: 'text-blue-500'
  },
  {
    id: 'integrity',
    name: 'Agente de Integridad',
    description: 'Detecta FKs faltantes y problemas de relaciones',
    icon: Link,
    color: 'text-green-500'
  },
  {
    id: 'orphan',
    name: 'Agente de Huérfanos',
    description: 'Encuentra datos huérfanos y jerarquías rotas',
    icon: Search,
    color: 'text-yellow-500'
  },
  {
    id: 'normalization',
    name: 'Agente de Normalización',
    description: 'Verifica cumplimiento de 1NF, 2NF, 3NF, BCNF',
    icon: Layers,
    color: 'text-purple-500'
  },
  {
    id: 'performance',
    name: 'Agente de Rendimiento',
    description: 'Analiza scans secuenciales, bloat y cache',
    icon: Zap,
    color: 'text-orange-500'
  },
  {
    id: 'indexing',
    name: 'Agente de Índices',
    description: 'Recomienda índices B-Tree, GIN, GiST',
    icon: List,
    color: 'text-cyan-500'
  },
  {
    id: 'quality',
    name: 'Agente de Calidad de Datos',
    description: 'Detecta duplicados, NULLs y baja cardinalidad',
    icon: BarChart,
    color: 'text-pink-500'
  },
  {
    id: 'anomaly',
    name: 'Agente de Anomalías',
    description: 'Encuentra outliers y anomalías temporales',
    icon: AlertTriangle,
    color: 'text-amber-500'
  },
  {
    id: 'ddl',
    name: 'Agente de DDL',
    description: 'Reconstruye DDL completo del catálogo',
    icon: FileCode,
    color: 'text-indigo-500'
  },
  {
    id: 'recommendation',
    name: 'Agente de Recomendaciones',
    description: 'Consolida hallazgos en plan de acción',
    icon: CheckSquare,
    color: 'text-emerald-500'
  }
]

export default function AgentSelector({ selected, onChange }) {
  const isSelected = (agentId) => selected.includes(agentId)

  const toggleAgent = (agentId) => {
    if (isSelected(agentId)) {
      onChange(selected.filter(id => id !== agentId))
    } else {
      onChange([...selected, agentId])
    }
  }

  const selectAll = () => {
    onChange(AGENTS.map(a => a.id))
  }

  const selectNone = () => {
    onChange([])
  }

  return (
    <div className="bg-dark-card rounded-lg border border-dark-border p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold">Seleccionar Agentes</h3>
          <p className="text-sm text-gray-400 mt-1">
            {selected.length === 0
              ? 'Se ejecutarán todos los agentes'
              : `${selected.length} agente(s) seleccionado(s)`}
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={selectAll}
            className="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
          >
            Todos
          </button>
          <button
            onClick={selectNone}
            className="px-3 py-1 text-sm bg-gray-600 hover:bg-gray-700 text-white rounded transition-colors"
          >
            Ninguno
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {AGENTS.map((agent) => {
          const Icon = agent.icon
          const selected = isSelected(agent.id)

          return (
            <div
              key={agent.id}
              onClick={() => toggleAgent(agent.id)}
              className={`
                p-4 rounded-lg border-2 cursor-pointer transition-all
                ${selected
                  ? 'border-blue-500 bg-blue-900/20'
                  : 'border-dark-border hover:border-gray-600 bg-dark-bg'
                }
              `}
            >
              <div className="flex items-start gap-3">
                <Icon className={`w-5 h-5 flex-shrink-0 ${agent.color}`} />
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium text-sm text-white mb-1">
                    {agent.name}
                  </h4>
                  <p className="text-xs text-gray-400 leading-tight">
                    {agent.description}
                  </p>
                </div>
                <div
                  className={`
                    w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0
                    ${selected
                      ? 'bg-blue-600 border-blue-600'
                      : 'border-gray-600'
                    }
                  `}
                >
                  {selected && (
                    <svg
                      className="w-3 h-3 text-white"
                      fill="none"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path d="M5 13l4 4L19 7"></path>
                    </svg>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {selected.length === 0 && (
        <div className="mt-4 p-3 bg-blue-900/20 border border-blue-800 rounded-lg">
          <p className="text-sm text-blue-300">
            <strong>💡 Nota:</strong> Si no selecciona ningún agente, se ejecutarán todos automáticamente.
          </p>
        </div>
      )}
    </div>
  )
}
