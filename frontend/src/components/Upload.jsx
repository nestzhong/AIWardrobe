import { useEffect, useRef, useState } from 'react'
import { Upload as UploadIcon, Camera, Image as ImageIcon, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useUpload } from '../contexts/UploadContext'
import GarmentReview from './GarmentReview'
import { API_BASE } from '../utils/api'

export default function Upload({ onUploadSuccess }) {
    const { t } = useTranslation()
    const {
        isUploading,
        progress,
        statusKey,
        current,
        total,
        completedSingleItem,
        batchResult,
        lastError,
        uploadFiles,
        captureAnalyze,
        consumeCompletedSingleItem,
        consumeBatchResult,
        consumeLastError
    } = useUpload()
    const [isDragging, setIsDragging] = useState(false)
    const [showCamera, setShowCamera] = useState(false)
    const [captureEnabled, setCaptureEnabled] = useState(false)
    const [captureData, setCaptureData] = useState(null)
    const fileInputRef = useRef(null)
    const cameraInputRef = useRef(null)
    const videoRef = useRef(null)
    const streamRef = useRef(null)

    useEffect(() => {
        let active = true
        fetch(`${API_BASE}/config`)
            .then(response => (response.ok ? response.json() : null))
            .then(data => {
                if (active && data) {
                    setCaptureEnabled(Boolean(data.experimental_garment_pipeline))
                }
            })
            .catch(() => {})
        return () => { active = false }
    }, [])

    const status = statusKey
        ? (total > 1 && current > 0 ? `${t(statusKey)} (${current}/${total})` : t(statusKey))
        : ''

    const startUpload = async (files) => {
        if (!files || files.length === 0) return

        if (captureEnabled && files.length === 1) {
            try {
                const result = await captureAnalyze(files[0])
                setCaptureData(result)
            } catch (error) {
                const message = error?.message === 'INVALID_IMAGE_TYPE'
                    ? t('upload.selectImage')
                    : (error?.message || 'UPLOAD_FAILED')
                alert(`${t('upload.uploadFailed')}: ${message}`)
            }
            return
        }

        void uploadFiles(files)
    }

    useEffect(() => {
        if (!completedSingleItem) return
        onUploadSuccess?.(completedSingleItem)
        consumeCompletedSingleItem()
    }, [completedSingleItem, onUploadSuccess, consumeCompletedSingleItem])

    useEffect(() => {
        if (!batchResult) return
        alert(t('upload.batchResult', batchResult))
        consumeBatchResult()
    }, [batchResult, t, consumeBatchResult])

    useEffect(() => {
        if (!lastError) return
        const translatedError = lastError === 'INVALID_IMAGE_TYPE'
            ? t('upload.selectImage')
            : lastError
        alert(`${t('upload.uploadFailed')}: ${translatedError}`)
        consumeLastError()
    }, [lastError, t, consumeLastError])

    const handleDragOver = (e) => {
        e.preventDefault()
        setIsDragging(true)
    }

    const handleDragLeave = (e) => {
        e.preventDefault()
        setIsDragging(false)
    }

    const handleDrop = (e) => {
        e.preventDefault()
        setIsDragging(false)
        const files = e.dataTransfer.files
        if (files.length > 0) {
            void startUpload(Array.from(files))
        }
    }

    const handleUploadClick = () => {
        fileInputRef.current?.click()
    }

    const handleCameraClick = () => {
        if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
            cameraInputRef.current?.click()
        } else {
            startCamera()
        }
    }

    const startCamera = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            })
            streamRef.current = stream
            if (videoRef.current) {
                videoRef.current.srcObject = stream
            }
            setShowCamera(true)
        } catch (err) {
            console.error('Camera error:', err)
            alert(t('upload.cameraError'))
        }
    }

    const stopCamera = () => {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop())
            streamRef.current = null
        }
        setShowCamera(false)
    }

    const capturePhoto = () => {
        if (!videoRef.current) return

        const canvas = document.createElement('canvas')
        canvas.width = videoRef.current.videoWidth
        canvas.height = videoRef.current.videoHeight
        const ctx = canvas.getContext('2d')
        ctx.drawImage(videoRef.current, 0, 0)

        canvas.toBlob((blob) => {
            if (blob) {
                const file = new File([blob], 'camera-photo.jpg', { type: 'image/jpeg' })
                void startUpload([file])
                stopCamera()
            }
        }, 'image/jpeg', 0.9)
    }

    const handleFileChange = (e) => {
        const files = e.target.files
        if (files && files.length > 0) {
            void startUpload(Array.from(files))
        }
        e.target.value = ''
    }

    if (showCamera) {
        return (
            <div className="fixed inset-0 z-50 bg-black flex flex-col">
                <div className="flex-1 relative">
                    <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        className="w-full h-full object-cover"
                    />
                </div>
                <div className="h-32 bg-black pb-safe flex items-center justify-around px-8">
                    <button className="p-4 text-white hover:text-red-400 transition-colors" onClick={stopCamera}>
                        <X size={28} />
                    </button>
                    <button className="w-16 h-16 rounded-full bg-white border-4 border-zinc-300 active:scale-95 transition-transform" onClick={capturePhoto}></button>
                    <div className="w-14"></div>
                </div>
            </div>
        )
    }

    if (captureData) {
        return (
            <div className="w-full">
                <GarmentReview
                    data={captureData}
                    onCancel={() => setCaptureData(null)}
                    onDone={(created) => {
                        setCaptureData(null)
                        if (created.length === 1) {
                            onUploadSuccess?.(created[0])
                        }
                    }}
                />
            </div>
        )
    }

    return (
        <div className="w-full">
            <div
                className={`liquid-upload relative overflow-hidden transition-all duration-300 flex flex-col items-center justify-center p-8 ${
                    isDragging ? 'scale-[1.01] border-[var(--accent)]' : 'hover:border-[var(--accent)]'
                }`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                style={{ minHeight: '300px' }}
            >
                <div className="liquid-glass w-16 h-16 mb-4 rounded-full flex items-center justify-center text-[var(--accent)]">
                    <UploadIcon size={28} />
                </div>

                <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-1">{t('upload.title')}</h3>
                <p className="text-sm text-[var(--text-secondary)] mb-8 text-center leading-relaxed">{t('upload.subtitle')}<br />{t('upload.subtitleAI')}</p>

                <div className="flex flex-col sm:flex-row gap-4 w-full max-w-xs">
                    <button className="flex-1 btn-primary" onClick={handleCameraClick}>
                        <Camera size={18} />
                        {t('upload.camera')}
                    </button>
                    <button className="flex-1 btn-secondary" onClick={handleUploadClick}>
                        <ImageIcon size={18} />
                        {t('upload.album')}
                    </button>
                </div>

                <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={handleFileChange}
                />
                <input
                    ref={cameraInputRef}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    className="hidden"
                    onChange={handleFileChange}
                />
            </div>

            {isUploading && (
                <div className="mt-6 space-y-2 animate-fade-in">
                    <div className="flex justify-between text-sm font-medium">
                        <span className="text-[var(--text-secondary)]">{status}</span>
                        <span className="text-[var(--accent)]">{progress}%</span>
                    </div>
                    <div className="liquid-glass h-2.5 w-full rounded-full overflow-hidden">
                        <div
                            className="h-full transition-all duration-300 relative top-0 left-0"
                            style={{ width: `${progress}%` }}
                        >
                            <div className="absolute inset-0 bg-gradient-to-r from-[var(--accent)] to-[var(--accent-2)]"></div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
