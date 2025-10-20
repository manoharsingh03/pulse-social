import React, { useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '@/App';

function LandingPage() {
  const navigate = useNavigate();
  const { user } = useContext(AuthContext);

  React.useEffect(() => {
    if (user) {
      navigate('/dashboard');
    }
  }, [user, navigate]);

  const handleLogin = () => {
    const redirectUrl = `${window.location.origin}/dashboard`;
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="landing-container" data-testid="landing-page">
      <div className="landing-content">
        <div className="landing-logo" data-testid="app-logo">Pulse</div>
        <h1 className="landing-title" data-testid="main-title">
          Feel. Connect. Heal.
        </h1>
        <p className="landing-subtitle" data-testid="subtitle">
          A new-age social platform for authentic emotional expression.
          No likes. No follows. Just real human connection.
        </p>
        <button 
          className="landing-cta" 
          onClick={handleLogin}
          data-testid="login-button"
        >
          Start Your Pulse
        </button>

        <div className="landing-features">
          <div className="feature-card" data-testid="feature-mood">
            <div className="feature-icon">💭</div>
            <h3 className="feature-title">Mood Pulses</h3>
            <p className="feature-desc">
              Express your real-time emotions through text or voice. No filters, just truth.
            </p>
          </div>
          <div className="feature-card" data-testid="feature-circles">
            <div className="feature-icon">🔗</div>
            <h3 className="feature-title">Instant Circles</h3>
            <p className="feature-desc">
              Get matched with 5-10 people feeling the same way. Ephemeral chats, lasting impact.
            </p>
          </div>
          <div className="feature-card" data-testid="feature-map">
            <div className="feature-icon">🌍</div>
            <h3 className="feature-title">Emotional Map</h3>
            <p className="feature-desc">
              See what the world is feeling right now. Real-time emotional pulse of humanity.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LandingPage;