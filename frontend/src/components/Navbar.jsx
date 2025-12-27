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
          <span>{user?.email}</span>
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
  logoutButton: {
    padding: '8px 16px',
    background: '#1a1a2e',
    color: 'white',
    border: '1px solid #16213e',
    borderRadius: '4px',
    cursor: 'pointer'
  }
}
