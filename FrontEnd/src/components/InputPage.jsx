import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './InputPage.css';

const InputPage = () => {
    // State declarations
    const [sourceLang, setSourceLang] = useState('English (US)');
    const [useAiDetection, setUseAiDetection] = useState(true);
    const [uploadedVideo, setUploadedVideo] = useState(null);
    const [videoUrl, setVideoUrl] = useState('');
    const [selectedLanguages, setSelectedLanguages] = useState(['es', 'fr', 'de']);
    const [isDragging, setIsDragging] = useState(false);
    const [processingProgress, setProcessingProgress] = useState(0);
    const [isProcessing, setIsProcessing] = useState(false);
    const [speakerMappings, setSpeakerMappings] = useState([
        { id: 1, name: 'Speaker 1', gender: 'Female', targetLang: 'es', voiceClone: false },
        { id: 2, name: 'Speaker 2', gender: 'Male', targetLang: 'de', voiceClone: false }
    ]);
    const [toneSettings, setToneSettings] = useState({
        serious: 0,
        genre: 0,
        speed: 0,
        pitch: 0
    });
    const [glossaryFile, setGlossaryFile] = useState(null);
    const [currentPage, setCurrentPage] = useState(1);
    const [uploadProgress, setUploadProgress] = useState({});

    const fileInputRef = useRef(null);
    const dropZoneRef = useRef(null);
    const navigate = useNavigate();

    // Mock data for languages with more properties - Added more languages
    const languages = [
        { code: 'es', name: 'Spanish LATAM', flag: '🇪🇸', progress: '93.7%', selected: false },
        { code: 'fr', name: 'French', flag: '🇫🇷', progress: '93.7%', selected: false },
        { code: 'de', name: 'German', flag: '🇩🇪', progress: '99.7%', selected: false },
        { code: 'ta', name: 'Tamil', flag: '🇮🇳', progress: '92.5%', selected: false },
        { code: 'hi', name: 'Hindi', flag: '🇮🇳', progress: '91.4%', selected: false },
        { code: 'zh', name: 'Mandarin', flag: '🇨🇳', progress: '96.5%', selected: false },
        { code: 'ja', name: 'Japanese', flag: '🇯🇵', progress: '92.8%', selected: false },
        { code: 'ko', name: 'Korean', flag: '🇰🇷', progress: '89.3%', selected: false },
        { code: 'ar', name: 'Arabic', flag: '🇸🇦', progress: '88.7%', selected: false },
        { code: 'ru', name: 'Russian', flag: '🇷🇺', progress: '94.1%', selected: false },
        { code: 'pt', name: 'Portuguese', flag: '🇵🇹', progress: '95.1%', selected: false },
        { code: 'it', name: 'Italian', flag: '🇮🇹', progress: '94.2%', selected: false },
        { code: 'nl', name: 'Dutch', flag: '🇳🇱', progress: '90.5%', selected: false },
        { code: 'pl', name: 'Polish', flag: '🇵🇱', progress: '87.9%', selected: false },
        { code: 'tr', name: 'Turkish', flag: '🇹🇷', progress: '86.4%', selected: false },
        { code: 'th', name: 'Thai', flag: '🇹🇭', progress: '85.2%', selected: false },
        { code: 'vi', name: 'Vietnamese', flag: '🇻🇳', progress: '84.8%', selected: false },
        { code: 'he', name: 'Hebrew', flag: '🇮🇱', progress: '83.6%', selected: false },
        { code: 'sv', name: 'Swedish', flag: '🇸🇪', progress: '89.1%', selected: false },
        { code: 'da', name: 'Danish', flag: '🇩🇰', progress: '88.7%', selected: false },
        { code: 'fi', name: 'Finnish', flag: '🇫🇮', progress: '82.3%', selected: false },
        { code: 'no', name: 'Norwegian', flag: '🇳🇴', progress: '87.5%', selected: false },
        { code: 'cs', name: 'Czech', flag: '🇨🇿', progress: '81.9%', selected: false },
        { code: 'hu', name: 'Hungarian', flag: '🇭🇺', progress: '80.4%', selected: false },
        { code: 'el', name: 'Greek', flag: '🇬🇷', progress: '79.8%', selected: false },
        { code: 'ro', name: 'Romanian', flag: '🇷🇴', progress: '78.6%', selected: false },
        { code: 'bg', name: 'Bulgarian', flag: '🇧🇬', progress: '77.2%', selected: false },
    ];

    // Calculate total pages
    const languagesPerPage = 9;
    const totalPages = Math.ceil(languages.length / languagesPerPage);

    // Get languages for current page
    const paginatedLanguages = languages.slice(
        (currentPage - 1) * languagesPerPage,
        currentPage * languagesPerPage
    );

    // Simplified platform icons - Only YouTube + plus for others
    const platforms = [
        {
            name: 'YouTube', color: 'bg-red-100', icon: (
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="#FF0000" viewBox="0 0 24 24">
                    <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z" />
                </svg>
            )
        },
        { name: '+12 More', color: 'bg-gray-100', icon: '+', isPlus: true }
    ];

    // Drag and drop handlers
    const handleDragEnter = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!dropZoneRef.current.contains(e.relatedTarget)) {
            setIsDragging(false);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = 'copy';
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);

        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleFileUpload(files[0]);
        }
    };

    const handleFileUpload = (file) => {
        // More robust file type checking
        const validVideoTypes = [
            'video/mp4', 'video/webm', 'video/ogg',
            'video/quicktime', 'video/x-msvideo',
            'video/x-matroska', 'application/x-troff-msvideo',
            'video/avi', 'video/mpeg'
        ];

        const validExtensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.mpg', '.mpeg'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();

        // Check if mime type is video OR if extension is valid video extension
        const isValidType = file.type.startsWith('video/') || validVideoTypes.includes(file.type);
        const isValidExtension = validExtensions.includes(fileExtension);

        if (!isValidType && !isValidExtension) {
            alert(`Please upload a valid video file. Detected type: ${file.type || 'unknown'}`);
            return;
        }

        // Simulate upload progress
        setUploadProgress({ [file.name]: 0 });
        simulateUploadProgress(file.name);

        const videoData = {
            name: file.name,
            size: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
            type: file.type || 'video/unknown',
            thumbnail: URL.createObjectURL(file), // Creates a preview URL for the video
            duration: '0 mins', // Placeholder as we can't easily get duration without processing
            confidence: '95.7%',
            lang: 'EN-US'
        };

        // Try to get actual video duration if possible (optional enhancement)
        const videoElement = document.createElement('video');
        videoElement.preload = 'metadata';
        videoElement.onloadedmetadata = function () {
            window.URL.revokeObjectURL(videoElement.src);
            const duration = Math.round(videoElement.duration / 60) + ' mins';
            setUploadedVideo(prev => ({ ...prev, duration: duration }));
        }
        videoElement.src = URL.createObjectURL(file);

        setUploadedVideo(videoData);
    };

    const simulateUploadProgress = (fileName) => {
        let progress = 0;
        const interval = setInterval(() => {
            progress += 5;
            setUploadProgress(prev => ({ ...prev, [fileName]: progress }));

            if (progress >= 100) {
                clearInterval(interval);
            }
        }, 100);
    };

    const handleFileInput = (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    };

    // Language selection handler
    const handleLanguageSelect = (code) => {
        setSelectedLanguages(prev => {
            if (prev.includes(code)) {
                return prev.filter(lang => lang !== code);
            } else {
                return [...prev, code];
            }
        });
    };

    // Voice clone toggle
    const toggleVoiceClone = (speakerId) => {
        setSpeakerMappings(prev =>
            prev.map(speaker =>
                speaker.id === speakerId
                    ? { ...speaker, voiceClone: !speaker.voiceClone }
                    : speaker
            )
        );
    };

    // Tone setting handler
    const handleToneChange = (setting, value) => {
        setToneSettings(prev => ({
            ...prev,
            [setting]: parseInt(value)
        }));
    };

    // Reset tone settings to 0
    const resetToneSettings = () => {
        setToneSettings({
            serious: 0,
            genre: 0,
            speed: 0,
            pitch: 0
        });
    };

    // Glossary file handler
    const handleGlossaryUpload = (e) => {
        const file = e.target.files[0];
        if (file && file.type === 'text/csv') {
            setGlossaryFile({
                name: file.name,
                size: (file.size / 1024).toFixed(2) + ' KB',
                terms: Math.floor(Math.random() * 50) + 10 // Random term count
            });
        } else {
            alert('Please upload a CSV file');
        }
    };

    // URL processing
    const processUrl = () => {
        if (!videoUrl) return;

        // Validate URL
        const urlPattern = /^(https?:\/\/)?(www\.)?(youtube\.com|vimeo\.com|bilibili\.com)\/.+/i;
        if (!urlPattern.test(videoUrl)) {
            alert('Please enter a valid YouTube, Vimeo, or Bilibili URL');
            return;
        }

        // Simulate video analysis
        setIsProcessing(true);
        setProcessingProgress(0);

        const progressInterval = setInterval(() => {
            setProcessingProgress(prev => {
                if (prev >= 100) {
                    clearInterval(progressInterval);
                    setIsProcessing(false);

                    // Set mock video data
                    setUploadedVideo({
                        name: 'Video from URL',
                        size: '15.3 MB',
                        type: 'video/mp4',
                        thumbnail: 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?auto=format&fit=crop&w=100&q=80',
                        duration: '5 mins',
                        confidence: '98.2%',
                        lang: 'EN-US',
                        source: 'url'
                    });

                    return 100;
                }
                return prev + 10;
            });
        }, 200);
    };

    // Generate video handler
    const handleGenerateVideo = () => {
        if (!uploadedVideo && !videoUrl) {
            alert('Please upload a video or enter a URL');
            return;
        }

        if (selectedLanguages.length === 0) {
            alert('Please select at least one target language');
            return;
        }

        setIsProcessing(true);
        setProcessingProgress(0);

        // Simulate generation process
        const interval = setInterval(() => {
            setProcessingProgress(prev => {
                const newProgress = prev + Math.random() * 15;
                if (newProgress >= 100) {
                    clearInterval(interval);
                    setIsProcessing(false);

                    // Reset tone settings to 0 after successful generation
                    resetToneSettings();

                    // Navigate to preview page with video data
                    navigate('/preview', {
                        state: {
                            video: uploadedVideo,
                            languages: selectedLanguages
                        }
                    });

                    return 100;
                }
                return newProgress;
            });
        }, 500);
    };

    // Calculate estimated time
    const calculateEstimatedTime = () => {
        const baseTime = 3.2; // minutes
        const languageFactor = selectedLanguages.length * 0.5;
        const speakerFactor = speakerMappings.filter(s => s.voiceClone).length * 0.8;
        return (baseTime + languageFactor + speakerFactor).toFixed(2);
    };

    // Remove uploaded video
    const removeVideo = () => {
        setUploadedVideo(null);
        setVideoUrl('');
        setUploadProgress({});
    };

    // Get language name by code
    const getLanguageName = (code) => {
        const lang = languages.find(l => l.code === code);
        return lang ? lang.name : code;
    };

    // Remove a selected language
    const removeSelectedLanguage = (code) => {
        setSelectedLanguages(prev => prev.filter(lang => lang !== code));
    };

    // Pagination handlers
    const nextPage = () => {
        if (currentPage < totalPages) {
            setCurrentPage(prev => prev + 1);
        }
    };

    const prevPage = () => {
        if (currentPage > 1) {
            setCurrentPage(prev => prev - 1);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 text-gray-800 font-sans selection:bg-blue-100 p-4 md:p-8 flex flex-col items-center">
            {/* Header */}
            <header className="flex items-center gap-3 mb-8 animate-fade-in">
                <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-blue-500 to-purple-600 flex items-center justify-center p-0.5 shadow-lg shadow-blue-200 animate-pulse-slow">
                    <div className="w-full h-full bg-white rounded-full flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                        </svg>
                    </div>
                </div>
                <h1 className="text-2xl font-bold tracking-wide bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent uppercase">
                    Global Voice Engine
                </h1>
                {isProcessing && (
                    <div className="ml-4 px-3 py-1 bg-gradient-to-r from-blue-500 to-purple-500 text-white text-xs font-bold rounded-full animate-pulse">
                        PROCESSING {processingProgress.toFixed(0)}%
                    </div>
                )}
            </header>

            {/* Main Grid */}
            <div className="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Column 1: Source Upload */}
                <div className="bg-white rounded-3xl p-6 shadow-xl shadow-gray-200/50 border border-gray-100 flex flex-col h-full relative overflow-hidden group transition-all duration-300 hover:shadow-2xl hover:shadow-blue-100/50">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-400 to-purple-400"></div>

                    <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-6 text-center">Source Upload</h2>

                    {/* Drag & Drop Area */}
                    <div
                        ref={dropZoneRef}
                        className={`flex-1 flex flex-col items-center justify-center mb-6 transition-all duration-300 ${isDragging ? 'scale-105' : ''}`}
                        onDragEnter={handleDragEnter}
                        onDragLeave={handleDragLeave}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                    >
                        <div
                            className={`relative w-48 h-48 rounded-full border-4 border-dashed flex flex-col items-center justify-center p-4 transition-all duration-300 cursor-pointer ${isDragging
                                ? 'border-blue-500 bg-blue-50 scale-110'
                                : 'border-gray-200 bg-gray-50 hover:border-blue-400 hover:bg-blue-50/30'
                                }`}
                            onClick={() => fileInputRef.current?.click()}
                        >
                            {isDragging && (
                                <div className="absolute inset-0 rounded-full bg-blue-500/10 animate-pulse pointer-events-none"></div>
                            )}
                            <div className="absolute inset-0 rounded-full border-t-4 border-blue-500 opacity-20 animate-spin-slow pointer-events-none"></div>
                            <svg xmlns="http://www.w3.org/2000/svg" className={`w-12 h-12 mb-2 transition-colors ${isDragging ? 'text-blue-600' : 'text-blue-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                            <span className={`text-center font-bold transition-colors ${isDragging ? 'text-blue-700' : 'text-gray-700'}`}>DRAG & DROP</span>
                            <span className="text-center text-xs text-gray-400 mt-1">VIDEO FILES</span>
                            <input
                                type="file"
                                ref={fileInputRef}
                                className="hidden"
                                accept="video/*"
                                onChange={handleFileInput}
                            />
                        </div>
                        <p className="text-xs text-gray-500 mt-4 text-center">Supports MP4, MOV, AVI up to 2GB</p>
                    </div>

                    {/* URL Input */}
                    <div className="mb-6">
                        <div className="relative">
                            <input
                                type="text"
                                value={videoUrl}
                                onChange={(e) => setVideoUrl(e.target.value)}
                                placeholder="Paste Video URL (YouTube, Vimeo, Bilibili)"
                                className="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all pr-24"
                            />
                            <button
                                onClick={processUrl}
                                disabled={!videoUrl || isProcessing}
                                className={`absolute right-2 top-1/2 transform -translate-y-1/2 px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${!videoUrl || isProcessing
                                    ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                                    : 'bg-blue-500 text-white hover:bg-blue-600 active:scale-95'
                                    }`}
                            >
                                {isProcessing ? 'Processing...' : 'Fetch'}
                            </button>
                        </div>
                    </div>

                    {/* Icons Row - Simplified */}
                    <div className="flex justify-center gap-4 mb-6">
                        {platforms.map((platform, idx) => (
                            <div
                                key={platform.name}
                                className={`w-8 h-8 rounded-full flex items-center justify-center cursor-pointer transition-transform hover:scale-110 ${platform.color} ${platform.isPlus ? 'text-gray-600' : ''}`}
                                title={platform.name}
                                onClick={() => !platform.isPlus && setVideoUrl(`https://${platform.name.toLowerCase()}.com/example`)}
                            >
                                {platform.isPlus ? (
                                    <span className="text-xs font-bold">{platform.icon}</span>
                                ) : (
                                    platform.icon
                                )}
                            </div>
                        ))}
                    </div>

                    {/* Uploaded Video Card or Placeholder */}
                    {uploadedVideo ? (
                        <div className="bg-gray-50 border border-gray-100 rounded-xl p-3 flex items-center gap-3 animate-slide-up">
                            <div className="relative">
                                <div className="w-12 h-12 bg-gray-200 rounded-lg overflow-hidden flex-shrink-0">
                                    <img src={uploadedVideo.thumbnail} alt="Video thumb" className="w-full h-full object-cover" />
                                </div>
                                {uploadProgress[uploadedVideo.name] && uploadProgress[uploadedVideo.name] < 100 ? (
                                    <div className="absolute -bottom-1 left-0 right-0 h-1 bg-gray-200 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-gradient-to-r from-blue-500 to-green-500 transition-all duration-300"
                                            style={{ width: `${uploadProgress[uploadedVideo.name]}%` }}
                                        ></div>
                                    </div>
                                ) : null}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium text-gray-900 truncate">{uploadedVideo.name}</div>
                                <div className="text-[10px] text-gray-500">
                                    {uploadedVideo.duration} • {uploadedVideo.confidence}
                                    {uploadProgress[uploadedVideo.name] < 100 && (
                                        <span className="ml-2 text-blue-500">
                                            Uploading... {uploadProgress[uploadedVideo.name]}%
                                        </span>
                                    )}
                                </div>
                            </div>
                            <div className="flex flex-col items-end gap-1">
                                <div className="flex items-center gap-1">
                                    <span className="text-[10px] font-medium text-gray-500">{uploadedVideo.lang}</span>
                                </div>
                                <button
                                    onClick={removeVideo}
                                    className="text-[10px] text-red-500 hover:text-red-700 font-bold"
                                >
                                    Remove
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="bg-gray-50/50 border border-dashed border-gray-200 rounded-xl p-4 text-center">
                            <p className="text-xs text-gray-400">No video uploaded yet</p>
                            <p className="text-[10px] text-gray-300 mt-1">Upload a file or paste a URL</p>
                        </div>
                    )}
                </div>

                {/* Column 2: Localization Matrix */}
                <div className="bg-white rounded-3xl p-6 shadow-xl shadow-gray-200/50 border border-gray-100 flex flex-col h-full relative overflow-hidden transition-all duration-300 hover:shadow-2xl hover:shadow-purple-100/50">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-purple-400 to-pink-400"></div>

                    <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-6 text-center">Localization Matrix</h2>

                    {/* AI Detection Toggle */}
                    <div className="bg-gradient-to-r from-gray-50 to-purple-50/30 rounded-xl p-4 mb-6 flex items-center justify-between border border-gray-100">
                        <div className="flex flex-col">
                            <span className="text-xs font-bold text-gray-700">AI-POWERED LANGUAGE DETECTION</span>
                            <span className="text-[10px] text-gray-400 mt-1">
                                Source Language: {sourceLang} - {useAiDetection ? '98%' : 'Manual'} Confidence
                            </span>
                        </div>
                        <div
                            className={`w-12 h-6 rounded-full p-1 cursor-pointer transition-all duration-300 ${useAiDetection ? 'bg-gradient-to-r from-blue-500 to-purple-500' : 'bg-gray-300'}`}
                            onClick={() => setUseAiDetection(!useAiDetection)}
                        >
                            <div className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform duration-300 ${useAiDetection ? 'translate-x-6' : 'translate-x-0'}`}></div>
                        </div>
                    </div>

                    {/* Selected Languages Display Box */}
                    <div className="mb-4">
                        <div className="flex justify-between items-center mb-2">
                            <span className="text-xs text-gray-500">
                                Selected: <span className="font-bold text-purple-600">{selectedLanguages.length}</span> languages
                            </span>
                            <button
                                onClick={() => setSelectedLanguages([])}
                                className="text-[10px] text-red-500 hover:text-red-700 font-bold"
                            >
                                Clear All
                            </button>
                        </div>
                        <div className="min-h-16 bg-gray-50 border border-gray-200 rounded-lg p-3 mb-4">
                            {selectedLanguages.length > 0 ? (
                                <div className="flex flex-wrap gap-2">
                                    {selectedLanguages.map(code => {
                                        const lang = languages.find(l => l.code === code);
                                        return (
                                            <div
                                                key={code}
                                                className="flex items-center gap-1 bg-white border border-purple-200 rounded-full px-3 py-1.5"
                                            >
                                                <span className="text-xs">{lang?.flag || '🌐'}</span>
                                                <span className="text-xs font-medium text-gray-700">{lang?.name || code}</span>
                                                <button
                                                    onClick={() => removeSelectedLanguage(code)}
                                                    className="ml-1 text-[10px] text-gray-400 hover:text-red-500"
                                                >
                                                    ×
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                            ) : (
                                <div className="text-center py-4">
                                    <span className="text-xs text-gray-400">No languages selected</span>
                                    <p className="text-[10px] text-gray-300 mt-1">Click on languages below to add them</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Language Grid */}
                    <div className="grid grid-cols-3 gap-3">
                        {paginatedLanguages.map((lang) => (
                            <div
                                key={lang.code}
                                onClick={() => handleLanguageSelect(lang.code)}
                                className={`border rounded-xl p-3 flex flex-col items-center justify-center cursor-pointer transition-all duration-300 group relative ${selectedLanguages.includes(lang.code)
                                    ? 'border-purple-300 bg-purple-50/50 shadow-md shadow-purple-100'
                                    : 'border-gray-100 hover:border-blue-300 hover:shadow-md'
                                    }`}
                            >
                                <span className="text-2xl mb-2 group-hover:scale-110 transition-transform">{lang.flag}</span>
                                <span className="text-xs font-semibold text-gray-700 text-center">{lang.name}</span>
                                <div className="mt-2 w-full bg-gray-100 h-1.5 rounded-full overflow-hidden">
                                    <div
                                        className="h-full rounded-full transition-all duration-500"
                                        style={{
                                            width: lang.progress,
                                            background: selectedLanguages.includes(lang.code)
                                                ? 'linear-gradient(to right, #8b5cf6, #ec4899)'
                                                : 'linear-gradient(to right, #60a5fa, #8b5cf6)'
                                        }}
                                    ></div>
                                </div>
                                <span className={`text-[10px] mt-1 ${selectedLanguages.includes(lang.code) ? 'text-purple-600 font-bold' : 'text-gray-400'}`}>
                                    {lang.progress}
                                </span>
                                {selectedLanguages.includes(lang.code) && (
                                    <div className="absolute top-2 right-2 w-2 h-2 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full"></div>
                                )}
                            </div>
                        ))}
                    </div>

                    {/* Pagination with Arrows */}
                    <div className="mt-auto pt-4 border-t border-gray-100">
                        <div className="flex justify-between items-center">
                            <div className="text-[10px] text-gray-500">
                                Page {currentPage} of {totalPages}
                            </div>
                            <div className="flex items-center gap-4">
                                <button
                                    onClick={prevPage}
                                    disabled={currentPage === 1}
                                    className={`p-1.5 rounded-full transition-all duration-300 ${currentPage === 1
                                        ? 'text-gray-300 cursor-not-allowed'
                                        : 'text-purple-600 hover:bg-purple-50 hover:scale-110'
                                        }`}
                                    title="Previous page"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                                    </svg>
                                </button>

                                <div className="text-xs font-medium text-gray-700">
                                    {currentPage} / {totalPages}
                                </div>

                                <button
                                    onClick={nextPage}
                                    disabled={currentPage === totalPages}
                                    className={`p-1.5 rounded-full transition-all duration-300 ${currentPage === totalPages
                                        ? 'text-gray-300 cursor-not-allowed'
                                        : 'text-purple-600 hover:bg-purple-50 hover:scale-110'
                                        }`}
                                    title="Next page"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Column 3: Voice Intelligence */}
                <div className="bg-white rounded-3xl p-6 shadow-xl shadow-gray-200/50 border border-gray-100 flex flex-col h-full relative overflow-hidden transition-all duration-300 hover:shadow-2xl hover:shadow-pink-100/50">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-pink-400 to-rose-400"></div>

                    <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-6 text-center">Voice Intelligence</h2>

                    {/* Speaker Mapping */}
                    <div className="mb-8">
                        <div className="flex justify-between items-center mb-3">
                            <h3 className="text-xs font-semibold text-gray-400 uppercase">Speaker Mapping</h3>
                            <span className="text-[10px] text-gray-500">
                                {speakerMappings.filter(s => s.voiceClone).length} cloned
                            </span>
                        </div>

                        <div className="space-y-3">
                            {speakerMappings.map((speaker) => (
                                <div
                                    key={speaker.id}
                                    className={`bg-gradient-to-r from-gray-50 to-white border rounded-lg p-3 flex items-center justify-between transition-all duration-300 ${speaker.voiceClone
                                        ? 'border-pink-200 shadow-sm shadow-pink-100/50'
                                        : 'border-gray-100'
                                        }`}
                                >
                                    <div>
                                        <div className="text-xs font-bold text-gray-800">
                                            {speaker.name} ({speaker.gender})
                                        </div>
                                        <div className="text-[10px] text-gray-500">
                                            Target: {getLanguageName(speaker.targetLang)}
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => toggleVoiceClone(speaker.id)}
                                        className={`px-3 py-1 text-[10px] font-bold rounded-full border transition-all duration-300 ${speaker.voiceClone
                                            ? 'bg-gradient-to-r from-pink-500 to-rose-500 text-white border-transparent hover:shadow-lg hover:shadow-pink-200'
                                            : 'bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200'
                                            }`}
                                    >
                                        {speaker.voiceClone ? '✓ Cloned' : 'Voice Clone'}
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Tone & Emotion Sliders */}
                    <div className="mb-6 space-y-5">
                        <div className="flex justify-between items-center mb-2">
                            <h3 className="text-xs font-semibold text-gray-400 uppercase">Tone & Emotion</h3>
                            <button
                                onClick={resetToneSettings}
                                className="text-[10px] text-blue-500 hover:text-blue-700 font-bold"
                            >
                                Reset to 0
                            </button>
                        </div>

                        {Object.entries(toneSettings).map(([key, value]) => (
                            <div key={key} className="flex items-center gap-4">
                                <span className="text-xs font-medium text-gray-600 w-12 capitalize">
                                    {key}
                                </span>
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    value={value}
                                    onChange={(e) => handleToneChange(key, e.target.value)}
                                    className="flex-1 accent-gradient h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                                />
                                <span className="text-[10px] font-bold w-8 text-center text-blue-600">
                                    {value}%
                                </span>
                            </div>
                        ))}
                    </div>

                    {/* Glossary Upload */}
                    <div className="mt-auto">
                        <h3 className="text-xs font-semibold text-gray-400 mb-3 uppercase">Glossary Upload</h3>
                        <div className="relative">
                            <div
                                onClick={() => document.getElementById('glossary-upload').click()}
                                className="bg-gradient-to-r from-gray-50 to-blue-50 border border-dashed border-gray-300 rounded-xl p-4 flex items-center gap-3 cursor-pointer hover:bg-blue-50 hover:border-blue-300 transition-all duration-300 group"
                            >
                                <div className="w-8 h-8 bg-gradient-to-br from-blue-100 to-blue-200 rounded-lg flex items-center justify-center text-blue-600 group-hover:scale-110 transition-transform">
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                </div>
                                <div className="flex-1">
                                    {glossaryFile ? (
                                        <div>
                                            <div className="text-xs font-bold text-gray-700">{glossaryFile.name}</div>
                                            <div className="text-[10px] text-gray-400">{glossaryFile.size} • {glossaryFile.terms} terms</div>
                                        </div>
                                    ) : (
                                        <div>
                                            <div className="text-xs font-bold text-gray-700">Upload CSV of Key Terms</div>
                                            <div className="text-[10px] text-gray-400">Maximize translation accuracy</div>
                                        </div>
                                    )}
                                </div>
                                {glossaryFile && (
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setGlossaryFile(null);
                                        }}
                                        className="text-[10px] text-red-500 hover:text-red-700 font-bold"
                                    >
                                        Remove
                                    </button>
                                )}
                            </div>
                            <input
                                id="glossary-upload"
                                type="file"
                                accept=".csv"
                                className="hidden"
                                onChange={handleGlossaryUpload}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* Footer Action */}
            <div className="mt-8 flex flex-col items-center animate-bounce-in">
                {isProcessing ? (
                    <div className="w-96 bg-gray-100 rounded-full h-3 mb-4 overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 transition-all duration-500 rounded-full"
                            style={{ width: `${processingProgress}%` }}
                        ></div>
                    </div>
                ) : null}

                <button
                    onClick={handleGenerateVideo}
                    disabled={isProcessing || (!uploadedVideo && !videoUrl)}
                    className={`bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 text-white font-bold py-4 px-12 rounded-full shadow-lg transform transition-all text-sm tracking-widest uppercase ${isProcessing || (!uploadedVideo && !videoUrl)
                        ? 'opacity-50 cursor-not-allowed'
                        : 'shadow-purple-200 hover:shadow-purple-300 hover:scale-105 active:scale-95'
                        }`}
                >
                    {isProcessing ? (
                        <span className="flex items-center gap-2">
                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                            Processing... {processingProgress.toFixed(0)}%
                        </span>
                    ) : (
                        'Generate Globalized Video'
                    )}
                </button>
                <p className="text-xs text-gray-400 mt-3 font-medium">
                    Estimated Time: <span className="text-gray-600">{calculateEstimatedTime()} mins</span>
                    <span className="ml-4">
                        Languages: <span className="text-purple-600 font-bold">{selectedLanguages.length}</span>
                    </span>
                </p>
            </div>

            {/* Processing Overlay */}
            {isProcessing && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl p-8 max-w-md text-center animate-scale-in">
                        <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-r from-blue-500 to-purple-500 flex items-center justify-center">
                            <svg className="w-10 h-10 text-white animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                        </div>
                        <h3 className="text-lg font-bold text-gray-800 mb-2">Processing Video</h3>
                        <p className="text-gray-600 text-sm mb-4">
                            Processing {selectedLanguages.length} languages with {speakerMappings.filter(s => s.voiceClone).length} cloned voices
                        </p>
                        <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
                            <div
                                className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-300"
                                style={{ width: `${processingProgress}%` }}
                            ></div>
                        </div>
                        <p className="text-xs text-gray-500">
                            {processingProgress < 100 ? 'This may take a few minutes...' : 'Complete!'}
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
};

export default InputPage;