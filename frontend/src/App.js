import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [startMsg, setStartMsg] = useState('');
  const [status, setStatus] = useState({ 
    rtmp: 'unknown', 
    backend: 'unknown', 
    selenium: 'unknown', 
    error: '', 
    processing_active: 'false' 
  });
  const [pimeyesTest, setPimeyesTest] = useState(null);
  const [pimeyesTesting, setPimeyesTesting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const [uploadedImage, setUploadedImage] = useState(null);
  const [imageResults, setImageResults] = useState([]);
  const [activeTab, setActiveTab] = useState('dashboard');

  useEffect(() => {
    fetchProfiles();
    fetchStatus();
    const interval1 = setInterval(fetchProfiles, 2000);
    const interval2 = setInterval(fetchStatus, 1000);
    return () => { clearInterval(interval1); clearInterval(interval2); };
  }, []);

  const fetchProfiles = async () => {
    try {
      const res = await axios.get('http://localhost:8000/rtmp-profiles/');
      setProfiles(res.data.profiles);
      setLoading(false);
    } catch (err) {
      setLoading(false);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await axios.get('http://localhost:8000/status/');
      const newStatus = res.data;
      
      // Check if RTMP stream status changed from 'ok' to 'error'
      if (status.rtmp === 'ok' && newStatus.rtmp === 'error') {
        // Stream ended - show notification
        setStartMsg('RTMP stream has ended. Please restart your stream in OBS.');
        setTimeout(() => setStartMsg(''), 5000);
      }
      
      setStatus(newStatus);
    } catch (err) {
      setStatus({ 
        rtmp: 'unknown', 
        backend: 'unknown', 
        selenium: 'unknown', 
        error: 'Could not fetch status', 
        processing_active: 'false' 
      });
    }
  };

  const startRTMPProcessing = async () => {
    setProcessing(true);
    setStartMsg('Starting real-time face detection...');
    try {
      await axios.post('http://localhost:8000/start-rtmp-processing/');
      setStartMsg('Real-time face detection started!');
      setTimeout(() => setStartMsg(''), 3000);
    } catch (err) {
      setStartMsg('Failed to start real-time processing.');
      setTimeout(() => setStartMsg(''), 3000);
    }
    setProcessing(false);
  };

  const stopRTMPProcessing = async () => {
    setProcessing(true);
    setStartMsg('Stopping real-time face detection...');
    try {
      await axios.post('http://localhost:8000/stop-rtmp-processing/');
      setStartMsg('Real-time face detection stopped!');
      setTimeout(() => setStartMsg(''), 3000);
    } catch (err) {
      setStartMsg('Failed to stop real-time processing.');
      setTimeout(() => setStartMsg(''), 3000);
    }
    setProcessing(false);
  };

  const testPimeyes = async () => {
    setPimeyesTesting(true);
    setPimeyesTest(null);
    try {
      const res = await axios.get('http://localhost:8000/test-pimeyes/');
      setPimeyesTest(res.data);
    } catch (err) {
      setPimeyesTest({ 
        status: 'error', 
        message: err.response?.data?.detail || 'Unknown error' 
      });
    }
    setPimeyesTesting(false);
  };

  const handleImageUpload = async (e) => {
    e.preventDefault();
    const file = e.target.image.files[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg('Uploading...');
    setUploadedImage(URL.createObjectURL(file));
    setImageResults([]);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await axios.post('http://localhost:8000/upload-image/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setImageResults(res.data.results);
      setUploadMsg('Upload complete!');
      setTimeout(() => setUploadMsg(''), 3000);
    } catch (err) {
      setUploadMsg('Upload failed.');
      setTimeout(() => setUploadMsg(''), 3000);
    }
    setUploading(false);
  };

  const StatusIndicator = ({ status, label }) => {
    const getStatusColor = (status) => {
      switch (status) {
        case 'ok': return '#10b981';
        case 'error': return '#ef4444';
        case 'processing': return '#f59e0b';
        case 'warning': return '#f59e0b';
        default: return '#6b7280';
      }
    };

    const getStatusIcon = (status) => {
      switch (status) {
        case 'ok': return '✓';
        case 'error': return '✗';
        case 'processing': return '⟳';
        case 'warning': return '⚠';
        default: return '?';
      }
    };

    return (
      <div className="status-indicator">
        <div 
          className="status-dot"
          style={{ backgroundColor: getStatusColor(status) }}
        >
          {getStatusIcon(status)}
        </div>
        <span className="status-label">{label}</span>
        <span className="status-value">{status}</span>
      </div>
    );
  };

  const isProcessingActive = status.processing_active === 'true';

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <h1 className="title">
            <span className="title-icon">🤖</span>
            Meta AI Glasses
            <span className="title-subtitle">Real-Time Face Recognition</span>
          </h1>
          <div className="header-actions">
            <button 
              className={`btn btn-primary ${processing ? 'loading' : ''}`}
              onClick={isProcessingActive ? stopRTMPProcessing : startRTMPProcessing}
              disabled={processing}
            >
              {processing ? 'Processing...' : isProcessingActive ? 'Stop Detection' : 'Start Detection'}
            </button>
            <button 
              className={`btn btn-secondary ${pimeyesTesting ? 'loading' : ''}`}
              onClick={testPimeyes}
              disabled={pimeyesTesting}
            >
              {pimeyesTesting ? 'Testing...' : 'Test PimEyes'}
            </button>
          </div>
        </div>
      </header>

      <nav className="nav">
        <button 
          className={`nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          📊 Dashboard
        </button>
        <button 
          className={`nav-tab ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          📤 Upload Image
        </button>
        <button 
          className={`nav-tab ${activeTab === 'profiles' ? 'active' : ''}`}
          onClick={() => setActiveTab('profiles')}
        >
          👥 Detected Profiles
        </button>
      </nav>

      <main className="main">
        {activeTab === 'dashboard' && (
          <div className="dashboard">
            <div className="status-grid">
              <StatusIndicator status={status.rtmp} label="RTMP Stream" />
              <StatusIndicator status={status.backend} label="Backend" />
              <StatusIndicator status={status.selenium} label="Selenium/PimEyes" />
              <StatusIndicator 
                status={isProcessingActive ? 'ok' : 'unknown'} 
                label="Real-Time Active" 
              />
            </div>

            {status.error && (
              <div className="error-banner">
                <span className="error-icon">⚠️</span>
                {status.error === 'Failed to connect to RTMP stream' ? (
                  <div>
                    <strong>No RTMP Stream Detected</strong><br/>
                    Please start streaming from OBS to <code>rtmp://localhost:1935/live/test</code> and then click "Start Detection"
                  </div>
                ) : (
                  `Error: ${status.error}`
                )}
              </div>
            )}

            {status.rtmp === 'error' && !status.error && (
              <div className="message-banner warning">
                <span className="message-icon">📡</span>
                <div>
                  <strong>RTMP Stream Not Available</strong><br/>
                  No active stream detected. Please configure OBS to stream to <code>rtmp://localhost:1935/live/test</code>
                </div>
              </div>
            )}

            {status.rtmp === 'unknown' && (
              <div className="message-banner info">
                <span className="message-icon">ℹ️</span>
                <div>
                  <strong>Ready to Start</strong><br/>
                  Configure OBS to stream to <code>rtmp://localhost:1935/live/test</code> and click "Start Detection" to begin face recognition
                </div>
              </div>
            )}

            {startMsg && (
              <div className="message-banner success">
                <span className="message-icon">ℹ️</span>
                {startMsg}
              </div>
            )}

            {pimeyesTest && (
              <div className={`message-banner ${pimeyesTest.status === 'ok' ? 'success' : pimeyesTest.status === 'warning' ? 'warning' : 'error'}`}>
                <span className="message-icon">
                  {pimeyesTest.status === 'ok' ? '✅' : pimeyesTest.status === 'warning' ? '⚠️' : '❌'}
                </span>
                {pimeyesTest.message}
              </div>
            )}

            <div className="setup-instructions">
              <h2>🚀 Quick Setup</h2>
              <div className="instructions-grid">
                <div className="instruction-card">
                  <div className="instruction-number">1</div>
                  <h3>Start Stream</h3>
                  <p>Configure OBS to stream to <code>rtmp://localhost:1935/live/test</code></p>
                </div>
                <div className="instruction-card">
                  <div className="instruction-number">2</div>
                  <h3>Start Detection</h3>
                  <p>Click "Start Detection" to begin real-time face recognition</p>
                </div>
                <div className="instruction-card">
                  <div className="instruction-number">3</div>
                  <h3>Test PimEyes</h3>
                  <p>Click "Test PimEyes" to verify Selenium automation</p>
                </div>
                <div className="instruction-card">
                  <div className="instruction-number">4</div>
                  <h3>View Results</h3>
                  <p>Detected profiles will appear in the "Detected Profiles" tab</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'upload' && (
          <div className="upload-section">
            <div className="upload-card">
              <h2>📤 Upload Image for Reverse Search</h2>
              <form onSubmit={handleImageUpload} className="upload-form">
                <div className="file-input-wrapper">
                  <input 
                    type="file" 
                    name="image" 
                    accept="image/*" 
                    disabled={uploading}
                    className="file-input"
                    id="image-upload"
                  />
                  <label htmlFor="image-upload" className="file-input-label">
                    <span className="file-input-icon">📁</span>
                    Choose an image file
                  </label>
                </div>
                <button 
                  type="submit" 
                  disabled={uploading}
                  className={`btn btn-primary ${uploading ? 'loading' : ''}`}
                >
                  {uploading ? 'Uploading...' : 'Upload & Search'}
                </button>
              </form>
              
              {uploadMsg && (
                <div className="message-banner info">
                  <span className="message-icon">ℹ️</span>
                  {uploadMsg}
                </div>
              )}
            </div>

            {uploadedImage && (
              <div className="uploaded-image">
                <h3>Uploaded Image</h3>
                <img src={uploadedImage} alt="Uploaded" className="preview-image" />
              </div>
            )}

            {imageResults.length > 0 && (
              <div className="search-results">
                <h2>🔍 Reverse Image Search Results</h2>
                <div className="results-grid">
                  {imageResults.map((result, idx) => (
                    <div key={idx} className="result-card">
                      <h3>Match {idx + 1}</h3>
                      {result.image && (
                        <img src={result.image} alt="Match" className="result-image" />
                      )}
                      {result.summary && (
                        <p className="result-summary">{result.summary}</p>
                      )}
                      {result.links && result.links.length > 0 && (
                        <div className="result-links">
                          {result.links.map((link, i) => (
                            <a 
                              key={i} 
                              href={link.url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="result-link"
                            >
                              {link.label}
                            </a>
                          ))}
                        </div>
                      )}
                      {result.error && (
                        <span className="result-error">{result.error}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'profiles' && (
          <div className="profiles-section">
            {loading ? (
              <div className="loading-state">
                <div className="loading-spinner"></div>
                <p>Loading profiles...</p>
              </div>
            ) : profiles.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">👤</div>
                <h2>No faces detected yet</h2>
                <p>Start streaming from your Meta AI glasses and click "Start Detection" to begin live face recognition.</p>
              </div>
            ) : (
              <div className="profiles-content">
                <h2>👥 Real-Time Detected Profiles ({profiles.length})</h2>
                <div className="profiles-grid">
                  {profiles.map((profile, idx) => (
                    <div key={idx} className="profile-card">
                      <div className="profile-header">
                        <h3>Profile {idx + 1}</h3>
                        <span className="profile-timestamp">
                          {new Date().toLocaleTimeString()}
                        </span>
                      </div>
                      
                      {profile.summary && (
                        <div className="profile-summary">
                          <strong>Summary:</strong> {profile.summary}
                        </div>
                      )}
                      
                      {profile.pimeyes_results && profile.pimeyes_results.length > 0 && (
                        <div className="pimeyes-results">
                          <h4>🔍 PimEyes Results</h4>
                          <div className="pimeyes-grid">
                            {profile.pimeyes_results.map((result, i) => (
                              <div key={i} className="pimeyes-result">
                                {result.link && (
                                  <a 
                                    href={result.link} 
                                    target="_blank" 
                                    rel="noopener noreferrer"
                                    className="pimeyes-link"
                                  >
                                    View Result
                                  </a>
                                )}
                                {result.image && (
                                  <img 
                                    src={result.image} 
                                    alt="PimEyes result" 
                                    className="pimeyes-image" 
                                  />
                                )}
                                {result.error && (
                                  <span className="pimeyes-error">{result.error}</span>
                                )}
                                {result.note && (
                                  <span className="pimeyes-note">{result.note}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App; 