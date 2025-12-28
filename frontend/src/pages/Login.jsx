import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const DEV_MODE = import.meta.env.VITE_DEV_MODE === 'true'

export default function Login({ setUser }) {
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleOAuthLogin = (provider) => {
    setIsLoading(true)
    setError('')
    window.location.href = `${API_URL}/auth/login/${provider}`
  }

  const handleDevLogin = async () => {
    setIsLoading(true)
    setError('')
    
    try {
      const response = await fetch(`${API_URL}/auth/dev-login`, {
        method: 'POST',
        credentials: 'include'
      })

      if (!response.ok) {
        throw new Error('DEV login failed')
      }

      const data = await response.json()
      setUser(data.user)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || 'DEV login failed. Make sure backend has DEV_MODE enabled.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Game Server Platform</h1>
        <p style={styles.subtitle}>Deploy and manage game servers</p>

        {error && (
          <div style={styles.error}>
            {error}
          </div>
        )}

        <div style={styles.buttonGroup}>
          <button
            onClick={() => handleOAuthLogin('google')}
            disabled={isLoading}
            style={{
              ...styles.oauthButton,
              ...styles.googleButton,
              ...(isLoading ? styles.buttonDisabled : {})
            }}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" style={styles.icon}>
              <path d="M17.64 9.2c0-.637-.057-1.252-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
              <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.715H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
              <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
              <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.292C4.672 5.159 6.656 3.58 9 3.58z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>

          <button
            onClick={() => handleOAuthLogin('microsoft')}
            disabled={isLoading}
            style={{
              ...styles.oauthButton,
              ...styles.microsoftButton,
              ...(isLoading ? styles.buttonDisabled : {})
            }}
          >
            <svg width="18" height="18" viewBox="0 0 23 23" style={styles.icon}>
              <path d="M11 11H0V0h11v11z" fill="#f25022"/>
              <path d="M23 11H12V0h11v11z" fill="#7fba00"/>
              <path d="M11 23H0V12h11v11z" fill="#00a4ef"/>
              <path d="M23 23H12V12h11v11z" fill="#ffb900"/>
            </svg>
            Continue with Microsoft
          </button>

          {DEV_MODE && (
            <>
              <div style={styles.divider} />
              <button
                onClick={handleDevLogin}
                disabled={isLoading}
                style={{
                  ...styles.oauthButton,
                  ...styles.devButton,
                  ...(isLoading ? styles.buttonDisabled : {})
                }}
              >
                ⚡ DEV LOGIN
              </button>
              <p style={styles.devNote}>
                Developer mode - Instant login without OAuth
              </p>
            </>
          )}
        </div>

        {!DEV_MODE && (
          <p style={styles.configNote}>
            OAuth providers require configuration. See backend/.env.example
          </p>
        )}
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
    minWidth: '400px'
  },
  title: {
    color: '#e94560',
    marginBottom: '10px',
    fontSize: '28px',
    fontWeight: 'bold'
  },
  subtitle: {
    color: '#a0a0a0',
    marginBottom: '30px',
    fontSize: '14px'
  },
  error: {
    background: 'rgba(233, 69, 96, 0.2)',
    border: '1px solid #e94560',
    color: '#e94560',
    padding: '12px',
    borderRadius: '6px',
    marginBottom: '20px',
    fontSize: '14px'
  },
  buttonGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px'
  },
  oauthButton: {
    width: '100%',
    padding: '14px 20px',
    border: 'none',
    borderRadius: '8px',
    color: 'white',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '12px',
    transition: 'all 0.2s',
    ':hover': {
      transform: 'translateY(-2px)',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)'
    }
  },
  googleButton: {
    background: '#4285F4'
  },
  microsoftButton: {
    background: '#00a4ef'
  },
  devButton: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    border: '2px solid #a78bfa'
  },
  buttonDisabled: {
    opacity: 0.6,
    cursor: 'not-allowed'
  },
  icon: {
    width: '18px',
    height: '18px'
  },
  divider: {
    height: '1px',
    background: '#16213e',
    margin: '8px 0'
  },
  devNote: {
    marginTop: '12px',
    fontSize: '12px',
    color: '#a78bfa',
    fontStyle: 'italic'
  },
  configNote: {
    marginTop: '20px',
    fontSize: '12px',
    color: '#666',
    lineHeight: '1.5'
  }
}
