import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'

export default function ServerDetail({ user }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const [server, setServer] = useState(null)
  const [stats, setStats] = useState({})
  const [logs, setLogs] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchServer = async () => {
      try {
        const token = localStorage.getItem('access_token')
        const response = await axios.get(`/api/servers/${id}`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        setServer(response.data)
        setStats(response.data.stats || {})
      } catch (error) {
        console.error('Failed to fetch server:', error)
        navigate('/dashboard')
      } finally {
        setLoading(false)
      }
    }
    
    fetchServer()
    
    const interval = setInterval(fetchServer, 5000)
    return () => clearInterval(interval)
  }, [id, navigate])

  const fetchLogs = async () => {
    try {
      const token = localStorage.getItem('access_token')
      const response = await axios.get(`/api/servers/${id}/logs?tail=50`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setLogs(response.data.logs || '')
    } catch (error) {
      console.error('Failed to fetch logs:', error)
    }
  }

  const handleWake = async () => {
    try {
      const token = localStorage.getItem('access_token')
      await axios.post(`/api/servers/${id}/wake`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setServer(prev => ({ ...prev, state: 'RUNNING' }))
    } catch (error) {
      console.error('Failed to wake server:', error)
    }
  }

  const handleHibernate = async () => {
    try {
      const token = localStorage.getItem('access_token')
      await axios.post(`/api/servers/${id}/hibernate`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      })
      setServer(prev => ({ ...prev, state: 'SLEEPING' }))
    } catch (error) {
      console.error('Failed to hibernate server:', error)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this server?')) return
    
    try {
      const token = localStorage.getItem('access_token')
      await axios.delete(`/api/servers/${id}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      navigate('/dashboard')
    } catch (error) {
      console.error('Failed to delete server:', error)
    }
  }

  if (loading) {
    return <div>Loading...</div>
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1>{server.friendly_name}</h1>
        <button onClick={() => navigate('/dashboard')} style={styles.backButton}>
          ← Back to Dashboard
        </button>
      </div>

      <div style={styles.section}>
        <h2>Server Status</h2>
        <div style={styles.infoGrid}>
          <div>
            <label>State</label>
            <span style={styles.status(server.state)}>{server.state}</span>
          </div>
          <div>
            <label>Public Port</label>
            <span>{server.public_port || 'N/A'}</span>
          </div>
          <div>
            <label>CPU</label>
            <span>{stats.cpu_percent || 0}%</span>
          </div>
          <div>
            <label>Memory</label>
            <span>{stats.memory_percent || 0}%</span>
          </div>
        </div>
      </div>

      <div style={styles.section}>
        <h2>Actions</h2>
        <div style={styles.buttonGroup}>
          {server.state === 'SLEEPING' && (
            <button onClick={handleWake} style={styles.wakeButton}>Wake Server</button>
          )}
          {server.state === 'RUNNING' && (
            <button onClick={handleHibernate} style={styles.hibernateButton}>Hibernate</button>
          )}
          <button onClick={fetchLogs} style={styles.logsButton}>Refresh Logs</button>
          <button onClick={handleDelete} style={styles.deleteButton}>Delete Server</button>
        </div>
      </div>

      <div style={styles.section}>
        <h2>Server Logs</h2>
        <pre style={styles.logs}>{logs || 'No logs available'}</pre>
      </div>
    </div>
  )
}

const styles = {
  container: {
    padding: '40px',
    maxWidth: '1200px',
    margin: '0 auto'
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '40px'
  },
  backButton: {
    padding: '10px 20px',
    background: '#0f3460',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer'
  },
  section: {
    background: '#0f3460',
    padding: '24px',
    borderRadius: '8px',
    marginBottom: '24px'
  },
  infoGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '16px',
    marginTop: '16px'
  },
  status: (state) => ({
    display: 'inline-block',
    padding: '4px 12px',
    borderRadius: '12px',
    fontSize: '14px',
    fontWeight: 'bold',
    background: state === 'RUNNING' ? '#4ade80' : '#fbbf24',
    color: '#000'
  }),
  buttonGroup: {
    display: 'flex',
    gap: '12px',
    flexWrap: 'wrap'
  },
  wakeButton: {
    padding: '12px 24px',
    background: '#4ade80',
    color: '#000',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 'bold'
  },
  hibernateButton: {
    padding: '12px 24px',
    background: '#fbbf24',
    color: '#000',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 'bold'
  },
  logsButton: {
    padding: '12px 24px',
    background: '#0f3460',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer'
  },
  deleteButton: {
    padding: '12px 24px',
    background: '#e94560',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer'
  },
  logs: {
    background: '#000',
    color: '#0f0',
    padding: '16px',
    borderRadius: '4px',
    fontSize: '12px',
    maxHeight: '400px',
    overflow: 'auto'
  }
}
