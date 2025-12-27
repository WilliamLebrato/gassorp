import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

export default function CreateServer({ user }) {
  const [gameImages, setGameImages] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    friendly_name: '',
    game_image_id: '',
    auto_sleep: false
  })

  useEffect(() => {
    const fetchGameImages = async () => {
      try {
        const token = localStorage.getItem('access_token')
        const response = await axios.get('/api/game-images', {
          headers: { Authorization: `Bearer ${token}` }
        })
        setGameImages(response.data)
      } catch (error) {
        console.error('Failed to fetch game images:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchGameImages()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setCreating(true)
    
    try {
      const token = localStorage.getItem('access_token')
      const response = await axios.post('/api/servers', formData, {
        headers: { Authorization: `Bearer ${token}` }
      })
      navigate(`/servers/${response.data.id}`)
    } catch (error) {
      console.error('Failed to create server:', error)
      alert('Failed to create server: ' + (error.response?.data?.detail || error.message))
    } finally {
      setCreating(false)
    }
  }

  if (loading) {
    return <div>Loading...</div>
  }

  return (
    <div style={styles.container}>
      <h1>Create New Server</h1>
      <form onSubmit={handleSubmit} style={styles.form}>
        <div style={styles.field}>
          <label>Server Name</label>
          <input
            type="text"
            value={formData.friendly_name}
            onChange={(e) => setFormData({ ...formData, friendly_name: e.target.value })}
            required
            style={styles.input}
          />
        </div>

        <div style={styles.field}>
          <label>Game Type</label>
          <select
            value={formData.game_image_id}
            onChange={(e) => setFormData({ ...formData, game_image_id: e.target.value })}
            required
            style={styles.input}
          >
            <option value="">Select a game...</option>
            {gameImages.map(image => (
              <option key={image.id} value={image.id}>
                {image.friendly_name}
              </option>
            ))}
          </select>
        </div>

        <div style={styles.field}>
          <label style={styles.checkbox}>
            <input
              type="checkbox"
              checked={formData.auto_sleep}
              onChange={(e) => setFormData({ ...formData, auto_sleep: e.target.checked })}
            />
            Auto-hibernate when idle
          </label>
        </div>

        <div style={styles.buttonGroup}>
          <button type="submit" disabled={creating} style={styles.submitButton}>
            {creating ? 'Creating...' : 'Create Server'}
          </button>
          <button type="button" onClick={() => navigate('/dashboard')} style={styles.cancelButton}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}

const styles = {
  container: {
    padding: '40px',
    maxWidth: '600px',
    margin: '0 auto'
  },
  form: {
    background: '#0f3460',
    padding: '32px',
    borderRadius: '8px'
  },
  field: {
    marginBottom: '24px'
  },
  input: {
    width: '100%',
    padding: '12px',
    background: '#1a1a2e',
    border: '1px solid #16213e',
    borderRadius: '6px',
    color: 'white',
    fontSize: '16px',
    marginTop: '8px'
  },
  checkbox: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    cursor: 'pointer'
  },
  buttonGroup: {
    display: 'flex',
    gap: '12px',
    marginTop: '32px'
  },
  submitButton: {
    flex: 1,
    padding: '12px 24px',
    background: '#e94560',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    fontSize: '16px',
    cursor: 'pointer',
    fontWeight: 'bold'
  },
  cancelButton: {
    flex: 1,
    padding: '12px 24px',
    background: '#1a1a2e',
    color: 'white',
    border: '1px solid #16213e',
    borderRadius: '6px',
    fontSize: '16px',
    cursor: 'pointer'
  }
}
