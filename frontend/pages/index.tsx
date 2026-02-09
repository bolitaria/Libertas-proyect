import React, { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import DashboardStats from '@/components/DashboardStats'
import DocumentList from '@/components/DocumentList'
import SystemStatus from '@/components/SystemStatus'
import ClassificationChart from '@/components/ClassificationChart'
import RecentActivity from '@/components/RecentActivity'
import { useQuery } from 'react-query'
import axios from 'axios'
import { motion } from 'framer-motion'
import { Download, FileText, Shield, Users, BarChart3, Globe } from 'lucide-react'

const HomePage = () => {
  const [systemStats, setSystemStats] = useState({
    documents: 0,
    classified: 0,
    users: 0,
    storage: 0
  })

  const { data: apiStatus } = useQuery('api-status', async () => {
    const response = await axios.get('http://localhost:8000/health')
    return response.data
  }, {
    refetchInterval: 30000
  })

  const { data: documents } = useQuery('documents', async () => {
    const response = await axios.get('http://localhost:8000/api/documents')
    return response.data
  })

  const { data: classificationStats } = useQuery('classification-stats', async () => {
    const response = await axios.get('http://localhost:8000/api/classification/stats')
    return response.data
  })

  useEffect(() => {
    // Simular carga de estadísticas
    const loadStats = async () => {
      try {
        // En producción, estos vendrían de la API
        setSystemStats({
          documents: 156,
          classified: 89,
          users: 12,
          storage: 2.4
        })
      } catch (error) {
        console.error('Error loading stats:', error)
      }
    }

    loadStats()
  }, [])

  const features = [
    {
      icon: <Download className="h-8 w-8" />,
      title: "Descarga Automática",
      description: "Descarga automática de documentos DOJ sobre Epstein",
      color: "from-blue-500 to-cyan-500"
    },
    {
      icon: <FileText className="h-8 w-8" />,
      title: "Clasificación ML",
      description: "Clasificación inteligente con modelos pre-entrenados",
      color: "from-purple-500 to-pink-500"
    },
    {
      icon: <Shield className="h-8 w-8" />,
      title: "Cifrado E2E",
      description: "Cifrado de extremo a extremo para máxima privacidad",
      color: "from-green-500 to-emerald-500"
    },
    {
      icon: <Users className="h-8 w-8" />,
      title: "Red P2P",
      description: "Comparte documentos de forma descentralizada",
      color: "from-orange-500 to-red-500"
    },
    {
      icon: <BarChart3 className="h-8 w-8" />,
      title: "Análisis Avanzado",
      description: "Análisis detallado y visualización de datos",
      color: "from-indigo-500 to-blue-500"
    },
    {
      icon: <Globe className="h-8 w-8" />,
      title: "Acceso Global",
      description: "Acceso desde cualquier lugar con conexión a internet",
      color: "from-rose-500 to-pink-500"
    }
  ]

  return (
    <Layout>
      <div className="space-y-8">
        {/* Hero Section */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center py-8"
        >
          <h1 className="text-4xl md:text-6xl font-bold bg-gradient-to-r from-libertas-blue via-libertas-purple to-libertas-teal bg-clip-text text-transparent">
            🕊️ Libertas Project
          </h1>
          <p className="text-xl text-gray-600 dark:text-gray-300 mt-4 max-w-3xl mx-auto">
            Sistema de investigación documental descentralizado para el caso Epstein.
            Descarga, clasifica y analiza documentos con privacidad y transparencia.
          </p>
        </motion.div>

        {/* Sistema Status */}
        <SystemStatus apiStatus={apiStatus} />

        {/* Dashboard Stats */}
        <DashboardStats stats={systemStats} />

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3, delay: index * 0.1 }}
              whileHover={{ scale: 1.05 }}
              className={`bg-gradient-to-br ${feature.color} p-6 rounded-2xl shadow-lg text-white`}
            >
              <div className="flex items-center space-x-4">
                <div className="p-3 bg-white/20 rounded-xl">
                  {feature.icon}
                </div>
                <div>
                  <h3 className="text-xl font-bold">{feature.title}</h3>
                  <p className="text-white/80 mt-1">{feature.description}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Charts and Lists */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <ClassificationChart data={classificationStats} />
          <RecentActivity />
        </div>

        {/* Document List */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800 dark:text-white">
              📄 Documentos Recientes
            </h2>
            <button className="px-4 py-2 bg-libertas-blue text-white rounded-lg hover:bg-libertas-blue/90 transition-colors">
              Ver Todos
            </button>
          </div>
          <DocumentList documents={documents?.documents || []} />
        </div>

        {/* Call to Action */}
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="text-center py-12 px-4 bg-gradient-to-r from-libertas-blue/10 to-libertas-purple/10 rounded-3xl"
        >
          <h2 className="text-3xl font-bold text-gray-800 dark:text-white mb-4">
            ¿Listo para empezar?
          </h2>
          <p className="text-gray-600 dark:text-gray-300 mb-8 max-w-2xl mx-auto">
            Únete a nuestra red descentralizada y contribuye a la transparencia 
            y acceso a la información.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button className="px-8 py-3 bg-libertas-blue text-white rounded-xl hover:bg-libertas-blue/90 transition-colors font-semibold">
              Descargar Cliente
            </button>
            <button className="px-8 py-3 bg-white dark:bg-gray-800 text-libertas-blue rounded-xl hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors font-semibold border-2 border-libertas-blue">
              Ver Documentación
            </button>
          </div>
        </motion.div>
      </div>
    </Layout>
  )
}

export default HomePage