import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import '@/App.css';
import LandingPage from '@/pages/LandingPage';
import Dashboard from '@/pages/Dashboard';
import CircleChat from '@/pages/CircleChat';
import { Toaster } from '@/components/ui/sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Auth Context
export const AuthContext = React.createContext();

function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Check for session_id in URL fragment
    const hash = window.location.hash;
    if (hash && hash.includes('session_id=')) {
      const sessionId = hash.split('session_id=')[1].split('&')[0];
      handleSessionExchange(sessionId);
      return;
    }

    // Check existing session
    checkSession();
  }, []);

  const handleSessionExchange = async (sessionId) => {
    try {
      const response = await axios.post(`${API}/auth/session`, { session_id: sessionId }, {
        withCredentials: true
      });
      setUser(response.data.user);
      window.history.replaceState({}, document.title, '/dashboard');
      navigate('/dashboard');
    } catch (error) {
      console.error('Session exchange failed:', error);
      setLoading(false);
    }
  };

  const checkSession = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`, {
        withCredentials: true
      });
      setUser(response.data);
      if (location.pathname === '/') {
        navigate('/dashboard');
      }
    } catch (error) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      await axios.post(`${API}/auth/logout`, {}, { withCredentials: true });
      setUser(null);
      navigate('/');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="pulse-loader"></div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, loading, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

function ProtectedRoute({ children }) {
  const { user, loading } = React.useContext(AuthContext);

  if (loading) return null;
  if (!user) return <Navigate to="/" replace />;

  return children;
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/circles/:circleId"
              element={
                <ProtectedRoute>
                  <CircleChat />
                </ProtectedRoute>
              }
            />
          </Routes>
          <Toaster position="top-center" />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;