import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import Navbar from '../components/Navbar'

export default function Dashboard({ user }) {
  const [servers, setServers] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchServers = async () => {
      try {
        const token = localStorage.getItem('access_token')
        const response = await axios.get('/api/servers', {
          headers: { Authorization: `Bearer ${token}` }
        })
        setServers(response.data)
      } catch (error) {
        console.error('Failed to fetch servers:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchServers()
  }, [])

  if (loading) {
    return <div>Loading...</div>
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1>My Servers</h1>
        <button onClick={() => navigate('/servers/create')} style={styles.createButton}>
          + Create Server
        </button>
      </div>
      
      {servers.length === 0 ? (
        <div style={styles.empty}>
          <p>No servers yet. Create your first game server!</p>
        </div>
      ) : (
        <div style={styles.serverGrid}>
          {servers.map(server => (
            <div key={server.id} style={styles.serverCard} onClick={() => navigate(`/servers/${server.id}`)}>
              <h3>{server.friendly_name}</h3>
              <p style={styles.gameName}>{server.game_image.friendly_name}</p>
              <div style={styles.status(server.state)}>
                {server.state}
              </div>
              <p style={styles.port}>Port: {server.public_port || 'N/A'}</p>
            </div>
          ))}
        </div>
      )}
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
  createButton: {
    padding: '12px 24px',
    background: '#e94560',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    fontSize: '16px',
    cursor: 'pointer'
  },
  empty: {
    textAlign: 'center',
    padding: '60px',
    color: '#a0a0a0'
  },
  serverGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '20px'
  },
  serverCard: {
    background: '#0f3460',
    padding: '24px',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'transform 0.2s',
    border: '1px solid #1a1a2e'
  },
  gameName: {
    color: '#a0a0a0',
    fontSize: '14px',
    margin: '8px 0'
  },
  status: (state) => ({
    display: 'inline-block',
    padding: '4px 12px',
    borderRadius: '12px',
    fontSize: '12px',
    fontWeight: 'bold',
    background: state === 'RUNNING' ? '#4ade80' : '#fbbf24',
    color: '#000'
  }),
  port: {
    color: '#a0a0a0',
    fontSize: '14px',
    marginTop: '12px'
  }
}
