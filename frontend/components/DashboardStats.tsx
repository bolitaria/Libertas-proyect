import React from 'react'
import { FileText, CheckCircle, Users, Database } from 'lucide-react'
import { motion } from 'framer-motion'

interface DashboardStatsProps {
  stats: {
    documents: number
    classified: number
    users: number
    storage: number
  }
}

const DashboardStats: React.FC<DashboardStatsProps> = ({ stats }) => {
  const statCards = [
    {
      title: 'Documentos',
      value: stats.documents,
      icon: <FileText className="h-6 w-6" />,
      color: 'bg-blue-500',
      description: 'Total descargados'
    },
    {
      title: 'Clasificados',
      value: stats.classified,
      icon: <CheckCircle className="h-6 w-6" />,
      color: 'bg-green-500',
      description: 'Procesados por ML'
    },
    {
      title: 'Usuarios',
      value: stats.users,
      icon: <Users className="h-6 w-6" />,
      color: 'bg-purple-500',
      description: 'En la red P2P'
    },
    {
      title: 'Almacenamiento',
      value: `${stats.storage} GB`,
      icon: <Database className="h-6 w-6" />,
      color: 'bg-amber-500',
      description: 'Espacio utilizado'
    }
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {statCards.map((stat, index) => (
        <motion.div
          key={stat.title}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: index * 0.1 }}
          whileHover={{ scale: 1.05 }}
          className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-6"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">{stat.title}</p>
              <p className="text-3xl font-bold mt-2">{stat.value}</p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{stat.description}</p>
            </div>
            <div className={`p-3 rounded-full ${stat.color} text-white`}>
              {stat.icon}
            </div>
          </div>
          <div className="mt-4">
            <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <motion.div
                className={`h-full ${stat.color}`}
                initial={{ width: 0 }}
                animate={{ width: `${Math.min((index + 1) * 25, 100)}%` }}
                transition={{ duration: 1, delay: 0.5 }}
              />
            </div>
          </div>
        </motion.div>
      ))}
    </div>
  )
}

export default DashboardStats