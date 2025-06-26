import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './App.css';

// Set backend URL from env, fallback to localhost
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

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
      const res = await axios.get(`${BACKEND_URL}/rtmp-profiles/`);
      setProfiles(res.data.profiles);
      setLoading(false);
    } catch (err) {
      setLoading(false);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/status/`);
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
      await axios.post(`${BACKEND_URL}/start-rtmp-processing/`);
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
      await axios.post(`${BACKEND_URL}/stop-rtmp-processing/`);
      setStartMsg('Real-time face detection stopped!');
      setTimeout(() => setStartMsg(''), 3000);
    } catch (err) {
      setStartMsg('Failed to stop real-time processing.');
      setTimeout(() => setStartMsg(''), 3000);
    }
    setProcessing(false);
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
      const res = await axios.post(`${BACKEND_URL}/upload-image/`, formData, {
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
        case 'ok': return 'bg-green-500';
        case 'error': return 'bg-red-500';
        case 'processing': return 'bg-yellow-400';
        case 'warning': return 'bg-yellow-400';
        default: return 'bg-gray-400';
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
      <div className="flex flex-col items-center justify-center bg-neutral-900 border border-neutral-800 rounded-2xl shadow-lg px-4 py-6 min-w-[150px] min-h-[120px] w-full max-w-xs mx-auto">
        <div className={`flex items-center justify-center w-10 h-10 rounded-full text-2xl font-bold mb-2 ${getStatusColor(status)}`}>{getStatusIcon(status)}</div>
        <div className="text-lg font-semibold text-white text-center break-words leading-tight mb-1">{label}</div>
        <div className="text-base text-neutral-400 text-center break-words">{status.charAt(0).toUpperCase() + status.slice(1)}</div>
      </div>
    );
  };

  const isProcessingActive = status.processing_active === 'true';

  // console.log("Profiles data:", profiles);
  return (
    <div className="min-h-screen bg-black text-white flex flex-col">
      <header className="sticky top-0 z-30 w-full bg-black border-b border-neutral-800">
        <div className="max-w-5xl mx-auto flex items-center justify-between px-4 py-3 sm:py-4">
          <h1 className="flex items-center gap-3 text-2xl font-bold tracking-tight">
            <span className="text-3xl">🤖</span>
            Meta AI Glasses
            <span className="hidden sm:inline text-base font-normal text-neutral-400 ml-2">Real-Time Face Recognition</span>
          </h1>
          <div>
            <button 
              className={`px-5 py-2 rounded-md font-semibold bg-white text-black hover:bg-neutral-100 transition disabled:opacity-60 ${processing ? 'opacity-60' : ''}`}
              onClick={isProcessingActive ? stopRTMPProcessing : startRTMPProcessing}
              disabled={processing}
            >
              {processing ? 'Processing...' : isProcessingActive ? 'Stop Detection' : 'Start Detection'}
            </button>
          </div>
        </div>
      </header>

      <nav className="sticky top-[56px] z-20 w-full bg-black border-b border-neutral-800">
        <div className="max-w-5xl mx-auto flex justify-center items-center gap-2 px-2 sm:px-4 overflow-x-auto">
          {[
            { tab: 'dashboard', icon: '📊', label: 'Dashboard' },
            { tab: 'upload', icon: '📤', label: 'Upload Image' },
            { tab: 'profiles', icon: '👥', label: 'Detected Profiles' },
          ].map(({ tab, icon, label }) => (
            <button
              key={tab}
              className={`whitespace-nowrap px-4 py-2 text-base font-medium rounded-lg transition-all duration-150 ${activeTab === tab ? 'bg-white text-black shadow font-semibold' : 'text-neutral-300 hover:text-white hover:bg-neutral-800'} mx-1`}
              onClick={() => setActiveTab(tab)}
            >
              <span className="mr-2">{icon}</span>{label}
            </button>
          ))}
        </div>
      </nav>

      <main className="flex-1 w-full max-w-5xl mx-auto px-4 sm:px-6 py-6">
        {activeTab === 'dashboard' && (
          <div className="space-y-8">
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
              <StatusIndicator status={status.rtmp} label="RTMP Stream" />
              <StatusIndicator status={status.backend} label="Backend" />
              <StatusIndicator status={status.selenium} label="Selenium/PimEyes" />
              <StatusIndicator 
                status={isProcessingActive ? 'ok' : 'unknown'} 
                label="Real-Time Active" 
              />
            </div>

            {status.error && (
              <div className="rounded-lg bg-red-900/80 border border-red-700 text-red-200 px-4 py-3 flex items-center gap-3 shadow">
                <span className="text-2xl">⚠️</span>
                <div className="flex-1 min-w-0">
                  {status.error === 'Failed to connect to RTMP stream' ? (
                    <div>
                      <strong>No RTMP Stream Detected</strong><br/>
                      <span className="break-all">Please start streaming from OBS to <code className="bg-black/40 px-1 rounded">rtmp://localhost:1935/live/test</code> and then click "Start Detection"</span>
                    </div>
                  ) : (
                    `Error: ${status.error}`
                  )}
                </div>
              </div>
            )}

            {status.rtmp === 'error' && !status.error && (
              <div className="rounded-lg bg-yellow-900/80 border border-yellow-700 text-yellow-200 px-4 py-3 flex items-center gap-3 shadow">
                <span className="text-2xl">📡</span>
                <div className="flex-1 min-w-0">
                  <strong>RTMP Stream Not Available</strong><br/>
                  <span className="break-all">No active stream detected. Please configure OBS to stream to <code className="bg-black/40 px-1 rounded">rtmp://localhost:1935/live/test</code></span>
                </div>
              </div>
            )}

            {status.rtmp === 'unknown' && (
              <div className="rounded-lg bg-blue-900/80 border border-blue-700 text-blue-200 px-4 py-3 flex items-center gap-3 shadow">
                <span className="text-2xl">ℹ️</span>
                <div className="flex-1 min-w-0">
                  <strong>Ready to Start</strong><br/>
                  <span className="break-all">Configure OBS to stream to <code className="bg-black/40 px-1 rounded">rtmp://localhost:1935/live/test</code> and click "Start Detection" to begin face recognition</span>
                </div>
              </div>
            )}

            {startMsg && (
              <div className="rounded-lg bg-green-900/80 border border-green-700 text-green-200 px-4 py-3 flex items-center gap-3 shadow">
                <span className="text-2xl">ℹ️</span>
                <span className="flex-1 min-w-0">{startMsg}</span>
              </div>
            )}

            <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 shadow-lg px-4 py-6">
              <h2 className="text-2xl font-semibold mb-6 flex items-center gap-2"><span>🚀</span> Quick Setup</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                <div className="rounded-xl bg-neutral-800/80 border border-neutral-700 p-5 flex flex-col gap-2 shadow">
                  <div className="flex items-center gap-2 mb-2"><span className="bg-blue-600 text-white rounded-full w-7 h-7 flex items-center justify-center font-bold">1</span><span className="font-semibold">Start Stream</span></div>
                  <div className="text-sm text-neutral-200">Configure OBS to stream to <span className="block break-all font-mono bg-black/40 px-1 rounded mt-1">rtmp://localhost:1935/live/test</span></div>
                </div>
                <div className="rounded-xl bg-neutral-800/80 border border-neutral-700 p-5 flex flex-col gap-2 shadow">
                  <div className="flex items-center gap-2 mb-2"><span className="bg-blue-600 text-white rounded-full w-7 h-7 flex items-center justify-center font-bold">2</span><span className="font-semibold">Start Detection</span></div>
                  <div className="text-sm text-neutral-200">Click "Start Detection" to begin real-time face recognition</div>
                </div>
                <div className="rounded-xl bg-neutral-800/80 border border-neutral-700 p-5 flex flex-col gap-2 shadow">
                  <div className="flex items-center gap-2 mb-2"><span className="bg-blue-600 text-white rounded-full w-7 h-7 flex items-center justify-center font-bold">3</span><span className="font-semibold">Test PimEyes</span></div>
                  <div className="text-sm text-neutral-200">Click "Test PimEyes" to verify Selenium automation</div>
                </div>
                <div className="rounded-xl bg-neutral-800/80 border border-neutral-700 p-5 flex flex-col gap-2 shadow">
                  <div className="flex items-center gap-2 mb-2"><span className="bg-blue-600 text-white rounded-full w-7 h-7 flex items-center justify-center font-bold">4</span><span className="font-semibold">View Results</span></div>
                  <div className="text-sm text-neutral-200">Detected profiles will appear in the "Detected Profiles" tab</div>
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
                      {profile.image && (
                        <div className="profile-image-wrapper">
                          <img src={profile.image} alt={`Face ${idx + 1}`} className="profile-image" />
                        </div>
                      )}
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