/**
 * Main App component for XToX Converter
 *
 * Provides LaTeX to PDF and Audio conversion functionality with
 * full accessibility support, keyboard navigation, and responsive design.
 *
 * TODO: Production enhancements:
 * - Add dark mode toggle
 * - Implement conversion progress tracking
 * - Add file preview before conversion
 * - Support batch file uploads
 * - Add conversion history view
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import './App.css';
import { conversionAPI } from './utils/apiClient';
import { AccessibleFileUpload } from './components/AccessibleFileUpload';
import { AccessibleAlert } from './components/AccessibleAlert';
import { ProgressBar } from './components/ProgressBar';
import { AuthStatus } from './components/AuthStatus';
import { MarketingPage } from './components/MarketingPage';
import { isMystiraOidcConfigured } from './auth/mystiraOidcConfig';

function App() {
  const [activeTab, setActiveTab] = useState('latex');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAuthReady, setIsAuthReady] = useState(false);

  const handleAuthChange = useCallback(authenticated => {
    setIsAuthenticated(authenticated);
  }, []);

  const handleAuthReady = useCallback(() => {
    setIsAuthReady(true);
  }, []);

  // LaTeX conversion state
  const [selectedFile, setSelectedFile] = useState(null);
  const [autoFix, setAutoFix] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [latexError, setLatexError] = useState(null);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef(null);

  // Audio conversion state
  const [selectedAudioFile, setSelectedAudioFile] = useState(null);
  const [targetFormat, setTargetFormat] = useState('mp3');
  const [bitrate, setBitrate] = useState('192k');
  const [sampleRate, setSampleRate] = useState(null);
  const [isProcessingAudio, setIsProcessingAudio] = useState(false);
  const [audioResult, setAudioResult] = useState(null);
  const [audioDragActive, setAudioDragActive] = useState(false);
  const [audioError, setAudioError] = useState(null);
  const [audioProgress, setAudioProgress] = useState(0);
  const audioFileInputRef = useRef(null);

  // Keyboard navigation for tabs
  useEffect(() => {
    const handleKeyDown = e => {
      if (e.key === 'ArrowLeft' && activeTab === 'audio') {
        e.preventDefault();
        setActiveTab('latex');
      } else if (e.key === 'ArrowRight' && activeTab === 'latex') {
        e.preventDefault();
        setActiveTab('audio');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeTab]);

  // LaTeX handlers
  const handleFileSelect = (file, error) => {
    if (error) {
      setLatexError(error);
      setSelectedFile(null);
      return;
    }

    if (file && file.name.endsWith('.tex')) {
      setSelectedFile(file);
      setResult(null);
      setLatexError(null);
    } else {
      setLatexError('Please select a .tex file');
      setSelectedFile(null);
    }
  };

  const handleDrag = e => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = e => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  // File input change handler - handled by AccessibleFileUpload component
  // Removed unused handler

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setResult(null);
    setLatexError(null);
    setProgress(0);

    // Simulate progress for better UX
    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 10;
      });
    }, 500);

    try {
      const response = await conversionAPI.convertLaTeX(selectedFile, autoFix);
      clearInterval(progressInterval);
      setProgress(100);
      setResult(response.data);
    } catch (error) {
      clearInterval(progressInterval);
      setProgress(0);
      const errorMessage =
        error.message || error.response?.data?.detail || 'Upload failed. Please try again.';
      setResult({
        success: false,
        errors: [errorMessage],
        warnings: [],
      });
      setLatexError(errorMessage);
    } finally {
      setIsProcessing(false);
      setTimeout(() => setProgress(0), 1000);
    }
  };

  const handleDownload = async () => {
    if (!result || !result.success) return;

    try {
      const response = await conversionAPI.downloadPDF(result.id);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${result.filename}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      const errorMessage = error.message || 'Failed to download PDF. Please try again.';
      setLatexError(errorMessage);
      setResult({
        ...result,
        success: false,
        errors: [...(result.errors || []), errorMessage],
      });
    }
  };

  const resetForm = () => {
    setSelectedFile(null);
    setResult(null);
    setAutoFix(false);
    setLatexError(null);
    setProgress(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Audio conversion handlers
  const handleAudioFileSelect = (file, error) => {
    if (error) {
      setAudioError(error);
      setSelectedAudioFile(null);
      return;
    }

    const audioExtensions = ['.ogg', '.opus', '.mp3', '.wav', '.m4a', '.aac', '.flac'];
    const fileExt = '.' + file.name.split('.').pop().toLowerCase();
    if (audioExtensions.includes(fileExt)) {
      setSelectedAudioFile(file);
      setAudioResult(null);
      setAudioError(null);
    } else {
      setAudioError('Please select an audio file (.ogg, .opus, .mp3, .wav, .m4a, .aac, .flac)');
      setSelectedAudioFile(null);
    }
  };

  const handleAudioDrag = e => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setAudioDragActive(true);
    } else if (e.type === 'dragleave') {
      setAudioDragActive(false);
    }
  };

  const handleAudioDrop = e => {
    e.preventDefault();
    e.stopPropagation();
    setAudioDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleAudioFileSelect(e.dataTransfer.files[0]);
    }
  };

  // Audio file input change handler - handled by AccessibleFileUpload component
  // Removed unused handler

  const handleAudioUpload = async () => {
    if (!selectedAudioFile) return;

    setIsProcessingAudio(true);
    setAudioResult(null);
    setAudioError(null);
    setAudioProgress(0);

    // Simulate progress
    const progressInterval = setInterval(() => {
      setAudioProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 10;
      });
    }, 500);

    try {
      const response = await conversionAPI.convertAudio(
        selectedAudioFile,
        targetFormat,
        bitrate,
        sampleRate
      );
      clearInterval(progressInterval);
      setAudioProgress(100);
      setAudioResult({ ...response.data, operation: 'conversion' });
    } catch (error) {
      clearInterval(progressInterval);
      setAudioProgress(0);
      const errorMessage =
        error.message || error.response?.data?.detail || 'Upload failed. Please try again.';
      setAudioResult({
        success: false,
        operation: 'conversion',
        errors: [errorMessage],
        warnings: [],
      });
      setAudioError(errorMessage);
    } finally {
      setIsProcessingAudio(false);
      setTimeout(() => setAudioProgress(0), 1000);
    }
  };

  const handleAudioTranscription = async () => {
    if (!selectedAudioFile) return;

    setIsProcessingAudio(true);
    setAudioResult(null);
    setAudioError(null);
    setAudioProgress(0);

    const progressInterval = setInterval(() => {
      setAudioProgress(prev => {
        if (prev >= 90) {
          clearInterval(progressInterval);
          return 90;
        }
        return prev + 10;
      });
    }, 500);

    try {
      const response = await conversionAPI.transcribeAudio(selectedAudioFile);
      clearInterval(progressInterval);
      setAudioProgress(100);
      setAudioResult({ ...response.data, operation: 'transcription' });
    } catch (error) {
      clearInterval(progressInterval);
      setAudioProgress(0);
      const errorMessage =
        error.message || error.response?.data?.detail || 'Transcription failed. Please try again.';
      setAudioResult({
        success: false,
        operation: 'transcription',
        errors: [errorMessage],
        warnings: [],
      });
      setAudioError(errorMessage);
    } finally {
      setIsProcessingAudio(false);
      setTimeout(() => setAudioProgress(0), 1000);
    }
  };

  const handleAudioDownload = async () => {
    if (!audioResult || !audioResult.success) return;

    try {
      const response = await conversionAPI.downloadAudio(audioResult.id);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${audioResult.filename}.${audioResult.target_format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      const errorMessage = error.message || 'Failed to download audio. Please try again.';
      setAudioError(errorMessage);
      setAudioResult({
        ...audioResult,
        success: false,
        errors: [...(audioResult.errors || []), errorMessage],
      });
    }
  };

  const resetAudioForm = () => {
    setSelectedAudioFile(null);
    setAudioResult(null);
    setTargetFormat('mp3');
    setBitrate('192k');
    setSampleRate(null);
    setAudioError(null);
    setAudioProgress(0);
    if (audioFileInputRef.current) {
      audioFileInputRef.current.value = '';
    }
  };

  const authControl = (
    <AuthStatus
      onAuthChange={handleAuthChange}
      onAuthReady={handleAuthReady}
      variant={isAuthenticated ? 'workspace' : 'landing'}
    />
  );

  if (!isAuthenticated) {
    return (
      <MarketingPage
        authControl={authControl}
        checkingSession={!isAuthReady}
        oidcConfigured={isMystiraOidcConfigured()}
      />
    );
  }

  return (
    <div className="workspace-page">
      {/* Skip to main content link for screen readers */}
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <div className="workspace-shell">
        <header className="workspace-header">
          <a className="marketing-wordmark" href="/" aria-label="XtOX workspace home">
            <img className="wordmark-icon" src="/xtox-mark.svg" alt="" aria-hidden="true" />
            <span>XtOX</span>
          </a>
          <div className="workspace-heading">
            <p>Private document workbench</p>
            <h1>Choose a transformation.</h1>
          </div>
          <div className="workspace-account">{authControl}</div>
        </header>

        <main id="main-content" className="workspace-main">
          {/* Tab Navigation */}
          <div className="workspace-tabs" role="tablist" aria-label="Conversion type selection">
            <div className="workspace-tab-row">
              <button
                role="tab"
                aria-selected={activeTab === 'latex'}
                aria-controls="latex-panel"
                id="latex-tab"
                onClick={() => setActiveTab('latex')}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setActiveTab('latex');
                  }
                }}
                className={`workspace-tab ${activeTab === 'latex' ? 'is-active' : ''}`}
              >
                <span className="workspace-tab-type">.TEX → .PDF</span>
                <span>Document</span>
              </button>
              <button
                role="tab"
                aria-selected={activeTab === 'audio'}
                aria-controls="audio-panel"
                id="audio-tab"
                onClick={() => setActiveTab('audio')}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setActiveTab('audio');
                  }
                }}
                className={`workspace-tab ${activeTab === 'audio' ? 'is-active' : ''}`}
              >
                <span className="workspace-tab-type">AUDIO → AUDIO / TEXT</span>
                <span>Voice</span>
              </button>
            </div>
          </div>

          {/* LaTeX Conversion Tab */}
          {activeTab === 'latex' && (
            <div role="tabpanel" id="latex-panel" aria-labelledby="latex-tab">
              <div className="workspace-panel bg-white rounded-b-xl shadow-lg p-4 sm:p-8 mb-8">
                <div className="panel-heading">
                  <span className="panel-index">01</span>
                  <div>
                    <h2 className="text-2xl font-semibold text-gray-800">Typeset a document</h2>
                    <p>Bring the source. XtOX returns a shareable PDF.</p>
                  </div>
                </div>

                <AccessibleFileUpload
                  accept=".tex"
                  maxSize={10 * 1024 * 1024}
                  onFileSelect={handleFileSelect}
                  label={
                    selectedFile
                      ? selectedFile.name
                      : 'Drop your .tex file here, or click to browse'
                  }
                  description="Maximum file size: 10MB"
                  error={latexError}
                  disabled={isProcessing}
                  dragActive={dragActive}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                />

                <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                  <label className="flex items-center space-x-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoFix}
                      onChange={e => setAutoFix(e.target.checked)}
                      className="w-5 h-5 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
                      aria-label="Enable auto-fix for common LaTeX errors"
                    />
                    <div>
                      <span className="text-sm font-medium text-gray-700">
                        Auto-fix common LaTeX errors
                      </span>
                      <p className="text-xs text-gray-500 mt-1">
                        Automatically add missing documentclass, begin/end document if needed
                      </p>
                    </div>
                  </label>
                </div>

                {isProcessing && (
                  <div className="mt-6">
                    <ProgressBar
                      value={progress}
                      label="Conversion Progress"
                      ariaLabel="LaTeX to PDF conversion progress"
                    />
                  </div>
                )}

                <div className="mt-6 text-center">
                  <button
                    onClick={handleUpload}
                    disabled={!selectedFile || isProcessing || !isAuthenticated}
                    aria-busy={isProcessing}
                    aria-live="polite"
                    className={`px-8 py-3 rounded-lg font-medium text-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                      !selectedFile || isProcessing || !isAuthenticated
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : 'bg-green-600 text-white hover:bg-green-700 shadow-lg hover:shadow-xl'
                    }`}
                  >
                    {isProcessing ? (
                      <span className="flex items-center justify-center">
                        <svg
                          className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          aria-hidden="true"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          ></circle>
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                          ></path>
                        </svg>
                        Converting...
                      </span>
                    ) : isAuthenticated ? (
                      'Convert to PDF'
                    ) : (
                      'Sign in to convert'
                    )}
                  </button>
                </div>
              </div>

              {result && (
                <div
                  className="workspace-result bg-white rounded-xl shadow-lg p-4 sm:p-8 mt-8"
                  role="region"
                  aria-live="polite"
                  aria-label="Conversion results"
                >
                  <h2 className="text-2xl font-semibold text-gray-800 mb-6">Conversion Results</h2>

                  {result.success ? (
                    <div className="text-center">
                      <AccessibleAlert
                        type="success"
                        title="Conversion Successful!"
                        message={
                          result.auto_fix_applied
                            ? 'Auto-fix was applied to your LaTeX file'
                            : undefined
                        }
                      />

                      <div className="mt-6 button-group flex flex-col sm:flex-row justify-center gap-4">
                        <button
                          onClick={handleDownload}
                          className="bg-blue-600 text-white px-8 py-3 rounded-lg hover:bg-blue-700 transition-colors duration-200 font-medium text-lg shadow-lg hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                          aria-label="Download converted PDF file"
                        >
                          Download PDF
                        </button>

                        <button
                          onClick={resetForm}
                          className="bg-gray-600 text-white px-8 py-3 rounded-lg hover:bg-gray-700 transition-colors duration-200 font-medium text-lg focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
                          aria-label="Convert another LaTeX file"
                        >
                          Convert Another File
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <AccessibleAlert
                        type="error"
                        title="Conversion Failed"
                        message="Please review the errors below and try again."
                        items={result.errors || []}
                      />

                      {result.warnings && result.warnings.length > 0 && (
                        <div className="mt-4">
                          <AccessibleAlert
                            type="warning"
                            title="Warnings"
                            items={result.warnings}
                          />
                        </div>
                      )}

                      <div className="text-center mt-6">
                        <button
                          onClick={resetForm}
                          className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors duration-200 font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                          aria-label="Try LaTeX conversion again"
                        >
                          Try Again
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Audio Conversion Tab */}
          {activeTab === 'audio' && (
            <div role="tabpanel" id="audio-panel" aria-labelledby="audio-tab">
              <div className="workspace-panel bg-white rounded-b-xl shadow-lg p-4 sm:p-8">
                <div className="panel-heading">
                  <span className="panel-index">02</span>
                  <div>
                    <h2 className="text-2xl font-semibold text-gray-800">
                      Convert or transcribe audio
                    </h2>
                    <p>
                      Reshape a voice note, or receive its words without retaining the transcript.
                    </p>
                  </div>
                </div>

                <AccessibleFileUpload
                  accept=".ogg,.opus,.mp3,.wav,.m4a,.aac,.flac"
                  maxSize={50 * 1024 * 1024}
                  onFileSelect={handleAudioFileSelect}
                  label={
                    selectedAudioFile
                      ? selectedAudioFile.name
                      : 'Drop your audio file here, or click to browse'
                  }
                  description="Supported: OGG, Opus, MP3, WAV, M4A, AAC, FLAC (Max: 50MB)"
                  error={audioError}
                  disabled={isProcessingAudio}
                  dragActive={audioDragActive}
                  onDragEnter={handleAudioDrag}
                  onDragLeave={handleAudioDrag}
                  onDragOver={handleAudioDrag}
                  onDrop={handleAudioDrop}
                />

                {selectedAudioFile && (
                  <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                    <h3 className="text-lg font-medium text-gray-800 mb-4">
                      Conversion Settings (Convert Audio only)
                    </h3>

                    <div className="mb-4">
                      <label
                        htmlFor="targetFormat"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Target Format
                      </label>
                      <select
                        id="targetFormat"
                        value={targetFormat}
                        onChange={e => setTargetFormat(e.target.value)}
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:outline-none"
                        aria-label="Select target audio format"
                      >
                        <option value="mp3">MP3</option>
                        <option value="wav">WAV</option>
                        <option value="ogg">OGG</option>
                        <option value="m4a">M4A</option>
                        <option value="aac">AAC</option>
                        <option value="flac">FLAC</option>
                      </select>
                    </div>

                    <div className="mb-4">
                      <label
                        htmlFor="bitrate"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Bitrate
                      </label>
                      <select
                        id="bitrate"
                        value={bitrate}
                        onChange={e => setBitrate(e.target.value)}
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:outline-none"
                        aria-label="Select audio bitrate"
                      >
                        <option value="128k">128 kbps (Smaller file)</option>
                        <option value="192k">192 kbps (Recommended)</option>
                        <option value="256k">256 kbps (High quality)</option>
                        <option value="320k">320 kbps (Best quality)</option>
                      </select>
                    </div>

                    <div className="mb-4">
                      <label
                        htmlFor="sampleRate"
                        className="block text-sm font-medium text-gray-700 mb-2"
                      >
                        Sample Rate (Optional)
                      </label>
                      <input
                        id="sampleRate"
                        type="number"
                        value={sampleRate || ''}
                        onChange={e =>
                          setSampleRate(e.target.value ? parseInt(e.target.value) : null)
                        }
                        placeholder="e.g., 44100"
                        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 focus:outline-none"
                        aria-label="Optional sample rate in Hz"
                        min="8000"
                        max="192000"
                        step="1000"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Leave empty to use original sample rate
                      </p>
                    </div>
                  </div>
                )}

                {isProcessingAudio && (
                  <div className="mt-6">
                    <ProgressBar
                      value={audioProgress}
                      label="Audio Processing Progress"
                      ariaLabel="Audio processing progress"
                    />
                  </div>
                )}

                <div className="mt-6 flex flex-col justify-center gap-4 text-center sm:flex-row">
                  <button
                    onClick={handleAudioUpload}
                    disabled={!selectedAudioFile || isProcessingAudio || !isAuthenticated}
                    aria-busy={isProcessingAudio}
                    aria-live="polite"
                    className={`px-8 py-3 rounded-lg font-medium text-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                      !selectedAudioFile || isProcessingAudio || !isAuthenticated
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : 'bg-green-600 text-white hover:bg-green-700 shadow-lg hover:shadow-xl'
                    }`}
                  >
                    {isProcessingAudio ? (
                      <span className="flex items-center justify-center">
                        <svg
                          className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          aria-hidden="true"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          ></circle>
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                          ></path>
                        </svg>
                        Processing...
                      </span>
                    ) : isAuthenticated ? (
                      'Convert Audio'
                    ) : (
                      'Sign in to continue'
                    )}
                  </button>
                  <button
                    onClick={handleAudioTranscription}
                    disabled={!selectedAudioFile || isProcessingAudio || !isAuthenticated}
                    aria-busy={isProcessingAudio}
                    className={`px-8 py-3 rounded-lg font-medium text-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                      !selectedAudioFile || isProcessingAudio || !isAuthenticated
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-lg hover:shadow-xl'
                    }`}
                  >
                    {isProcessingAudio
                      ? 'Processing...'
                      : isAuthenticated
                        ? 'Transcribe Audio'
                        : 'Sign in to continue'}
                  </button>
                </div>
              </div>

              {/* Audio Conversion Results */}
              {audioResult && (
                <div
                  className="workspace-result bg-white rounded-xl shadow-lg p-4 sm:p-8 mt-8"
                  role="region"
                  aria-live="polite"
                  aria-label="Audio processing results"
                >
                  <h2 className="text-2xl font-semibold text-gray-800 mb-6">
                    {audioResult.operation === 'transcription'
                      ? 'Transcription Results'
                      : 'Conversion Results'}
                  </h2>

                  {audioResult.success ? (
                    <div className="text-center">
                      <AccessibleAlert
                        type="success"
                        title={
                          audioResult.operation === 'transcription'
                            ? 'Transcription Successful!'
                            : 'Conversion Successful!'
                        }
                        message={
                          audioResult.operation === 'transcription'
                            ? audioResult.language
                              ? `Detected language: ${audioResult.language}`
                              : 'Your transcript is ready.'
                            : `Converted to ${audioResult.target_format.toUpperCase()}`
                        }
                      />

                      {audioResult.operation === 'transcription' && audioResult.text && (
                        <div className="mt-6 rounded-lg bg-gray-50 p-4 text-left">
                          <h3 className="mb-2 text-sm font-semibold text-gray-800">Transcript</h3>
                          <p className="whitespace-pre-wrap text-gray-700">{audioResult.text}</p>
                        </div>
                      )}

                      {(audioResult.duration || audioResult.file_size_kb) && (
                        <div className="mt-4 text-sm text-gray-600">
                          {audioResult.duration && (
                            <p>Duration: {Math.round(audioResult.duration)}s</p>
                          )}
                          {audioResult.file_size_kb && (
                            <p>File size: {audioResult.file_size_kb.toFixed(2)} KB</p>
                          )}
                        </div>
                      )}

                      <div className="mt-6 button-group flex flex-col sm:flex-row justify-center gap-4">
                        {audioResult.operation !== 'transcription' && (
                          <button
                            onClick={handleAudioDownload}
                            className="bg-blue-600 text-white px-8 py-3 rounded-lg hover:bg-blue-700 transition-colors duration-200 font-medium text-lg shadow-lg hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                            aria-label={`Download converted ${audioResult.target_format.toUpperCase()} file`}
                          >
                            Download {audioResult.target_format.toUpperCase()}
                          </button>
                        )}

                        <button
                          onClick={resetAudioForm}
                          className="bg-gray-600 text-white px-8 py-3 rounded-lg hover:bg-gray-700 transition-colors duration-200 font-medium text-lg focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
                          aria-label="Convert another audio file"
                        >
                          Process Another File
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <AccessibleAlert
                        type="error"
                        title={
                          audioResult.operation === 'transcription'
                            ? 'Transcription Failed'
                            : 'Conversion Failed'
                        }
                        message="Please review the errors below and try again."
                        items={audioResult.errors || []}
                      />

                      <div className="text-center mt-6">
                        <button
                          onClick={resetAudioForm}
                          className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors duration-200 font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                          aria-label="Try audio conversion again"
                        >
                          Try Again
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
