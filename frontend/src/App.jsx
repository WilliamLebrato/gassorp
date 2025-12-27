import { Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ServerDetail from './pages/ServerDetail'
import CreateServer from './pages/CreateServer'
import Navbar from './components/Navbar'
import axios from 'axios'

function App() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem('access_token')
        if (!token) {
          setLoading(false)
          return
        }
        
        const response = await axios.get('/api/me', {
          headers: { Authorization: `Bearer ${token}` }
        })
        setUser(response.data)
      } catch (error) {
        localStorage.removeItem('access_token')
      } finally {
        setLoading(false)
      }
    }
    
    checkAuth()
  }, [])

  if (loading) {
    return <div>Loading...</div>
  }

  return (
    <>
      {user && <Navbar user={user} setUser={setUser} />}
      <Routes>
        <Route 
          path="/login" 
          element={!user ? <Login setUser={setUser} /> : <Navigate to="/dashboard" />} 
        />
        <Route 
          path="/dashboard" 
          element={user ? <Dashboard user={user} /> : <Navigate to="/login" />} 
        />
        <Route 
          path="/servers/create" 
          element={user ? <CreateServer user={user} /> : <Navigate to="/login" />} 
        />
        <Route 
          path="/servers/:id" 
          element={user ? <ServerDetail user={user} /> : <Navigate to="/login" />} 
        />
        <Route path="/" element={<Navigate to="/dashboard" />} />
      </Routes>
    </>
  )
}

export default App
