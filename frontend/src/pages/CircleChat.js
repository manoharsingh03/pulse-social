import React, { useState, useEffect, useContext } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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

function CircleChat() {
  const { circleId } = useParams();
  const navigate = useNavigate();
  const { user } = useContext(AuthContext);
  const [circle, setCircle] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    fetchCircle();
    fetchMessages();
    const interval = setInterval(fetchMessages, 3000); // Poll every 3 seconds
    return () => clearInterval(interval);
  }, [circleId]);

  const fetchCircle = async () => {
    try {
      const response = await axios.get(`${API}/circles/${circleId}`, { withCredentials: true });
      setCircle(response.data);
    } catch (error) {
      console.error('Failed to fetch circle:', error);
      toast.error('Circle not found');
      navigate('/dashboard');
    }
  };

  const fetchMessages = async () => {
    try {
      const response = await axios.get(`${API}/circles/${circleId}/messages`, { withCredentials: true });
      setMessages(response.data);
    } catch (error) {
      console.error('Failed to fetch messages:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!newMessage.trim()) return;

    setSending(true);
    try {
      await axios.post(
        `${API}/circles/${circleId}/messages`,
        { message: newMessage },
        { withCredentials: true }
      );
      setNewMessage('');
      fetchMessages();
    } catch (error) {
      console.error('Failed to send message:', error);
      toast.error('Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const getTimeRemaining = (expiresAt) => {
    const now = new Date();
    const expiry = new Date(expiresAt);
    const diff = expiry - now;
    const minutes = Math.floor(diff / 60000);
    return minutes > 0 ? `${minutes} minutes remaining` : 'Expired';
  };

  if (!circle) {
    return (
      <div className="loading-screen">
        <div className="pulse-loader"></div>
      </div>
    );
  }

  return (
    <div className="circle-chat-container" data-testid="circle-chat-page">
      <header className="chat-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '2rem' }}>
              {EMOTIONS.find(e => e.name === circle.emotion)?.emoji || '💭'}
            </span>
            <div>
              <h2 className="section-title" style={{ marginBottom: '0.25rem' }} data-testid="circle-emotion">
                {circle.emotion} circle
              </h2>
              <p style={{ fontSize: '0.875rem', color: '#64748b' }} data-testid="circle-expiry">
                {circle.members.length} members · {getTimeRemaining(circle.expires_at)}
              </p>
            </div>
          </div>
        </div>
        <button 
          className="back-btn" 
          onClick={() => navigate('/dashboard')}
          data-testid="back-button"
        >
          ← Back
        </button>
      </header>

      <main className="chat-main">
        <div className="messages-container" data-testid="messages-container">
          {messages.length === 0 ? (
            <div className="empty-state" data-testid="empty-messages">
              No messages yet. Start the conversation!
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className={`message-bubble ${msg.user_id === user?.id ? 'own' : ''}`}
                data-testid={`message-${msg.id}`}
              >
                <p className="message-text">{msg.message}</p>
                <p className="message-time">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </p>
              </div>
            ))
          )}
        </div>

        <div className="message-input-container">
          <input
            type="text"
            className="message-input"
            placeholder="Share your feelings..."
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            data-testid="message-input"
          />
          <button
            className="send-btn"
            onClick={handleSendMessage}
            disabled={sending || !newMessage.trim()}
            data-testid="send-message-button"
          >
            {sending ? 'Sending...' : 'Send'}
          </button>
        </div>
      </main>
    </div>
  );
}

export default CircleChat;