import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext } from '@/App';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const EMOTIONS = [
  { emoji: '😊', name: 'joyful' },
  { emoji: '😔', name: 'sad' },
  { emoji: '😤', name: 'stressed' },
  { emoji: '😰', name: 'anxious' },
  { emoji: '😡', name: 'angry' },
  { emoji: '😌', name: 'peaceful' },
  { emoji: '😞', name: 'lonely' },
  { emoji: '🤗', name: 'grateful' },
];

function Dashboard() {
  const { user, logout } = useContext(AuthContext);
  const navigate = useNavigate();
  const [selectedEmotion, setSelectedEmotion] = useState(null);
  const [moodText, setMoodText] = useState('');
  const [posting, setPosting] = useState(false);
  const [circles, setCircles] = useState([]);
  const [mapData, setMapData] = useState([]);
  const [myPulses, setMyPulses] = useState([]);

  useEffect(() => {
    fetchCircles();
    fetchMapData();
    fetchMyPulses();
  }, []);

  const fetchCircles = async () => {
    try {
      const response = await axios.get(`${API}/circles`, { withCredentials: true });
      setCircles(response.data);
    } catch (error) {
      console.error('Failed to fetch circles:', error);
    }
  };

  const fetchMapData = async () => {
    try {
      const response = await axios.get(`${API}/map`);
      setMapData(response.data);
    } catch (error) {
      console.error('Failed to fetch map data:', error);
    }
  };

  const fetchMyPulses = async () => {
    try {
      const response = await axios.get(`${API}/pulse/me`, { withCredentials: true });
      setMyPulses(response.data);
    } catch (error) {
      console.error('Failed to fetch pulses:', error);
    }
  };

  const handlePostPulse = async () => {
    if (!selectedEmotion || !moodText.trim()) {
      toast.error('Please select an emotion and write something');
      return;
    }

    setPosting(true);
    try {
      await axios.post(
        `${API}/pulse`,
        {
          emotion: selectedEmotion.name,
          text: moodText,
          location: 'Global' // Could use geolocation API
        },
        { withCredentials: true }
      );
      toast.success('Pulse posted! Matching you with a circle...');
      setSelectedEmotion(null);
      setMoodText('');
      setTimeout(() => {
        fetchCircles();
        fetchMyPulses();
      }, 1000);
    } catch (error) {
      console.error('Failed to post pulse:', error);
      toast.error('Failed to post pulse');
    } finally {
      setPosting(false);
    }
  };

  const getTimeRemaining = (expiresAt) => {
    const now = new Date();
    const expiry = new Date(expiresAt);
    const diff = expiry - now;
    const minutes = Math.floor(diff / 60000);
    return minutes > 0 ? `${minutes}m left` : 'Expired';
  };

  return (
    <div className="dashboard-container" data-testid="dashboard-page">
      <header className="dashboard-header">
        <div className="dashboard-logo" data-testid="dashboard-logo">Pulse</div>
        <div className="user-section">
          <img 
            src={user?.picture} 
            alt={user?.name} 
            className="user-avatar"
            data-testid="user-avatar"
          />
          <span className="user-name" data-testid="user-name">{user?.name}</span>
          <button 
            className="logout-btn" 
            onClick={logout}
            data-testid="logout-button"
          >
            Logout
          </button>
        </div>
      </header>

      <main className="dashboard-main">
        <div className="dashboard-grid">
          {/* Mood Poster */}
          <section className="section-card" data-testid="mood-poster-section">
            <h2 className="section-title">How are you feeling?</h2>
            <div className="mood-poster">
              <div className="emotion-grid">
                {EMOTIONS.map((emotion) => (
                  <button
                    key={emotion.name}
                    className={`emotion-btn ${selectedEmotion?.name === emotion.name ? 'selected' : ''}`}
                    onClick={() => setSelectedEmotion(emotion)}
                    data-testid={`emotion-${emotion.name}`}
                  >
                    {emotion.emoji}
                  </button>
                ))}
              </div>
              <textarea
                className="mood-textarea"
                placeholder="What's on your mind? Share your truth..."
                value={moodText}
                onChange={(e) => setMoodText(e.target.value)}
                data-testid="mood-textarea"
              />
              <button
                className="post-btn"
                onClick={handlePostPulse}
                disabled={posting || !selectedEmotion || !moodText.trim()}
                data-testid="post-pulse-button"
              >
                {posting ? 'Posting...' : 'Send Pulse'}
              </button>
            </div>
          </section>

          {/* Active Circles */}
          <section className="section-card" data-testid="circles-section">
            <h2 className="section-title">Your Circles</h2>
            <div className="circles-list">
              {circles.length === 0 ? (
                <div className="empty-state" data-testid="empty-circles">
                  No active circles yet. Post a pulse to get matched!
                </div>
              ) : (
                circles.map((circle) => (
                  <div
                    key={circle.id}
                    className="circle-card"
                    onClick={() => navigate(`/circles/${circle.id}`)}
                    data-testid={`circle-${circle.id}`}
                  >
                    <div className="circle-emotion">
                      {EMOTIONS.find(e => e.name === circle.emotion)?.emoji || '💭'}
                    </div>
                    <div className="circle-info">
                      <span>{circle.members.length} members</span>
                      <span>{getTimeRemaining(circle.expires_at)}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>

        {/* Emotional Map */}
        <section className="section-card" data-testid="emotional-map-section">
          <h2 className="section-title">Global Emotional Map</h2>
          <div className="map-container">
            {mapData.length === 0 ? (
              <div className="empty-state" data-testid="empty-map">
                No emotional data yet. Be the first to share!
              </div>
            ) : (
              mapData.map((location, idx) => (
                <div key={idx} className="map-location" data-testid={`location-${idx}`}>
                  <div className="location-name">{location.location}</div>
                  <div className="emotion-percentages">
                    {Object.entries(location.emotions).map(([emotion, percent]) => (
                      <span key={emotion} className="emotion-tag">
                        {emotion}: {percent}%
                      </span>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        {/* My Pulses */}
        <section className="section-card" data-testid="my-pulses-section" style={{ marginTop: '2rem' }}>
          <h2 className="section-title">My Recent Pulses</h2>
          <div className="circles-list">
            {myPulses.length === 0 ? (
              <div className="empty-state" data-testid="empty-pulses">
                You haven't posted any pulses yet.
              </div>
            ) : (
              myPulses.map((pulse) => (
                <div key={pulse.id} className="circle-card" data-testid={`pulse-${pulse.id}`}>
                  <div className="circle-emotion">
                    {EMOTIONS.find(e => e.name === pulse.emotion)?.emoji || '💭'}
                  </div>
                  <p style={{ margin: '0.5rem 0', fontSize: '0.95rem' }}>{pulse.text}</p>
                  <div className="circle-info">
                    <span>Sentiment: {pulse.sentiment || 'neutral'}</span>
                    <span>{new Date(pulse.timestamp).toLocaleString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export default Dashboard;