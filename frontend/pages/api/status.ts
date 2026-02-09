import { NextApiRequest, NextApiResponse } from 'next'
import axios from 'axios'

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  try {
    // Proxy para evitar CORS
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    
    const [healthRes, statsRes] = await Promise.allSettled([
      axios.get(`${backendUrl}/health`),
      axios.get(`${backendUrl}/api/status`)
    ])
    
    const data = {
      timestamp: new Date().toISOString(),
      backend: {
        health: healthRes.status === 'fulfilled' ? healthRes.value.data : { error: 'Unavailable' },
        stats: statsRes.status === 'fulfilled' ? statsRes.value.data : { error: 'Unavailable' }
      },
      frontend: {
        status: 'healthy',
        version: '1.0.0'
      }
    }
    
    res.status(200).json(data)
  } catch (error) {
    res.status(500).json({ error: 'Internal server error' })
  }
}