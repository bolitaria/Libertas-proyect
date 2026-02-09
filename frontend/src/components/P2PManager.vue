<template>
  <div class="p2p-manager">
    <div class="header">
      <h2>P2P Network Manager</h2>
      <div class="status-indicator" :class="networkStatus">
        {{ networkStatusText }}
      </div>
    </div>
    
    <div class="stats-grid">
      <div class="stat-card">
        <h3>Connected Peers</h3>
        <p class="stat-number">{{ stats.connectedPeers }}</p>
      </div>
      <div class="stat-card">
        <h3>Shared Files</h3>
        <p class="stat-number">{{ stats.sharedFiles }}</p>
      </div>
      <div class="stat-card">
        <h3>Download Speed</h3>
        <p class="stat-number">{{ formatSpeed(stats.downloadSpeed) }}</p>
      </div>
      <div class="stat-card">
        <h3>Upload Speed</h3>
        <p class="stat-number">{{ formatSpeed(stats.uploadSpeed) }}</p>
      </div>
    </div>
    
    <div class="tabs">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="{ active: activeTab === tab.id }"
      >
        {{ tab.label }}
      </button>
    </div>
    
    <!-- Tab: Shared Files -->
    <div v-if="activeTab === 'shared'" class="tab-content">
      <div class="action-bar">
        <button @click="shareNewFile" class="btn-primary">
          <i class="fas fa-share-alt"></i> Share New File
        </button>
        <button @click="refreshShared" class="btn-secondary">
          <i class="fas fa-sync"></i> Refresh
        </button>
      </div>
      
      <div class="file-list">
        <div v-for="file in sharedFiles" :key="file.hash" class="file-card">
          <div class="file-info">
            <h4>{{ file.name }}</h4>
            <div class="file-meta">
              <span class="size">{{ formatBytes(file.size) }}</span>
              <span class="peers">{{ file.peers }} peers</span>
              <span class="downloads">{{ file.downloads }} downloads</span>
            </div>
            <div class="file-actions">
              <button @click="copyMagnet(file)" class="btn-small">
                <i class="fas fa-magnet"></i> Magnet Link
              </button>
              <button @click="stopSharing(file)" class="btn-small btn-danger">
                <i class="fas fa-stop"></i> Stop Sharing
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Tab: Network Search -->
    <div v-if="activeTab === 'search'" class="tab-content">
      <div class="search-box">
        <input 
          v-model="searchQuery" 
          @keyup.enter="searchNetwork"
          placeholder="Search for documents in P2P network..."
          type="search"
        />
        <button @click="searchNetwork" class="btn-primary">
          <i class="fas fa-search"></i> Search
        </button>
      </div>
      
      <div v-if="searchResults.length > 0" class="search-results">
        <h3>Search Results ({{ searchResults.length }})</h3>
        
        <div v-for="result in searchResults" :key="result.file_hash" class="result-card">
          <div class="result-info">
            <h4>{{ result.name }}</h4>
            <p class="result-meta">
              Size: {{ formatBytes(result.size) }} | 
              Peers: {{ result.peer_count }} | 
              Source: {{ result.source }}
            </p>
            <div v-if="result.encrypted" class="encrypted-badge">
              <i class="fas fa-lock"></i> Encrypted
            </div>
          </div>
          <div class="result-actions">
            <button 
              @click="downloadFromPeer(result)" 
              :disabled="downloading[result.file_hash]"
              class="btn-primary"
            >
              <span v-if="downloading[result.file_hash]">
                <i class="fas fa-spinner fa-spin"></i> Downloading...
              </span>
              <span v-else>
                <i class="fas fa-download"></i> Download
              </span>
            </button>
          </div>
        </div>
      </div>
      
      <div v-else-if="searchPerformed" class="no-results">
        <p>No results found for "{{ searchQuery }}"</p>
      </div>
    </div>
    
    <!-- Tab: Network Settings -->
    <div v-if="activeTab === 'settings'" class="tab-content">
      <div class="settings-form">
        <div class="form-group">
          <label>Max Upload Speed</label>
          <div class="slider-container">
            <input 
              v-model="settings.maxUploadSpeed" 
              type="range" 
              min="0" 
              max="10000" 
              step="100"
            />
            <span>{{ formatSpeed(settings.maxUploadSpeed) }}</span>
          </div>
        </div>
        
        <div class="form-group">
          <label>Max Download Speed</label>
          <div class="slider-container">
            <input 
              v-model="settings.maxDownloadSpeed" 
              type="range" 
              min="0" 
              max="10000" 
              step="100"
            />
            <span>{{ formatSpeed(settings.maxDownloadSpeed) }}</span>
          </div>
        </div>
        
        <div class="form-group">
          <label>Max Connections</label>
          <input 
            v-model="settings.maxConnections" 
            type="number" 
            min="1" 
            max="500"
          />
        </div>
        
        <div class="form-group">
          <label>
            <input v-model="settings.enableEncryption" type="checkbox" />
            Enable End-to-End Encryption
          </label>
        </div>
        
        <div class="form-group">
          <label>
            <input v-model="settings.autoShare" type="checkbox" />
            Automatically Share Processed Documents
          </label>
        </div>
        
        <div class="form-actions">
          <button @click="saveSettings" class="btn-primary">
            Save Settings
          </button>
        </div>
      </div>
    </div>
    
    <!-- Download Progress Modal -->
    <div v-if="activeDownload" class="modal-overlay">
      <div class="modal">
        <h3>Download Progress</h3>
        <p>{{ activeDownload.fileName }}</p>
        
        <div class="progress-container">
          <div class="progress-bar" :style="{ width: activeDownload.progress + '%' }"></div>
        </div>
        
        <div class="download-details">
          <div>Progress: {{ activeDownload.progress.toFixed(1) }}%</div>
          <div>Speed: {{ formatSpeed(activeDownload.speed) }}</div>
          <div>Peers: {{ activeDownload.peers }}</div>
        </div>
        
        <button @click="cancelDownload" class="btn-danger">
          Cancel Download
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useToast } from 'vue-toastification'

export default {
  name: 'P2PManager',
  
  setup() {
    const toast = useToast()
    
    // Estado del componente
    const networkStatus = ref('disconnected')
    const networkStatusText = ref('Disconnected')
    const activeTab = ref('shared')
    const searchQuery = ref('')
    const searchResults = reactive([])
    const searchPerformed = ref(false)
    const sharedFiles = reactive([])
    const downloading = reactive({})
    const activeDownload = ref(null)
    
    // Estadísticas
    const stats = reactive({
      connectedPeers: 0,
      sharedFiles: 0,
      downloadSpeed: 0,
      uploadSpeed: 0
    })
    
    // Configuración
    const settings = reactive({
      maxUploadSpeed: 1000,
      maxDownloadSpeed: 5000,
      maxConnections: 100,
      enableEncryption: true,
      autoShare: false
    })
    
    // Tabs
    const tabs = [
      { id: 'shared', label: 'Shared Files' },
      { id: 'search', label: 'Network Search' },
      { id: 'settings', label: 'Settings' }
    ]
    
    // WebSocket para actualizaciones en tiempo real
    let ws = null
    
    // Métodos
    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/p2p`
      
      ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        networkStatus.value = 'connected'
        networkStatusText.value = 'Connected'
        toast.success('Connected to P2P network')
      }
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        
        switch (data.type) {
          case 'stats_update':
            Object.assign(stats, data.stats)
            break
            
          case 'download_progress':
            if (activeDownload.value && activeDownload.value.id === data.downloadId) {
              activeDownload.value = { ...activeDownload.value, ...data.progress }
            }
            break
            
          case 'download_complete':
            toast.success(`Download complete: ${data.fileName}`)
            if (activeDownload.value && activeDownload.value.id === data.downloadId) {
              activeDownload.value = null
            }
            break
            
          case 'peer_connected':
            toast.info(`New peer connected: ${data.peerId}`)
            break
        }
      }
      
      ws.onclose = () => {
        networkStatus.value = 'disconnected'
        networkStatusText.value = 'Disconnected'
        toast.warning('Disconnected from P2P network')
        
        // Reconectar después de 5 segundos
        setTimeout(connectWebSocket, 5000)
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        toast.error('P2P connection error')
      }
    }
    
    const fetchStats = async () => {
      try {
        const response = await fetch('/api/p2p/stats')
        const data = await response.json()
        Object.assign(stats, data)
      } catch (error) {
        console.error('Error fetching stats:', error)
      }
    }
    
    const fetchSharedFiles = async () => {
      try {
        const response = await fetch('/api/p2p/shared')
        const files = await response.json()
        sharedFiles.splice(0, sharedFiles.length, ...files)
      } catch (error) {
        console.error('Error fetching shared files:', error)
        toast.error('Failed to load shared files')
      }
    }
    
    const searchNetwork = async () => {
      if (!searchQuery.value.trim()) return
      
      try {
        const response = await fetch(`/api/p2p/search?q=${encodeURIComponent(searchQuery.value)}`)
        const results = await response.json()
        
        searchResults.splice(0, searchResults.length, ...results)
        searchPerformed.value = true
        
        toast.info(`Found ${results.length} results`)
      } catch (error) {
        console.error('Error searching network:', error)
        toast.error('Search failed')
      }
    }
    
    const downloadFromPeer = async (file) => {
      if (downloading[file.file_hash]) return
      
      downloading[file.file_hash] = true
      
      try {
        const response = await fetch('/api/p2p/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            file_hash: file.file_hash,
            peer_id: file.peer_id
          })
        })
        
        if (response.ok) {
          const data = await response.json()
          
          activeDownload.value = {
            id: data.downloadId,
            fileName: file.name,
            progress: 0,
            speed: 0,
            peers: 1
          }
          
          toast.info(`Started download: ${file.name}`)
        } else {
          throw new Error('Download request failed')
        }
      } catch (error) {
        console.error('Error starting download:', error)
        toast.error('Download failed')
      } finally {
        delete downloading[file.file_hash]
      }
    }
    
    const shareNewFile = async () => {
      // Esto abriría un selector de archivos en una implementación real
      toast.info('File sharing dialog would open here')
    }
    
    const stopSharing = async (file) => {
      try {
        const response = await fetch(`/api/p2p/shared/${file.hash}`, {
          method: 'DELETE'
        })
        
        if (response.ok) {
          toast.success(`Stopped sharing: ${file.name}`)
          fetchSharedFiles()
        }
      } catch (error) {
        console.error('Error stopping share:', error)
        toast.error('Failed to stop sharing')
      }
    }
    
    const copyMagnet = (file) => {
      navigator.clipboard.writeText(file.magnet_link)
        .then(() => toast.success('Magnet link copied to clipboard'))
        .catch(() => toast.error('Failed to copy magnet link'))
    }
    
    const cancelDownload = async () => {
      if (!activeDownload.value) return
      
      try {
        await fetch(`/api/p2p/download/${activeDownload.value.id}`, {
          method: 'DELETE'
        })
        
        toast.info('Download cancelled')
        activeDownload.value = null
      } catch (error) {
        console.error('Error cancelling download:', error)
      }
    }
    
    const saveSettings = async () => {
      try {
        const response = await fetch('/api/p2p/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(settings)
        })
        
        if (response.ok) {
          toast.success('Settings saved')
        }
      } catch (error) {
        console.error('Error saving settings:', error)
        toast.error('Failed to save settings')
      }
    }
    
    const formatBytes = (bytes) => {
      if (bytes === 0) return '0 B'
      
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }
    
    const formatSpeed = (bytesPerSecond) => {
      if (bytesPerSecond === 0) return '0 B/s'
      
      const k = 1024
      const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s']
      const i = Math.floor(Math.log(bytesPerSecond) / Math.log(k))
      
      return parseFloat((bytesPerSecond / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }
    
    const refreshShared = () => {
      fetchSharedFiles()
      toast.info('Refreshed shared files list')
    }
    
    // Ciclo de vida
    onMounted(() => {
      connectWebSocket()
      fetchStats()
      fetchSharedFiles()
      
      // Actualizar estadísticas cada 10 segundos
      const interval = setInterval(fetchStats, 10000)
      
      onUnmounted(() => {
        if (ws) ws.close()
        clearInterval(interval)
      })
    })
    
    return {
      // Estado
      networkStatus,
      networkStatusText,
      activeTab,
      searchQuery,
      searchResults,
      searchPerformed,
      sharedFiles,
      downloading,
      activeDownload,
      stats,
      settings,
      tabs,
      
      // Métodos
      searchNetwork,
      downloadFromPeer,
      shareNewFile,
      stopSharing,
      copyMagnet,
      cancelDownload,
      saveSettings,
      formatBytes,
      formatSpeed,
      refreshShared
    }
  }
}
</script>

<style scoped>
.p2p-manager {
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.status-indicator {
  padding: 5px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: bold;
  text-transform: uppercase;
}

.status-indicator.connected {
  background: #28a745;
  color: white;
}

.status-indicator.disconnected {
  background: #dc3545;
  color: white;
}

.status-indicator.connecting {
  background: #ffc107;
  color: black;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  padding: 15px;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.stat-card h3 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #666;
}

.stat-number {
  margin: 0;
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

.tabs {
  display: flex;
  border-bottom: 2px solid #dee2e6;
  margin-bottom: 20px;
}

.tabs button {
  padding: 10px 20px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  transition: all 0.3s;
}

.tabs button:hover {
  color: #333;
}

.tabs button.active {
  color: #007bff;
  border-bottom-color: #007bff;
  font-weight: bold;
}

.tab-content {
  background: white;
  padding: 20px;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.action-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.file-list, .search-results {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-card, .result-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 4px;
  border-left: 4px solid #007bff;
}

.file-info h4, .result-info h4 {
  margin: 0 0 5px 0;
  color: #333;
}

.file-meta, .result-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: #666;
}

.file-actions, .result-actions {
  display: flex;
  gap: 5px;
}

.btn-primary, .btn-secondary, .btn-danger, .btn-small {
  padding: 8px 15px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background: #545b62;
}

.btn-danger {
  background: #dc3545;
  color: white;
}

.btn-danger:hover {
  background: #bd2130;
}

.btn-small {
  padding: 5px 10px;
  font-size: 12px;
}

.btn-primary:disabled, .btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.search-box {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.search-box input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.encrypted-badge {
  display: inline-block;
  padding: 2px 8px;
  background: #28a745;
  color: white;
  border-radius: 10px;
  font-size: 11px;
  margin-top: 5px;
}

.no-results {
  text-align: center;
  padding: 40px;
  color: #666;
}

.settings-form {
  max-width: 500px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
  color: #333;
}

.form-group input[type="range"] {
  width: 100%;
}

.form-group input[type="number"] {
  width: 100px;
  padding: 5px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.form-group input[type="checkbox"] {
  margin-right: 10px;
}

.slider-container {
  display: flex;
  align-items: center;
  gap: 10px;
}

.slider-container span {
  min-width: 80px;
  text-align: right;
  font-size: 12px;
  color: #666;
}

.form-actions {
  margin-top: 30px;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal {
  background: white;
  padding: 30px;
  border-radius: 8px;
  max-width: 500px;
  width: 90%;
}

.progress-container {
  height: 20px;
  background: #f0f0f0;
  border-radius: 10px;
  margin: 20px 0;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: #007bff;
  transition: width 0.3s;
}

.download-details {
  display: flex;
  justify-content: space-between;
  margin-bottom: 20px;
  font-size: 12px;
  color: #666;
}

i {
  margin-right: 5px;
}

.fa-spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>