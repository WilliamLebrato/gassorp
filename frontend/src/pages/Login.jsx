import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function Login({ setUser }) {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')

  const handleLogin = (e) => {
    e.preventDefault()
    
    // Mock login - create a fake user and token
    const mockUser = {
      id: 1,
      email: email || 'demo@gsp.dev',
      credits: 100.0
    }
    
    const mockToken = btoa(JSON.stringify(mockUser))
    localStorage.setItem('access_token', mockToken)
    setUser(mockUser)
    navigate('/dashboard')
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Game Server Platform</h1>
        <p style={styles.subtitle}>Deploy and manage game servers</p>
        <form onSubmit={handleLogin}>
          <input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={styles.input}
          />
          <button type="submit" style={styles.button}>
            Sign In (Demo Mode)
          </button>
        </form>
        <p style={styles.demo}>
          Demo Mode - No OAuth configured
        </p>
      </div>
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)'
  },
  card: {
    background: '#0f3460',
    padding: '40px',
    borderRadius: '12px',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    textAlign: 'center',
    minWidth: '350px'
  },
  title: {
    color: '#e94560',
    marginBottom: '10px',
    fontSize: '28px'
  },
  subtitle: {
    color: '#a0a0a0',
    marginBottom: '30px',
    fontSize: '14px'
  },
  input: {
    width: '100%',
    padding: '12px',
    marginBottom: '16px',
    border: 'none',
    borderRadius: '6px',
    background: '#1a1a2e',
    color: 'white',
    fontSize: '16px'
  },
  button: {
    width: '100%',
    padding: '12px',
    border: 'none',
    borderRadius: '6px',
    background: '#e94560',
    color: 'white',
    fontSize: '16px',
    cursor: 'pointer',
    fontWeight: 'bold'
  },
  demo: {
    marginTop: '20px',
    fontSize: '12px',
    color: '#666'
  }
}
