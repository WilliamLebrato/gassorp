import { useNavigate } from 'react-router-dom'

export default function Navbar({ user, setUser }) {
  const navigate = useNavigate()

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    setUser(null)
    navigate('/login')
  }

  return (
    <nav style={styles.navbar}>
      <div style={styles.container}>
        <h1 style={styles.logo} onClick={() => navigate('/dashboard')}>
          GSP
        </h1>
        <div style={styles.userInfo}>
          <div style={styles.balance}>
            <span style={styles.balanceLabel}>Balance:</span>
            <span style={styles.balanceValue}>${user?.credits?.toFixed(2) || '0.00'}</span>
          </div>
          <span style={styles.email}>{user?.email}</span>
          <button onClick={handleLogout} style={styles.logoutButton}>
            Logout
          </button>
        </div>
      </div>
    </nav>
  )
}

const styles = {
  navbar: {
    background: '#0f3460',
    padding: '16px 0',
    borderBottom: '1px solid #16213e'
  },
  container: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '0 40px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  logo: {
    color: '#e94560',
    fontSize: '24px',
    fontWeight: 'bold',
    margin: 0,
    cursor: 'pointer'
  },
  userInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px'
  },
  balance: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 16px',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    borderRadius: '8px',
    border: '2px solid #a78bfa'
  },
  balanceLabel: {
    color: '#e0e7ff',
    fontSize: '14px',
    fontWeight: '500'
  },
  balanceValue: {
    color: '#ffffff',
    fontSize: '16px',
    fontWeight: 'bold'
  },
  email: {
    color: '#a0a0a0',
    fontSize: '14px'
  },
  logoutButton: {
    padding: '8px 16px',
    background: '#1a1a2e',
    color: 'white',
    border: '1px solid #16213e',
    borderRadius: '4px',
    cursor: 'pointer'
  }
}
